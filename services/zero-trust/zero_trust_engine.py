# services/zero-trust/zero_trust_engine.py
"""
Epic 81: Zero-Trust Security Architecture
"Never trust, always verify" — every service-to-service call is
authenticated, authorized, and audited regardless of network location.

Components:
  mTLS enforcement    → Traffic Director sidecar proxy validates SPIFFE IDs
  Security Command Center Premium → continuous asset inventory + vuln scanning
  Chronicle SIEM      → all GCP audit logs streamed for threat correlation
  SOAR playbooks      → automated threat response within seconds of detection

Threat detection rules (Chronicle / Mandiant intelligence):
  - Impossible travel: API key used from 2 continents within 5 min
  - Credential stuffing: >10 failed auth attempts in 60s from same IP
  - Data exfiltration: single tenant scanning >50GB BigQuery in 1 hour
  - Privilege escalation: IAM role binding created outside Terraform
  - Lateral movement: service account calling unexpected APIs
  - Tenant isolation breach: query accessing another tenant's dataset

Automated SOAR responses (within 60 seconds):
  CRITICAL → disable service account + block IP + isolate tenant + page on-call
  HIGH     → rate-limit IP + alert Slack security channel + create SCC finding
  MEDIUM   → log to Chronicle + create Cloud Monitoring alert
"""
import logging, json, uuid, time, hashlib, random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class ThreatSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"
    INFO     = "INFO"

class ThreatCategory(str, Enum):
    IMPOSSIBLE_TRAVEL     = "IMPOSSIBLE_TRAVEL"
    CREDENTIAL_STUFFING   = "CREDENTIAL_STUFFING"
    DATA_EXFILTRATION     = "DATA_EXFILTRATION"
    PRIVILEGE_ESCALATION  = "PRIVILEGE_ESCALATION"
    LATERAL_MOVEMENT      = "LATERAL_MOVEMENT"
    TENANT_ISOLATION_BREACH = "TENANT_ISOLATION_BREACH"
    ANOMALOUS_API_USAGE   = "ANOMALOUS_API_USAGE"
    SUPPLY_CHAIN_ATTACK   = "SUPPLY_CHAIN_ATTACK"

class RemediationAction(str, Enum):
    DISABLE_SA       = "DISABLE_SERVICE_ACCOUNT"
    BLOCK_IP         = "BLOCK_IP_CLOUD_ARMOR"
    ISOLATE_TENANT   = "ISOLATE_TENANT_NETWORK"
    RATE_LIMIT_IP    = "RATE_LIMIT_IP"
    REVOKE_TOKEN     = "REVOKE_API_TOKEN"
    PAGE_ONCALL      = "PAGE_ONCALL_PAGERDUTY"
    SLACK_ALERT      = "SLACK_SECURITY_CHANNEL"
    CREATE_FINDING   = "CREATE_SCC_FINDING"
    TERMINATE_SESSION= "TERMINATE_ACTIVE_SESSIONS"

@dataclass
class ServiceIdentity:
    service_name: str
    spiffe_id:    str          # e.g. spiffe://alti.ai/ns/prod/sa/alti-prod-run-sa
    cert_fingerprint:str
    issued_at:    float
    expires_at:   float
    allowed_peers:list[str]   # SPIFFE IDs allowed to call this service

@dataclass
class MTLSHandshake:
    handshake_id:  str
    caller_service:str
    called_service:str
    caller_spiffe:  str
    called_spiffe:  str
    authorized:    bool
    rejection_reason:Optional[str]
    latency_ms:    float
    timestamp:     float = field(default_factory=time.time)

@dataclass
class ThreatEvent:
    event_id:      str
    category:      ThreatCategory
    severity:      ThreatSeverity
    tenant_id:     Optional[str]
    service:       str
    description:   str
    evidence:      dict
    actions_taken: list[RemediationAction]
    detected_at:   float = field(default_factory=time.time)
    resolved:      bool  = False

@dataclass
class SCCFinding:
    finding_id:   str
    category:     str
    severity:     ThreatSeverity
    resource_name:str
    description:  str
    recommendation:str
    state:        str       # "ACTIVE" | "INACTIVE"
    created_at:   float = field(default_factory=time.time)

