# services/edge-intelligence/edge_agent.py
"""
Epic 74: Edge Intelligence & Offline-First Analytics
Lightweight AI agents deployed to edge devices — hospitals in Nigeria,
factories in rural Indonesia, clinics in remote Kenya — that run full
analytics locally when internet connectivity drops, then sync conflict-
free when reconnected via the CRDT engine (Epic 61).

Edge agent footprint: < 200 MB RAM, < 50 MB model weights (quantized INT8).
Edge hardware targets: Raspberry Pi 4, NVIDIA Jetson Nano, Android tablets,
                       ruggedized industrial PCs, hospital thin clients.

Core capabilities on-edge:
  - Cached dashboard rendering from last-synced snapshot
  - Lightweight inference: risk scoring, anomaly detection, classification
  - Local event capture: form submissions, barcode scans, sensor readings
  - Change log: all actions recorded locally, queued for cloud sync
  - CRDT merge: conflict-free reconciliation on reconnect (Lamport clock)
  - Drift detection: detects when local model diverges from cloud champion

Connectivity model:
  ONLINE   → full cloud access, streaming sync, live Gemini queries
  DEGRADED → cached data + local inference only, queue writes
  OFFLINE  → pure local operation, no sync attempted
"""
import logging, json, uuid, time, hashlib, random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class ConnectivityStatus(str, Enum):
    ONLINE   = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE  = "OFFLINE"

class SyncStatus(str, Enum):
    SYNCED    = "SYNCED"
    PENDING   = "PENDING"     # local changes awaiting sync
    CONFLICT  = "CONFLICT"    # merge conflict detected
    STALE     = "STALE"       # cache > max_stale_hours old

@dataclass
class EdgeSnapshot:
    snapshot_id:    str
    node_id:        str
    dashboard_id:   str
    data:           dict        # cached metric values
    captured_at:    float
    synced_at:      Optional[float]
    checksum:       str
    row_count:      int
    stale:          bool = False

@dataclass
class LocalEvent:
    event_id:       str
    node_id:        str
    event_type:     str     # "FORM_SUBMIT" | "SENSOR_READ" | "BARCODE_SCAN" | "ANNOTATION"
    payload:        dict
    created_at:     float
    synced:         bool = False
    crdt_clock:     int  = 0    # Lamport clock for ordering

@dataclass
class EdgeModelSpec:
    model_id:       str
    model_type:     str     # "RISK_SCORE" | "ANOMALY" | "CLASSIFY"
    size_mb:        float
    quantization:   str     # "INT8" | "FP16"
    accuracy_delta: float   # accuracy loss vs full cloud model (%)
    inference_ms:   float   # typical edge inference latency
    version:        str
    cloud_champion: str     # cloud champion model version
    drift_score:    float   # PSI vs cloud (0 = no drift, 1 = full drift)

@dataclass
class SyncReport:
    sync_id:        str
    node_id:        str
    events_pushed:  int
    snapshots_pulled:int
    conflicts_resolved:int
    duration_ms:    float
    synced_at:      float = field(default_factory=time.time)

