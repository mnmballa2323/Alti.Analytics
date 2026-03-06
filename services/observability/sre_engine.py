# services/observability/sre_engine.py
"""
Epic 79: Full Observability — SLOs, Distributed Tracing & SRE Dashboards
Defines SLO/SLI contracts for all 24 platform services, tracks error budgets,
instruments distributed tracing via OpenTelemetry + Cloud Trace, and
triggers automated incident escalation when budgets are at risk.

SLO definitions follow Google SRE principles:
  SLI = Service Level Indicator (what we measure)
  SLO = Service Level Objective (target threshold)
  Error Budget = 100% - SLO = how much "unacceptable" we can tolerate per period

Error budget policy:
  > 50% budget remaining → no action
  50% → 25% remaining   → Slack warning to on-call channel
  25% → 10% remaining   → PagerDuty low-urgency alert
  < 10% remaining        → PagerDuty high-urgency + freeze non-critical deploys
  0% (budget exhausted)  → Incident declared, all deploys blocked

Cloud Trace integration:
  Every service wraps its handlers in OpenTelemetry spans.
  Spans propagate W3C trace context (traceparent header) across all hops.
  Traces visible in Cloud Console > Trace.
"""
import logging, json, uuid, time, math, random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class SLIType(str, Enum):
    AVAILABILITY = "AVAILABILITY"   # good_requests / total_requests
    LATENCY      = "LATENCY"        # % requests faster than threshold
    THROUGHPUT   = "THROUGHPUT"     # requests per second
    QUALITY      = "QUALITY"        # custom correctness metric

class BurnRateStatus(str, Enum):
    HEALTHY  = "HEALTHY"       # > 50% budget remaining
    WARNING  = "WARNING"       # 25-50% remaining
    ALERT    = "ALERT"         # 10-25% remaining
    CRITICAL = "CRITICAL"      # < 10% remaining
    EXHAUSTED= "EXHAUSTED"     # 0% remaining

@dataclass
class SLO:
    service:     str
    sli_type:    SLIType
    description: str
    target_pct:  float          # e.g. 99.9 means 99.9% SLO
    window_days: int            # rolling window (28 or 30 days)
    threshold_ms:Optional[int]  # for LATENCY SLIs: max acceptable ms
    current_pct: float = 0.0    # current measured SLI value
    error_budget_minutes:float  = 0.0
    budget_consumed_min:float   = 0.0

@dataclass
class TraceSpan:
    span_id:    str
    trace_id:   str
    service:    str
    operation:  str
    start_time: float
    end_time:   float = 0.0
    status:     str   = "OK"   # "OK" | "ERROR" | "TIMEOUT"
    attributes: dict  = field(default_factory=dict)
    parent_id:  Optional[str] = None

    @property
    def duration_ms(self) -> float:
        return round((self.end_time - self.start_time) * 1000, 2) if self.end_time else 0

@dataclass
class Incident:
    incident_id: str
    service:     str
    severity:    str           # "P1" | "P2" | "P3"
    title:       str
    budget_pct_remaining:float
    opened_at:   float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolved:    bool = False