class ZeroTrustEngine:
    """
    Enterprise Zero-Trust security layer for Alti.Analytics.
    Every service-to-service call is verified via mTLS + SPIFFE.
    All events are correlated in Chronicle for threat detection.
    SOAR playbooks auto-respond within 60 seconds of detection.
    """

    # Service mesh: allowed caller → callee pairs (zero-trust allow-list)
    _ALLOWED_PEERS = {
        "api-gateway":        ["*"],  # gateway can call any service
        "swarm-orchestrator": ["nl2sql","knowledge-graph","storytelling","scenario-engine",
                               "voice-multimodal","industry-templates","vertex-agent"],
        "nl2sql":             ["spanner-alloydb","data-catalog","multilingual"],
        "streaming-analytics":["spanner-alloydb","data-quality"],
        "mlops":              ["spanner-alloydb","vertex-agent"],
        "global-compliance":  ["spanner-alloydb"],
        "data-sovereignty":   ["global-compliance","spanner-alloydb"],
        "tenant-control-plane":["spanner-alloydb","global-compliance"],
        "observability":      ["*"],  # SRE can observe all services
    }

    # SOAR playbook: threat category → automated remediation actions
    _SOAR_PLAYBOOKS = {
        ThreatCategory.IMPOSSIBLE_TRAVEL: {
            ThreatSeverity.CRITICAL: [RemediationAction.REVOKE_TOKEN,
                                       RemediationAction.TERMINATE_SESSION,
                                       RemediationAction.SLACK_ALERT,
                                       RemediationAction.PAGE_ONCALL,
                                       RemediationAction.CREATE_FINDING],
        },
        ThreatCategory.CREDENTIAL_STUFFING: {
            ThreatSeverity.HIGH: [RemediationAction.BLOCK_IP,
                                   RemediationAction.RATE_LIMIT_IP,
                                   RemediationAction.SLACK_ALERT,
                                   RemediationAction.CREATE_FINDING],
        },
        ThreatCategory.DATA_EXFILTRATION: {
            ThreatSeverity.CRITICAL: [RemediationAction.ISOLATE_TENANT,
                                       RemediationAction.DISABLE_SA,
                                       RemediationAction.PAGE_ONCALL,
                                       RemediationAction.CREATE_FINDING],
        },
        ThreatCategory.PRIVILEGE_ESCALATION: {
            ThreatSeverity.CRITICAL: [RemediationAction.DISABLE_SA,
                                       RemediationAction.TERMINATE_SESSION,
                                       RemediationAction.PAGE_ONCALL,
                                       RemediationAction.CREATE_FINDING],
        },
        ThreatCategory.LATERAL_MOVEMENT: {
            ThreatSeverity.HIGH: [RemediationAction.ISOLATE_TENANT,
                                   RemediationAction.SLACK_ALERT,
                                   RemediationAction.CREATE_FINDING],
        },
        ThreatCategory.TENANT_ISOLATION_BREACH: {
            ThreatSeverity.CRITICAL: [RemediationAction.ISOLATE_TENANT,
                                       RemediationAction.DISABLE_SA,
                                       RemediationAction.PAGE_ONCALL,
                                       RemediationAction.CREATE_FINDING],
        },
    }

    def __init__(self, project_id: str = "alti-analytics-prod"):
        self.project_id    = project_id
        self.logger        = logging.getLogger("ZeroTrust")
        logging.basicConfig(level=logging.INFO)
        self._identities:  dict[str, ServiceIdentity] = {}
        self._handshakes:  list[MTLSHandshake]        = []
        self._threats:     list[ThreatEvent]          = []
        self._findings:    list[SCCFinding]           = []
        self._auth_log:    list[dict]                 = []
        self._register_service_mesh()
        self.logger.info(f"🔐 Zero-Trust Engine: {len(self._identities)} service identities | SOAR playbooks active")

    def _register_service_mesh(self):
        """Issues SPIFFE X.509 SVIDs for all 24 production services."""
        services = list(self._ALLOWED_PEERS.keys()) + [
            "data-catalog","time-travel","collaboration","federated-analytics",
            "industry-templates","storytelling","scenario-engine","voice-multimodal",
            "data-quality","multilingual","currency-intelligence","regional-models",
            "edge-intelligence","vertex-agent","spanner-alloydb","knowledge-graph",
            "cost-intelligence","data-sovereignty",
        ]
        for svc in set(services):
            spiffe = f"spiffe://alti.ai/ns/prod/sa/alti-prod-{svc}-sa"
            ident  = ServiceIdentity(
                service_name=svc, spiffe_id=spiffe,
                cert_fingerprint=hashlib.sha256(spiffe.encode()).hexdigest()[:16],
                issued_at=time.time(),
                expires_at=time.time() + 24*3600,  # SVIDs rotate every 24h
                allowed_peers=self._ALLOWED_PEERS.get(svc, [])
            )
            self._identities[svc] = ident

    def verify_mtls(self, caller: str, callee: str) -> MTLSHandshake:
        """
        Validates a service-to-service call via SPIFFE ID verification.
        In production: Traffic Director sidecar proxy enforces this
        before any TCP connection is established — zero network trust.
        """
        t0 = time.time()
        caller_id = self._identities.get(caller)
        callee_id = self._identities.get(callee)

        if not caller_id or not callee_id:
            authorized = False
            reason     = f"Unknown service identity: {'caller' if not caller_id else 'callee'}"
        elif time.time() > caller_id.expires_at:
            authorized = False
            reason     = f"SVID expired for {caller}"
        else:
            # Check allow-list
            allowed = self._ALLOWED_PEERS.get(callee, [])
            authorized = "*" in allowed or caller in allowed or \
                         self._ALLOWED_PEERS.get(caller, []) == ["*"]
            reason = None if authorized else f"{caller} not permitted to call {callee}"

        handshake = MTLSHandshake(
            handshake_id=str(uuid.uuid4()), caller_service=caller, called_service=callee,
            caller_spiffe=caller_id.spiffe_id if caller_id else "UNKNOWN",
            called_spiffe=callee_id.spiffe_id if callee_id else "UNKNOWN",
            authorized=authorized, rejection_reason=reason,
            latency_ms=round((time.time()-t0)*1000 + 0.8, 2)
        )
        self._handshakes.append(handshake)
        if not authorized:
            self.logger.warning(f"⛔ mTLS DENIED: {caller} → {callee} | {reason}")
            # Unauthorized calls trigger threat detection
            self.detect_threat(ThreatCategory.LATERAL_MOVEMENT, ThreatSeverity.HIGH,
                               None, caller,
                               f"Service {caller} attempted unauthorized call to {callee}",
                               {"caller": caller, "callee": callee, "spiffe": handshake.caller_spiffe})
        return handshake

    def detect_threat(self, category: ThreatCategory, severity: ThreatSeverity,
                      tenant_id: Optional[str], service: str,
                      description: str, evidence: dict) -> ThreatEvent:
        """
        Registers a detected threat and immediately runs the SOAR playbook.
        Response time target: < 60 seconds from detection to remediation.
        """
        playbook = self._SOAR_PLAYBOOKS.get(category, {})
        actions  = playbook.get(severity, [RemediationAction.SLACK_ALERT, RemediationAction.CREATE_FINDING])

        event = ThreatEvent(event_id=str(uuid.uuid4()), category=category,
                            severity=severity, tenant_id=tenant_id, service=service,
                            description=description, evidence=evidence,
                            actions_taken=actions)
        self._threats.append(event)

        # Run SOAR playbook
        for action in actions:
            self._execute_remediation(action, event)

        # Create SCC finding for CRITICAL/HIGH
        if severity in (ThreatSeverity.CRITICAL, ThreatSeverity.HIGH):
            self._create_scc_finding(event)

        self.logger.warning(f"🚨 [{severity}] {category}: {description[:80]} | actions: {[a.value for a in actions]}")
        return event

    def _execute_remediation(self, action: RemediationAction, event: ThreatEvent):
        """Executes a SOAR playbook action. In production: calls GCP APIs."""
        if action == RemediationAction.DISABLE_SA:
            self.logger.warning(f"  🔴 SOAR: Disabling service account for {event.service}")
        elif action == RemediationAction.BLOCK_IP:
            self.logger.warning(f"  🔴 SOAR: Adding IP to Cloud Armor denylist")
        elif action == RemediationAction.ISOLATE_TENANT:
            self.logger.warning(f"  🔴 SOAR: Isolating tenant {event.tenant_id} — VPC firewall rule applied")
        elif action == RemediationAction.REVOKE_TOKEN:
            self.logger.warning(f"  🔴 SOAR: Revoking all active tokens for affected principal")
        elif action == RemediationAction.PAGE_ONCALL:
            self.logger.warning(f"  📟 SOAR: PagerDuty P1 incident created for security team")
        elif action == RemediationAction.SLACK_ALERT:
            self.logger.info(f"  📣 SOAR: Slack #security-alerts notified")
        elif action == RemediationAction.CREATE_FINDING:
            pass  # handled in detect_threat
        elif action == RemediationAction.TERMINATE_SESSION:
            self.logger.warning(f"  🔴 SOAR: All active sessions terminated for affected user")

    def _create_scc_finding(self, event: ThreatEvent) -> SCCFinding:
        finding = SCCFinding(
            finding_id=str(uuid.uuid4()),
            category=event.category.value,
            severity=event.severity,
            resource_name=f"//cloudresourcemanager.googleapis.com/projects/{self.project_id}",
            description=event.description,
            recommendation=f"Review audit logs for {event.service}. Check Chronicle timeline for correlating events.",
            state="ACTIVE"
        )
        self._findings.append(finding)
        return finding

    def vulnerability_scan(self) -> list[dict]:
        """
        Simulates Security Command Center Premium vulnerability scan.
        In production: SCC continuously scans and this reads the findings API.
        """
        simulated_vulns = [
            {"resource": "cloud_run/alti-prod-regional-models", "category": "CONTAINER_VULNERABILITY",
             "severity": "MEDIUM", "cve": "CVE-2025-12345",
             "description": "Base image python:3.12-slim has known OpenSSL vulnerability",
             "fix": "Update base image to python:3.12.9-slim"},
            {"resource": "bigquery/alti_analytics_prod", "category": "PUBLIC_DATASET_ACCESS",
             "severity": "HIGH", "cve": None,
             "description": "BigQuery dataset has allAuthenticatedUsers reader binding",
             "fix": "Remove allAuthenticatedUsers from dataset IAM policy"},
            {"resource": "iam/alti-prod-run-sa", "category": "SERVICE_ACCOUNT_KEY",
             "severity": "LOW", "cve": None,
             "description": "Service account has user-managed key older than 90 days",
             "fix": "Rotate or delete service account keys; prefer Workload Identity Federation"},
        ]
        self.logger.info(f"🔍 SCC Vulnerability Scan: {len(simulated_vulns)} findings")
        return simulated_vulns

    def security_posture_dashboard(self) -> dict:
        critical_threats = sum(1 for t in self._threats if t.severity == ThreatSeverity.CRITICAL)
        denied_calls     = sum(1 for h in self._handshakes if not h.authorized)
        active_findings  = sum(1 for f in self._findings if f.state == "ACTIVE")
        return {
            "service_identities":   len(self._identities),
            "mtls_handshakes_total":len(self._handshakes),
            "mtls_denied":          denied_calls,
            "threats_detected":     len(self._threats),
            "critical_threats":     critical_threats,
            "active_scc_findings":  active_findings,
            "soar_actions_taken":   sum(len(t.actions_taken) for t in self._threats),
            "svid_rotation_hours":  24,
        }


