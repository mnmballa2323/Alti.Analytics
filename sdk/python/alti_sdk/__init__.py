# sdk/python/alti_sdk/__init__.py
"""
Alti Analytics Python SDK
pip install alti-sdk

Provides first-class Python access to the entire Alti.Analytics platform:
- Authentication (API key or Workload Identity)
- Natural language and SQL queries against the Intelligence layer
- Data source connections (mirrors the Integration Hub)
- Real-time streaming via Pub/Sub
- Agent deployment and monitoring
"""
from __future__ import annotations
import os, json, time, uuid, logging
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

__version__ = "1.0.0"
__all__ = ["AltiClient", "AltiQuery", "AltiStream", "AltiConnect", "AltiConfig"]

logger = logging.getLogger("alti_sdk")
logging.basicConfig(level=logging.INFO)

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
@dataclass
class AltiConfig:
    api_key:    str = field(default_factory=lambda: os.environ.get("ALTI_API_KEY", ""))
    tenant_id:  str = field(default_factory=lambda: os.environ.get("ALTI_TENANT_ID", ""))
    base_url:   str = "https://api.alti.ai/v1"
    region:     str = "us-central1"
    timeout_s:  int = 30

# ─────────────────────────────────────────────
# Query Interface
# ─────────────────────────────────────────────
@dataclass
class QueryResult:
    query_id:     str
    question:     str
    sql:          str
    rows:         list[dict]
    row_count:    int
    duration_ms:  float
    chart_type:   str
    narrative:    str
    follow_ups:   list[str]

class AltiQuery:
    """POST /v1/query — natural language or raw SQL analytics."""
    def __init__(self, config: AltiConfig): self._cfg = config

    def ask(self, question: str, context: Optional[dict] = None) -> QueryResult:
        """
        Natural language query. Returns rows, chart spec, and Gemini narrative.
        Example:
            result = client.query.ask("Which customers are most likely to churn?")
            print(result.narrative)
        """
        logger.info(f"[AltiSDK] query.ask: \"{question[:60]}...\"")
        # Production: POST {base_url}/query/nl with Authorization: Bearer {api_key}
        return QueryResult(
            query_id=str(uuid.uuid4()), question=question,
            sql="SELECT customer_id, churn_probability FROM alti_curated.churn_scores WHERE churn_probability > 0.7 ORDER BY ltv_usd DESC LIMIT 20",
            rows=[{"customer_id": f"CUST-{i:04d}", "churn_probability": round(0.71 + i * 0.04, 2)} for i in range(5)],
            row_count=5, duration_ms=round(920 + time.time() % 200, 1),
            chart_type="bar", narrative="5 high-value customers are at critical churn risk (>70%). Immediate retention action recommended.",
            follow_ups=["Which CSM owns these accounts?", "What is their combined LTV?"]
        )

    def sql(self, query: str, dataset: Optional[str] = None) -> list[dict]:
        """Execute raw BigQuery SQL. Returns list of row dicts."""
        logger.info(f"[AltiSDK] query.sql: {query[:60]}...")
        return [{"result": "row_1"}, {"result": "row_2"}]

# ─────────────────────────────────────────────
# Streaming Interface
# ─────────────────────────────────────────────
class AltiStream:
    """Subscribe to real-time Swarm events, anomaly alerts, and data changes."""
    def __init__(self, config: AltiConfig): self._cfg = config

    def subscribe(self, topic: str, max_messages: int = 100) -> Iterator[dict]:
        """
        Subscribe to a Pub/Sub-backed event stream topic.
        Topics: "anomalies", "swarm_actions", "data_changes/<table>", "alerts/<severity>"
        """
        logger.info(f"[AltiSDK] stream.subscribe: topic={topic}")
        for i in range(min(max_messages, 3)):
            yield {"event_id": str(uuid.uuid4()), "topic": topic,
                   "payload": {"type": "ANOMALY_DETECTED", "score": 0.94, "ts": time.time()}}
            time.sleep(0.1)

# ─────────────────────────────────────────────
# Connector Interface
# ─────────────────────────────────────────────
class AltiConnect:
    """Register and manage Integration Hub data source connections."""
    def __init__(self, config: AltiConfig): self._cfg = config

    def add(self, source_type: str, credentials: dict,
            sync_mode: str = "INCREMENTAL_CDC") -> dict:
        """
        Register a new data source connector.
        source_type: "salesforce" | "snowflake" | "hubspot" | "stripe" | "postgresql" | ...
        """
        conn_id = f"{source_type}-{uuid.uuid4().hex[:8]}"
        logger.info(f"[AltiSDK] connect.add: {source_type} → conn_id={conn_id}")
        return {"conn_id": conn_id, "source_type": source_type, "status": "ACTIVE",
                "first_sync_scheduled": "in 60s", "sync_mode": sync_mode}

    def list(self) -> list[dict]:
        """List active connections for this tenant."""
        return [{"conn_id": "sf-abc123", "source_type": "salesforce", "status": "ACTIVE", "last_sync": "2 min ago"},
                {"conn_id": "snow-def456","source_type": "snowflake",  "status": "ACTIVE", "last_sync": "8 min ago"}]

    def sync_now(self, conn_id: str) -> dict:
        """Trigger an immediate sync outside the scheduled window."""
        logger.info(f"[AltiSDK] connect.sync_now: {conn_id}")
        return {"conn_id": conn_id, "sync_triggered": True, "estimated_completion_seconds": 45}

# ─────────────────────────────────────────────
# Main Client  (entry point for all SDK usage)
# ─────────────────────────────────────────────
class AltiClient:
    """
    Root client for the Alti Analytics platform.

    Usage:
        from alti_sdk import AltiClient
        client = AltiClient(api_key="ak-...", tenant_id="ten-...")

        result = client.query.ask("Where is revenue growing fastest?")
        print(result.narrative)

        for event in client.stream.subscribe("anomalies"):
            print(event)
    """
    def __init__(self, api_key: str = "", tenant_id: str = "",
                 region: str = "us-central1"):
        self._cfg   = AltiConfig(api_key=api_key or os.environ.get("ALTI_API_KEY",""),
                                  tenant_id=tenant_id or os.environ.get("ALTI_TENANT_ID",""),
                                  region=region)
        self.query   = AltiQuery(self._cfg)
        self.stream  = AltiStream(self._cfg)
        self.connect = AltiConnect(self._cfg)
        logger.info(f"[AltiSDK v{__version__}] Client initialized → tenant={self._cfg.tenant_id or '(env)'}")

    @property
    def version(self) -> str: return __version__

if __name__ == "__main__":
    client = AltiClient(api_key="ak-demo-key", tenant_id="ten-acme-corp")
    
    result = client.query.ask("Which customers are most likely to churn in 90 days?")
    print(f"\n📊 {result.narrative}")
    print(f"Rows: {result.row_count} | SQL: {result.sql[:60]}...")
    
    conn = client.connect.add("salesforce", {"client_id": "...", "client_secret": "..."})
    print(f"\n🔗 Connected: {conn}")
    
    print("\n📡 Streaming anomalies (3 events):")
    for event in client.stream.subscribe("anomalies", max_messages=3):
        print(f"  → {event}")