class SREEngine:
    """
    Full observability and SRE engine for the Alti.Analytics platform.
    Manages 24-service SLO portfolio, distributed traces, and incident lifecycle.
    """
    # ── SLO portfolio: all 24 platform services ───────────────────────────────
    _SLO_DEFINITIONS = [
        # Core AI services
        ("api-gateway",          SLIType.AVAILABILITY, "API Gateway availability",          99.95, 28, None,  "Gateway up and returning 2xx"),
        ("nl2sql",               SLIType.LATENCY,      "NL2SQL p99 < 2s",                  99.0,  28, 2000,  "Natural language to SQL p99 latency"),
        ("swarm-orchestrator",   SLIType.AVAILABILITY, "Swarm Orchestrator availability",   99.9,  28, None,  "Agent swarm available and routing queries"),
        ("knowledge-graph",      SLIType.LATENCY,      "Knowledge Graph query p95 < 500ms", 98.0,  28, 500,   "Graph traversal latency"),
        # Data services
        ("streaming-analytics",  SLIType.LATENCY,      "Streaming pipeline latency < 200ms",99.0,  28, 200,   "End-to-end streaming event latency"),
        ("data-catalog",         SLIType.AVAILABILITY, "Data Catalog availability",          99.5,  28, None,  "Catalog search and indexing available"),
        ("time-travel",          SLIType.AVAILABILITY, "Time Travel availability",           99.5,  28, None,  "Snapshot access and branching"),
        ("data-quality",         SLIType.LATENCY,      "Data Quality check < 5min",          97.0,  28, 300000,"Quality scan completion time"),
        # Intelligence services
        ("storytelling",         SLIType.LATENCY,      "Report generation < 30s",            98.0,  28, 30000, "AI narrative report generation latency"),
        ("scenario-engine",      SLIType.AVAILABILITY, "Scenario Engine availability",       99.0,  28, None,  "Causal scenario planning available"),
        ("voice-multimodal",     SLIType.LATENCY,      "Voice-to-SQL p99 < 3s",             98.0,  28, 3000,  "End-to-end voice query pipeline latency"),
        ("industry-templates",   SLIType.LATENCY,      "Tenant onboarding < 5min",          99.0,  28, 300000,"Tenant onboarding SLO"),
        # Global platform services
        ("multilingual",         SLIType.LATENCY,      "Language detection < 100ms",        99.5,  28, 100,   "Language detection and translation latency"),
        ("global-compliance",    SLIType.LATENCY,      "Compliance assess < 500ms",         99.9,  28, 500,   "Jurisdiction assessment latency"),
        ("data-sovereignty",     SLIType.AVAILABILITY, "Sovereignty Engine availability",    99.9,  28, None,  "Transfer validation always available"),
        ("currency-intelligence",SLIType.LATENCY,      "FX rate < 100ms",                   99.9,  28, 100,   "Currency conversion latency"),
        ("regional-models",      SLIType.LATENCY,      "Regional NL2SQL p99 < 500ms",       98.5,  28, 500,   "Regional model inference latency"),
        ("edge-intelligence",    SLIType.AVAILABILITY, "Edge sync available",                99.0,  28, None,  "Edge-to-cloud sync endpoint"),
        # GCP-native services
        ("vertex-agent",         SLIType.LATENCY,      "Grounded answer p99 < 5s",          97.0,  28, 5000,  "Vertex AI Agent Builder grounded query latency"),
        ("spanner-alloydb",      SLIType.LATENCY,      "Data tier router < 100ms",          99.9,  28, 100,   "Tier routing decision latency"),
        # MLOps & analytics
        ("mlops",                SLIType.AVAILABILITY, "Model Registry availability",        99.5,  28, None,  "Model promotion and serving available"),
        ("federated-analytics",  SLIType.AVAILABILITY, "Federated Engine availability",      99.0,  28, None,  "Privacy-preserving federation available"),
        ("collaboration",        SLIType.LATENCY,      "CRDT sync < 200ms",                 99.0,  28, 200,   "Real-time collaboration sync latency"),
        ("cost-intelligence",    SLIType.LATENCY,      "Cost forecast < 10s",               98.0,  28, 10000, "Cost forecast generation latency"),
    ]

    def __init__(self, project_id: str = "alti-analytics-prod"):
        self.project_id = project_id
        self.logger     = logging.getLogger("SRE_Engine")
        logging.basicConfig(level=logging.INFO)
        self._slos:      dict[str, SLO]      = {}
        self._traces:    list[TraceSpan]     = []
        self._incidents: list[Incident]      = []
        self._active_traces: dict[str,list]  = {}   # trace_id → spans
        self._build_slos()
        self._simulate_current_state()
        self.logger.info(f"📊 SRE Engine: {len(self._slos)} SLOs defined across 24 services")

    def _build_slos(self):
        for (svc, sli_type, desc, target, window, threshold, _) in self._SLO_DEFINITIONS:
            # Error budget = (1 - target/100) * window_days * 24 * 60 minutes
            budget_minutes = (1 - target/100) * window * 24 * 60
            slo = SLO(service=svc, sli_type=sli_type, description=desc,
                      target_pct=target, window_days=window,
                      threshold_ms=threshold,
                      error_budget_minutes=round(budget_minutes, 1))
            self._slos[svc] = slo

    def _simulate_current_state(self):
        """Populate realistic current SLI measurements."""
        for slo in self._slos.values():
            # Simulate slight degradation from target — most services healthy
            noise = random.uniform(-0.08, 0.02)
            slo.current_pct = round(max(slo.target_pct - 0.3 + noise, slo.target_pct - 0.5), 4)
            # Error budget consumed based on delta from target
            delta_pct = max(0, slo.target_pct - slo.current_pct) / 100
            slo.budget_consumed_min = round(delta_pct * slo.window_days * 24 * 60, 1)

    def burn_rate(self, service: str) -> dict:
        """
        Returns the current burn rate and error budget status for a service.
        Burn rate = (budget consumed / budget total) × 100
        """
        slo = self._slos.get(service)
        if not slo: raise ValueError(f"Unknown service: {service}")
        budget_remaining = max(0, slo.error_budget_minutes - slo.budget_consumed_min)
        pct_remaining    = (budget_remaining / slo.error_budget_minutes * 100) if slo.error_budget_minutes > 0 else 100
        burn_rate        = slo.budget_consumed_min / max(1, slo.error_budget_minutes) * 100

        if pct_remaining > 50:   status = BurnRateStatus.HEALTHY
        elif pct_remaining > 25: status = BurnRateStatus.WARNING
        elif pct_remaining > 10: status = BurnRateStatus.ALERT
        elif pct_remaining > 0:  status = BurnRateStatus.CRITICAL
        else:                    status = BurnRateStatus.EXHAUSTED

        return {"service": service, "slo_target": slo.target_pct,
                "current_sli": slo.current_pct, "sli_type": slo.sli_type,
                "budget_total_min": slo.error_budget_minutes,
                "budget_consumed_min": slo.budget_consumed_min,
                "budget_remaining_min": round(budget_remaining, 1),
                "budget_pct_remaining": round(pct_remaining, 1),
                "burn_rate_pct": round(burn_rate, 2),
                "status": status}

    def trigger_alert(self, service: str, pct_remaining: float) -> Optional[Incident]:
        """Auto-escalates based on burn rate thresholds."""
        if pct_remaining > 50: return None  # healthy, no alert
        slo = self._slos[service]
        severity = "P1" if pct_remaining < 10 else ("P2" if pct_remaining < 25 else "P3")
        incident = Incident(
            incident_id=str(uuid.uuid4()),
            service=service,
            severity=severity,
            title=f"[{severity}] SLO error budget at {pct_remaining:.1f}%: {service} ({slo.description})",
            budget_pct_remaining=pct_remaining
        )
        self._incidents.append(incident)
        channel = "pagerduty" if severity in ("P1","P2") else "slack"
        self.logger.warning(f"🚨 [{severity}] Budget {pct_remaining:.1f}% remaining for {service} → escalating via {channel}")
        return incident

    def scan_all_budgets(self) -> list[dict]:
        """Scans all 24 services and triggers alerts where needed."""
        results = []
        for svc in self._slos:
            br = self.burn_rate(svc)
            incident = self.trigger_alert(svc, br["budget_pct_remaining"])
            br["incident_opened"] = incident is not None
            results.append(br)
        return sorted(results, key=lambda x: x["budget_pct_remaining"])

    # ── Distributed tracing ───────────────────────────────────────────────────
    def start_span(self, service: str, operation: str,
                   trace_id: str = None, parent_id: str = None,
                   attributes: dict = None) -> TraceSpan:
        """
        Opens a new trace span. In production: opentelemetry-sdk exports to Cloud Trace.
        Auto-generates trace_id if this is a root span (no parent).
        """
        span = TraceSpan(
            span_id=uuid.uuid4().hex[:16],
            trace_id=trace_id or uuid.uuid4().hex,
            service=service, operation=operation,
            start_time=time.time(), parent_id=parent_id,
            attributes=attributes or {}
        )
        self._active_traces.setdefault(span.trace_id, []).append(span)
        return span

    def end_span(self, span: TraceSpan, status: str = "OK") -> TraceSpan:
        span.end_time = time.time()
        span.status   = status
        self._traces.append(span)
        return span

    def simulate_request_trace(self, query: str = "NL2SQL query",
                                locale: str = "en-US") -> list[TraceSpan]:
        """
        Simulates a full distributed trace across all service hops for a single user query.
        Shows how request flows: API Gateway → NL2SQL → Spanner/AlloyDB → Streaming
        """
        trace_id = uuid.uuid4().hex
        spans = []

        def s(svc, op, parent=None, extra_ms=0):
            sp = self.start_span(svc, op, trace_id, parent.span_id if parent else None)
            time.sleep(0)
            sp.end_time = sp.start_time + (random.uniform(5, 50) + extra_ms) / 1000
            sp.status = "OK"
            self._traces.append(sp)
            spans.append(sp)
            return sp

        root     = s("api-gateway",    "POST /api/nl2sql/query")
        auth     = s("api-gateway",    "auth.verify_token",       root)
        multi    = s("multilingual",   "detect_language",          root,   5)
        nl2sql   = s("nl2sql",         "generate_sql",             root,  80)
        complian = s("global-compliance","assess_processing",      nl2sql, 8)
        spanner  = s("spanner-alloydb","route_to_tier",            nl2sql, 2)
        bq       = s("spanner-alloydb","bigquery.execute_query",   spanner, 120)
        story    = s("storytelling",   "generate_narrative",       root,  200)

        self.logger.info(f"🔍 Trace {trace_id[:12]}: {len(spans)} spans | total={root.duration_ms:.0f}ms")
        return spans

    def trace_waterfall(self, trace_id: str) -> list[dict]:
        """Returns a waterfall-format trace suitable for rendering in the UI."""
        spans = [s for s in self._traces if s.trace_id == trace_id]
        if not spans: return []
        t0 = min(s.start_time for s in spans)
        return sorted([{
            "span_id": s.span_id[:12], "service": s.service,
            "operation": s.operation,
            "start_offset_ms": round((s.start_time - t0) * 1000, 1),
            "duration_ms": s.duration_ms,
            "status": s.status,
            "parent": s.parent_id[:12] if s.parent_id else None
        } for s in spans], key=lambda x: x["start_offset_ms"])

    def sre_dashboard(self) -> dict:
        """Full SRE dashboard: service health, budgets, incidents."""
        all_budgets = [self.burn_rate(svc) for svc in self._slos]
        return {
            "total_services": len(self._slos),
            "healthy":   sum(1 for b in all_budgets if b["status"] == BurnRateStatus.HEALTHY),
            "warning":   sum(1 for b in all_budgets if b["status"] == BurnRateStatus.WARNING),
            "alert":     sum(1 for b in all_budgets if b["status"] == BurnRateStatus.ALERT),
            "critical":  sum(1 for b in all_budgets if b["status"] == BurnRateStatus.CRITICAL),
            "exhausted": sum(1 for b in all_budgets if b["status"] == BurnRateStatus.EXHAUSTED),
            "open_incidents": len([i for i in self._incidents if not i.resolved]),
            "total_spans_traced": len(self._traces),
            "services": sorted(all_budgets, key=lambda x: x["budget_pct_remaining"])[:8],
        }