if __name__ == "__main__":
    engine = ZeroTrustEngine()

    print("=== mTLS Service-to-Service Verification ===")
    calls = [
        ("api-gateway",         "nl2sql",             True),
        ("api-gateway",         "storytelling",       True),
        ("nl2sql",              "spanner-alloydb",    True),
        ("nl2sql",              "mlops",              False),   # not allowed
        ("streaming-analytics", "vertex-agent",       False),  # not allowed
        ("observability",       "cost-intelligence",  True),   # SRE observes all
    ]
    for caller, callee, expected in calls:
        h = engine.verify_mtls(caller, callee)
        icon = "✅" if h.authorized else "⛔"
        print(f"  {icon} {caller:25} → {callee:25} | authorized={h.authorized} | {h.latency_ms}ms")

    print("\n=== Threat Detection & SOAR Response ===")
    engine.detect_threat(ThreatCategory.DATA_EXFILTRATION, ThreatSeverity.CRITICAL,
                         "t-bank-001", "nl2sql",
                         "Tenant scanned 52GB BigQuery in 8 minutes — anomalous data pull",
                         {"bytes_scanned": 52_400_000_000, "duration_min": 8, "ip": "185.220.101.42"})
    engine.detect_threat(ThreatCategory.IMPOSSIBLE_TRAVEL, ThreatSeverity.CRITICAL,
                         "t-retail-002", "api-gateway",
                         "API key used from DE and CN within 3 minutes — impossible travel",
                         {"country_a": "DE", "country_b": "CN", "gap_minutes": 3})
    engine.detect_threat(ThreatCategory.PRIVILEGE_ESCALATION, ThreatSeverity.CRITICAL,
                         None, "swarm-orchestrator",
                         "IAM rolebinding created outside Terraform — roles/owner binding detected",
                         {"binding": "roles/owner", "principal": "user@external.com"})

    print("\n=== SCC Vulnerability Scan ===")
    vulns = engine.vulnerability_scan()
    for v in vulns:
        print(f"  [{v['severity']}] {v['resource']}: {v['description'][:70]}")
        print(f"    Fix: {v['fix']}")

    print("\n=== Security Posture Dashboard ===")
    print(json.dumps(engine.security_posture_dashboard(), indent=2))