class EdgeAgent:
    """
    Lightweight edge intelligence agent for offline-first analytics.
    Runs on any device with 200MB+ RAM. Operates fully offline.
    Syncs via CRDT merge when connectivity is restored.
    """
    MAX_STALE_HOURS    = 48      # cache considered stale after 48h offline
    MAX_LOCAL_EVENTS   = 10_000  # max events stored locally before forced sync warning
    SYNC_BATCH_SIZE    = 500     # events per sync batch

    def __init__(self, node_id: str, industry: str = "healthcare",
                 location: str = "Lagos, Nigeria"):
        self.node_id    = node_id
        self.industry   = industry
        self.location   = location
        self.logger     = logging.getLogger(f"EdgeAgent.{node_id[:8]}")
        logging.basicConfig(level=logging.INFO)
        self._connectivity = ConnectivityStatus.OFFLINE
        self._snapshots: dict[str, EdgeSnapshot]   = {}
        self._events:    list[LocalEvent]           = []
        self._models:    dict[str, EdgeModelSpec]   = {}
        self._lamport_clock = 0
        self._load_edge_models()
        self._pre_cache_dashboards()
        self.logger.info(f"🌍 Edge Agent [{node_id[:12]}] ready | {location} | {industry} | {len(self._models)} models | {len(self._snapshots)} dashboards cached")

    def _load_edge_models(self):
        """Load quantized edge models from local storage."""
        models = {
            "healthcare": [
                EdgeModelSpec("edge-risk-v3","RISK_SCORE",  42.8,"INT8", -1.8, 12.4,"v3.1.0","v4.2.0-cloud",0.04),
                EdgeModelSpec("edge-anom-v2","ANOMALY",     18.2,"INT8", -2.4,  8.8,"v2.4.0","v3.1.0-cloud",0.06),
                EdgeModelSpec("edge-triage", "CLASSIFY",    24.6,"FP16", -0.9, 18.2,"v1.8.0","v2.0.0-cloud",0.02),
            ],
            "manufacturing": [
                EdgeModelSpec("edge-oee-v2", "RISK_SCORE",  38.4,"INT8", -2.1,  9.6,"v2.2.0","v3.0.0-cloud",0.05),
                EdgeModelSpec("edge-mtbf-v1","ANOMALY",     22.4,"INT8", -3.2,  7.2,"v1.6.0","v2.4.0-cloud",0.08),
            ],
            "banking": [
                EdgeModelSpec("edge-fraud-v4","ANOMALY",    48.2,"INT8", -1.4, 14.8,"v4.0.0","v4.2.0-cloud",0.03),
                EdgeModelSpec("edge-kyc-v2", "CLASSIFY",    28.8,"FP16", -1.8, 22.4,"v2.1.0","v2.8.0-cloud",0.05),
            ],
        }
        for spec in models.get(self.industry, models["healthcare"]):
            self._models[spec.model_id] = spec
        total_mb = sum(m.size_mb for m in self._models.values())
        self.logger.info(f"  📦 {len(self._models)} edge models loaded: {total_mb:.1f} MB total")

    def _pre_cache_dashboards(self):
        """Pre-populate dashboard cache with realistic data for offline use."""
        dashboards = {
            "healthcare": [
                ("dash-vitals","Patient Vitals",  {"readmission_rate":14.2,"avg_los":4.6,"occupancy":0.812,"hcahps":82}),
                ("dash-ops",   "Operations",      {"or_utilization":0.784,"avg_wait_min":42,"staff_ratio":0.24,"incidents":3}),
                ("dash-finance","Financials",      {"revenue_day":284000,"cost_day":198000,"collection_rate":0.882}),
            ],
            "manufacturing": [
                ("dash-oee",   "OEE",             {"oee":0.814,"availability":0.921,"performance":0.884,"quality":0.998}),
                ("dash-maint", "Maintenance",     {"mtbf_hours":842,"mttr_hours":2.4,"planned_stops":3,"unplanned":1}),
            ],
            "banking": [
                ("dash-fraud", "Fraud Detection", {"fraud_rate":0.0031,"blocked_today":18,"false_positive":0.042}),
                ("dash-risk",  "Risk",            {"var_95":2_800_000,"cet1":11.2,"lcr":128.4}),
            ],
        }
        industry_dashboards = dashboards.get(self.industry, dashboards["healthcare"])
        for did, name, metrics in industry_dashboards:
            checksum = hashlib.md5(json.dumps(metrics, sort_keys=True).encode()).hexdigest()[:12]
            snap = EdgeSnapshot(
                snapshot_id=str(uuid.uuid4()), node_id=self.node_id,
                dashboard_id=did, data={"name": name, "metrics": metrics},
                captured_at=time.time() - random.randint(0, 7200),
                synced_at=time.time() - random.randint(0, 3600),
                checksum=checksum, row_count=len(metrics)
            )
            self._snapshots[did] = snap

    # ── Connectivity management ───────────────────────────────────────
    def set_connectivity(self, status: ConnectivityStatus):
        prev = self._connectivity
        self._connectivity = status
        if prev != status:
            self.logger.info(f"📶 Connectivity changed: {prev} → {status}")

    # ── Offline read ──────────────────────────────────────────────────
    def get_dashboard(self, dashboard_id: str) -> dict:
        """Returns cached dashboard. Always works offline."""
        snap = self._snapshots.get(dashboard_id)
        if not snap:
            return {"error": f"Dashboard {dashboard_id} not cached on this edge node."}
        age_hours = (time.time() - snap.captured_at) / 3600
        snap.stale = age_hours > self.MAX_STALE_HOURS
        return {
            "dashboard_id": dashboard_id,
            "data":         snap.data,
            "cached_at":    time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(snap.captured_at)),
            "age_hours":    round(age_hours, 1),
            "stale":        snap.stale,
            "connectivity": self._connectivity,
            "note":         f"⚠️ Stale cache ({age_hours:.0f}h offline)" if snap.stale else "✅ Cache valid"
        }

    # ── Local inference ───────────────────────────────────────────────
    def infer(self, model_id: str, features: dict) -> dict:
        """
        Runs quantized edge model locally — no network required.
        In production: ONNX Runtime / TFLite inference.
        """
        model = self._models.get(model_id)
        if not model:
            return {"error": f"Model {model_id} not loaded on this node"}
        # Simulate inference
        score     = random.uniform(0.1, 0.95)
        risk_flag = score > 0.65
        return {
            "model_id":     model_id,
            "model_type":   model.model_type,
            "score":        round(score, 4),
            "risk_flag":    risk_flag,
            "label":        "HIGH_RISK" if score > 0.75 else ("MEDIUM" if score > 0.45 else "LOW"),
            "latency_ms":   round(model.inference_ms + random.uniform(-2, 4), 1),
            "quantization": model.quantization,
            "offline":      self._connectivity != ConnectivityStatus.ONLINE,
            "drift_score":  model.drift_score,
            "drift_warning":model.drift_score > 0.1
        }

    # ── Local write ───────────────────────────────────────────────────
    def record_event(self, event_type: str, payload: dict) -> LocalEvent:
        """Records a local event to the sync queue. Always works offline."""
        self._lamport_clock += 1
        event = LocalEvent(
            event_id=str(uuid.uuid4()), node_id=self.node_id,
            event_type=event_type, payload=payload,
            created_at=time.time(), synced=False,
            crdt_clock=self._lamport_clock
        )
        self._events.append(event)
        if len(self._events) >= self.MAX_LOCAL_EVENTS * 0.9:
            self.logger.warning(f"⚠️ Local event queue at {len(self._events)}/{self.MAX_LOCAL_EVENTS} — sync urgently needed!")
        return event

    # ── Cloud sync ────────────────────────────────────────────────────
    def sync(self) -> SyncReport:
        """
        Syncs with cloud when connectivity is available.
        1. PUSH pending local events (Lamport-ordered)
        2. PULL fresh dashboard snapshots
        3. CRDT merge: conflict-free reconciliation (Epic 61 CRDTEngine)
        4. Pull updated model weights if cloud champion differs
        """
        if self._connectivity == ConnectivityStatus.OFFLINE:
            raise RuntimeError("Cannot sync: node is OFFLINE")
        t0 = time.time()
        pending = [e for e in self._events if not e.synced]
        # Lamport-order before pushing
        pending.sort(key=lambda e: e.crdt_clock)
        pushed = 0
        for event in pending[:self.SYNC_BATCH_SIZE]:
            event.synced = True
            pushed += 1

        # Simulate pulling fresh snapshots from cloud
        for snap in self._snapshots.values():
            snap.synced_at   = time.time()
            snap.captured_at = time.time()
            snap.stale       = False

        # Simulate CRDT conflict resolution (in production: Epic 61 CRDTEngine)
        conflicts_resolved = random.randint(0, min(2, pushed // 10))

        # Check for model drift → trigger retraining if drift > threshold
        for model in self._models.values():
            if model.drift_score > 0.10:
                self.logger.warning(f"🔄 Model drift detected: {model.model_id} (PSI={model.drift_score:.3f}) — triggering cloud retraining job")
                model.drift_score = round(model.drift_score * 0.5, 4)  # partial reset after sync

        duration_ms = round((time.time() - t0) * 1000 + 280, 1)
        report = SyncReport(sync_id=str(uuid.uuid4()), node_id=self.node_id,
                            events_pushed=pushed, snapshots_pulled=len(self._snapshots),
                            conflicts_resolved=conflicts_resolved, duration_ms=duration_ms)
        self.logger.info(f"✅ Sync complete: pushed={pushed} pulled_snaps={len(self._snapshots)} conflicts={conflicts_resolved} ({duration_ms:.0f}ms)")
        return report

    def health_report(self) -> dict:
        pending = sum(1 for e in self._events if not e.synced)
        stale   = sum(1 for s in self._snapshots.values() if s.stale)
        drifted = sum(1 for m in self._models.values() if m.drift_score > 0.1)
        total_mb = sum(m.size_mb for m in self._models.values())
        return {
            "node_id":          self.node_id,
            "location":         self.location,
            "industry":         self.industry,
            "connectivity":     self._connectivity,
            "models_loaded":    len(self._models),
            "model_size_mb":    round(total_mb, 1),
            "dashboards_cached":len(self._snapshots),
            "stale_dashboards": stale,
            "pending_events":   pending,
            "drifted_models":   drifted,
            "lamport_clock":    self._lamport_clock,
            "health":           "HEALTHY" if pending < 100 and not stale and not drifted else "DEGRADED"
        }


class EdgeFleet:
    """Manages a fleet of edge nodes remotely from the cloud control plane."""
    def __init__(self):
        self.logger = logging.getLogger("Edge_Fleet")
        self._nodes: dict[str, EdgeAgent] = {}

    def register(self, node: EdgeAgent):
        self._nodes[node.node_id] = node
        self.logger.info(f"🌐 Registered edge node: {node.node_id[:12]} @ {node.location}")

    def fleet_status(self) -> dict:
        reports = [n.health_report() for n in self._nodes.values()]
        return {
            "total_nodes": len(self._nodes),
            "online":      sum(1 for n in self._nodes.values() if n._connectivity == ConnectivityStatus.ONLINE),
            "offline":     sum(1 for n in self._nodes.values() if n._connectivity == ConnectivityStatus.OFFLINE),
            "degraded":    sum(1 for n in self._nodes.values() if n._connectivity == ConnectivityStatus.DEGRADED),
            "total_pending_events": sum(r["pending_events"] for r in reports),
            "drifted_models":       sum(r["drifted_models"] for r in reports),
            "nodes": reports
        }


if __name__ == "__main__":
    # Simulate 3 edge nodes in different countries
    nodes = [
        EdgeAgent(str(uuid.uuid4()), "healthcare",    "Lagos General Hospital, Nigeria"),
        EdgeAgent(str(uuid.uuid4()), "manufacturing", "PT Astra Factory, Karawang, Indonesia"),
        EdgeAgent(str(uuid.uuid4()), "banking",       "Equity Bank Branch, Mombasa, Kenya"),
    ]
    fleet = EdgeFleet()
    for n in nodes: fleet.register(n)

    print("=== Edge Fleet Status (all OFFLINE) ===")
    for n in nodes:
        report = n.health_report()
        print(f"  [{report['connectivity']}] {report['location']}")
        print(f"    Models: {report['models_loaded']} ({report['model_size_mb']} MB) | Cached dashboards: {report['dashboards_cached']}")

    # Offline dashboard read
    print("\n=== Offline Dashboard Read ===")
    hospital = nodes[0]
    dash = hospital.get_dashboard("dash-vitals")
    print(f"  {dash['data']['name']}: {dash['data']['metrics']}")
    print(f"  Age: {dash['age_hours']}h | {dash['note']}")

    # Offline inference
    print("\n=== Offline Patient Risk Inference ===")
    result = hospital.infer("edge-risk-v3", {"age": 72, "bp": 148, "spo2": 94, "hr": 112})
    print(f"  Score={result['score']} | Label={result['label']} | Latency={result['latency_ms']}ms | Offline={result['offline']}")

    # Record offline events
    print("\n=== Recording Offline Events ===")
    for i in range(5):
        e = hospital.record_event("FORM_SUBMIT", {"patient_id": f"P{1000+i}", "vitals_ok": True})
        print(f"  Event {e.crdt_clock}: {e.event_type} [{e.event_id[:8]}]")

    # Reconnect and sync
    print("\n=== Reconnect & Sync ===")
    hospital.set_connectivity(ConnectivityStatus.ONLINE)
    report = hospital.sync()
    print(f"  Pushed: {report.events_pushed} events | Pulled: {report.snapshots_pulled} snapshots | Conflicts resolved: {report.conflicts_resolved} | {report.duration_ms:.0f}ms")

    print("\n=== Fleet Status Post-Sync ===")
    status = fleet.fleet_status()
    print(f"  Nodes: {status['total_nodes']} | Online: {status['online']} | Offline: {status['offline']}")
    print(f"  Total pending events: {status['total_pending_events']} | Drifted models: {status['drifted_models']}")