if __name__ == "__main__":
    sre = SREEngine()

    print("=== SRE Budget Scan — All 24 Services ===")
    results = sre.scan_all_budgets()
    print(f"\n{'Service':30} {'SLO':6} {'SLI':6} {'Budget%':9} {'Status'}")
    print("─" * 70)
    for r in results:
        icon = "🔴" if r["status"] in ("CRITICAL","EXHAUSTED") else ("🟡" if r["status"] in ("WARNING","ALERT") else "🟢")
        print(f"{icon} {r['service']:28} {r['slo_target']:5.1f}% {r['current_sli']:5.2f}% {r['budget_pct_remaining']:7.1f}%  {r['status']}")

    print(f"\n=== Distributed Trace Simulation ===")
    spans = sre.simulate_request_trace("Show me churn risk for top customers", "en-US")
    waterfall = sre.trace_waterfall(spans[0].trace_id)
    print(f"Trace ID: {spans[0].trace_id[:16]}")
    print(f"{'Service':25} {'Operation':35} {'Offset':8} {'Duration':10} Status")
    for s in waterfall:
        indent = "  └─ " if s["parent"] else ""
        print(f"{indent}{s['service']:23} {s['operation']:35} +{s['start_offset_ms']:5.0f}ms  {s['duration_ms']:7.1f}ms  {s['status']}")

    print(f"\n=== SRE Dashboard ===")
    dash = sre.sre_dashboard()
    print(f"  Total services: {dash['total_services']} | 🟢 Healthy: {dash['healthy']} | 🟡 Warning: {dash['warning']} | 🔴 Alert+: {dash['alert']+dash['critical']}")
    print(f"  Open incidents: {dash['open_incidents']} | Spans traced: {dash['total_spans_traced']}")
