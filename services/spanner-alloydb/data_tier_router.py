# services/spanner-alloydb/data_tier_router.py
"""
Epic 77: Cloud Spanner + AlloyDB — Global Data Architecture
Intelligent data tier router that automatically routes operations to the
correct storage layer based on query type, consistency requirements, and
performance characteristics.

Data Triad:
  Cloud Spanner  → OLTP transactions (banking, healthcare, inventory)
                   Global strong consistency, external consistency
                   Multi-region: nam-eur-asia1 (3 continents)
                   Use for: writes, point reads, single-row transactions

  AlloyDB        → Operational analytics (fast aggregations on recent data)
                   PostgreSQL-compatible, 4× faster than Aurora
                   pgvector enabled for embedding similarity search
                   Use for: last-30d analytics, JOINs, reporting queries

  BigQuery        → Historical intelligence (data warehousing, ML training)
                   Petabyte-scale columnar analytics
                   Use for: historical trends, ML feature engineering,
                             scheduled reports, cross-tenant aggregations

Routing decision:
  1. Is it a WRITE or requires strong consistency? → Spanner
  2. Is it a READ on recent data (<= 30 days) or requires Postgres compat? → AlloyDB
  3. Everything else (historical, large scans, ML) → BigQuery
"""
import logging, time, uuid, json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class StorageTier(str, Enum):
    SPANNER  = "CLOUD_SPANNER"
    ALLOYDB  = "ALLOYDB"
    BIGQUERY = "BIGQUERY"

class OperationType(str, Enum):
    WRITE             = "WRITE"
    POINT_READ        = "POINT_READ"       # single-row lookup
    RANGE_READ        = "RANGE_READ"       # scan with filter
    AGGREGATE_RECENT  = "AGGREGATE_RECENT" # aggregation on recent data
    AGGREGATE_HIST    = "AGGREGATE_HIST"   # historical aggregation
    VECTOR_SEARCH     = "VECTOR_SEARCH"    # embedding similarity
    ANALYTICS_REPORT  = "ANALYTICS_REPORT" # large scan / reporting
    ML_TRAINING       = "ML_TRAINING"      # feature engineering

@dataclass
class QueryContext:
    operation:     OperationType
    table:         str
    filters:       dict = field(default_factory=dict)
    requires_consistency: bool = False   # needs external consistency guarantee
    data_age_days: int = 0               # how old is the data we're querying
    row_estimate:  int = 0               # estimated result set size
    tenant_id:     str = ""
    locale:        str = "en-US"

@dataclass
class RoutingDecision:
    tier:          StorageTier
    rationale:     str
    query_plan:    str           # translated query for the target tier
    sla_ms:        int           # expected latency SLO in ms
    consistency:   str           # "STRONG" | "READ_YOUR_WRITES" | "EVENTUAL"
    cost_estimate: str           # "LOW" | "MEDIUM" | "HIGH"

@dataclass
class SpannerTransaction:
    tx_id:     str
    tenant_id: str
    table:     str
    operation: str               # "INSERT" | "UPDATE" | "DELETE"
    mutations: list[dict]
    committed_at: Optional[float] = None
    commit_ts:    Optional[str]   = None   # Spanner commit timestamp

@dataclass
class AlloyDBQuery:
    query_id:  str
    sql:       str
    params:    dict
    result_rows: list[dict]
    latency_ms:  float
    plan_rows:   int             # query planner estimated rows

class DataTierRouter:
    """
    Routes all platform data operations to the optimal storage tier.
    Abstracts Spanner / AlloyDB / BigQuery behind a single unified API.
    """
    # Routing table: operation → tier mapping with rationale
    _ROUTING_TABLE = {
        OperationType.WRITE:            (StorageTier.SPANNER,  "STRONG",           50,   "LOW",    "All writes go to Spanner for external consistency guarantee across regions"),
        OperationType.POINT_READ:       (StorageTier.SPANNER,  "STRONG",           10,   "LOW",    "Single-row reads use Spanner strong reads for consistency after writes"),
        OperationType.RANGE_READ:       (StorageTier.ALLOYDB,  "READ_YOUR_WRITES", 25,   "LOW",    "Range reads routed to AlloyDB read pool for PostgreSQL compatibility and speed"),
        OperationType.AGGREGATE_RECENT: (StorageTier.ALLOYDB,  "EVENTUAL",         80,   "MEDIUM", "Recent aggregations (<=30d) in AlloyDB — 4× faster than PostgreSQL for OLAP"),
        OperationType.AGGREGATE_HIST:   (StorageTier.BIGQUERY, "EVENTUAL",         2000, "LOW",    "Historical aggregations in BigQuery — petabyte-scale columnar at lowest cost"),
        OperationType.VECTOR_SEARCH:    (StorageTier.ALLOYDB,  "EVENTUAL",         40,   "MEDIUM", "pgvector in AlloyDB handles embedding similarity queries natively"),
        OperationType.ANALYTICS_REPORT: (StorageTier.BIGQUERY, "EVENTUAL",         5000, "LOW",    "Large scan reports run in BigQuery using slot reservations — cost-efficient"),
        OperationType.ML_TRAINING:      (StorageTier.BIGQUERY, "EVENTUAL",         30000,"LOW",    "ML feature engineering and training data export run entirely in BigQuery"),
    }

    def __init__(self, project_id: str = "alti-analytics-prod",
                 spanner_instance: str = "alti-prod-spanner",
                 alloydb_host: str = "10.0.8.3",   # AlloyDB primary private IP
                 bq_dataset: str = "alti_analytics_prod"):
        self.project_id       = project_id
        self.spanner_instance = spanner_instance
        self.alloydb_host     = alloydb_host
        self.bq_dataset       = bq_dataset
        self.logger   = logging.getLogger("DataTier_Router")
        logging.basicConfig(level=logging.INFO)
        self._tx_log: list[SpannerTransaction]   = []
        self._queries:list[AlloyDBQuery]         = []
        self.logger.info(f"🗄️  Data Tier Router initialized | Spanner={spanner_instance} | AlloyDB={alloydb_host} | BQ={bq_dataset}")

    def route(self, ctx: QueryContext) -> RoutingDecision:
        """Determines the best storage tier for this operation."""
        op = ctx.operation
        # Override: if data is >30 days old and not a write, push to BigQuery
        if op in (OperationType.RANGE_READ, OperationType.AGGREGATE_RECENT) and ctx.data_age_days > 30:
            op = OperationType.AGGREGATE_HIST

        # Override: large result sets always go to BigQuery
        if ctx.row_estimate > 100_000 and op not in (OperationType.WRITE, OperationType.POINT_READ):
            op = OperationType.ANALYTICS_REPORT

        tier, consistency, sla_ms, cost, rationale = self._ROUTING_TABLE[op]
        query_plan = self._translate_query(ctx, tier)

        decision = RoutingDecision(tier=tier, rationale=rationale,
                                   query_plan=query_plan, sla_ms=sla_ms,
                                   consistency=consistency, cost_estimate=cost)
        self.logger.info(f"  🔀 Route: {ctx.operation} on {ctx.table} → {tier} ({consistency}, {sla_ms}ms SLO)")
        return decision

    def _translate_query(self, ctx: QueryContext, tier: StorageTier) -> str:
        """Generates tier-appropriate SQL/GQL for the routed query."""
        table = ctx.table
        if tier == StorageTier.SPANNER:
            # Spanner SQL (ANSI SQL with Spanner extensions)
            mutations = ", ".join(f"{k} = @{k}" for k in ctx.filters)
            return f"-- Spanner SQL\nUPDATE {table} SET {mutations or 'UpdatedAt = PENDING_COMMIT_TIMESTAMP()'} WHERE TenantId = @TenantId"
        elif tier == StorageTier.ALLOYDB:
            # Standard PostgreSQL (AlloyDB is fully PG-compatible)
            where = " AND ".join(f"{k} = ${i+1}" for i, k in enumerate(ctx.filters)) or "TRUE"
            return f"-- AlloyDB (PostgreSQL)\nSELECT * FROM {table.lower().replace('.','_')} WHERE {where} LIMIT 1000"
        else:
            # BigQuery Standard SQL
            bq_table = f"`{self.project_id}.{self.bq_dataset}.{table.replace('.','_')}`"
            return f"-- BigQuery Standard SQL\nSELECT * FROM {bq_table} WHERE tenant_id = @tenant_id LIMIT 10000"

    # ── Spanner operations ─────────────────────────────────────────────────────
    def spanner_write(self, tenant_id: str, table: str,
                      mutations: list[dict], operation: str = "INSERT") -> SpannerTransaction:
        """
        Writes to Cloud Spanner. In production: google.cloud.spanner_v1.Client.
        Returns the commit timestamp for read-your-writes consistency.
        """
        tx = SpannerTransaction(tx_id=str(uuid.uuid4()), tenant_id=tenant_id,
                                table=table, operation=operation,
                                mutations=mutations)
        # Simulate Spanner commit with commit timestamp
        simulated_latency = 0.022  # 22ms typical Spanner single-region write
        time.sleep(0)              # no actual sleep in simulation
        tx.committed_at = time.time()
        tx.commit_ts    = f"2026-03-05T{time.strftime('%H:%M:%S')}Z"
        self._tx_log.append(tx)
        self.logger.info(f"  ✍️  Spanner WRITE: {table} | {len(mutations)} mutations | tx={tx.tx_id[:12]} | ts={tx.commit_ts}")
        return tx

    def spanner_read(self, tenant_id: str, table: str,
                     key: dict, columns: list[str] = None) -> dict:
        """Strong read from Cloud Spanner. Using provided key for direct lookup."""
        self.logger.info(f"  👀 Spanner READ: {table} | key={key}")
        # Simulated result
        return {"TenantId": tenant_id, "Status": "ACTIVE", "UpdatedAt": time.time(), **key}

    # ── AlloyDB operations ─────────────────────────────────────────────────────
    def alloydb_query(self, sql: str, params: dict = None) -> AlloyDBQuery:
        """
        Executes on AlloyDB (read pool). In production: asyncpg / psycopg2 connection pool.
        AlloyDB is the operational analytics engine — fast JOINs on recent data.
        """
        params = params or {}
        # Simulate query execution
        row_count = 42 + hash(sql) % 200
        latency   = round(15 + len(sql) * 0.1, 1)
        rows      = [{"id": str(i), "value": round(i * 1.23, 2)} for i in range(min(row_count, 5))]
        result    = AlloyDBQuery(query_id=str(uuid.uuid4()), sql=sql,
                                 params=params, result_rows=rows,
                                 latency_ms=latency, plan_rows=row_count)
        self._queries.append(result)
        self.logger.info(f"  🐘 AlloyDB query: {latency}ms | {row_count} rows | {sql[:60]}...")
        return result

    def alloydb_vector_search(self, embedding: list[float], table: str,
                              embedding_col: str = "embedding",
                              top_k: int = 10) -> list[dict]:
        """
        pgvector ANN search on AlloyDB.
        In production: SELECT ... ORDER BY embedding_col <=> $1 LIMIT k
        Used for: semantic doc search, similar customer finding, anomaly clustering.
        """
        self.logger.info(f"  🔍 pgvector search: {table}.{embedding_col} top-{top_k}")
        return [{"id": str(uuid.uuid4()), "distance": round(0.12 + i * 0.04, 4),
                 "similarity": round(0.98 - i * 0.04, 4), "rank": i + 1}
                for i in range(top_k)]

    # ── Unified query API ────────────────────────────────────────────────────
    def execute(self, ctx: QueryContext, sql: str = None,
                mutations: list[dict] = None) -> dict:
        """
        Unified execution API. Routes automatically, executes on the right tier.
        """
        decision = self.route(ctx)
        result   = {"tier": decision.tier, "consistency": decision.consistency,
                    "sla_ms": decision.sla_ms, "query_plan": decision.query_plan}

        if decision.tier == StorageTier.SPANNER:
            if ctx.operation == OperationType.WRITE:
                tx = self.spanner_write(ctx.tenant_id, ctx.table, mutations or [])
                result["commit_timestamp"] = tx.commit_ts
                result["tx_id"] = tx.tx_id
            else:
                row = self.spanner_read(ctx.tenant_id, ctx.table, ctx.filters)
                result["row"] = row
        elif decision.tier == StorageTier.ALLOYDB:
            qr = self.alloydb_query(sql or decision.query_plan, ctx.filters)
            result["rows"] = qr.result_rows
            result["latency_ms"] = qr.latency_ms
        else:
            result["bq_job"] = f"bq-job-{uuid.uuid4().hex[:12]}"
            result["estimated_bytes"] = ctx.row_estimate * 100
            result["message"] = "BigQuery job submitted asynchronously"

        return result

    def tier_stats(self) -> dict:
        return {
            "spanner_transactions": len(self._tx_log),
            "spanner_tables":       list({t.table for t in self._tx_log}),
            "alloydb_queries":      len(self._queries),
            "alloydb_avg_latency":  round(sum(q.latency_ms for q in self._queries) / max(1, len(self._queries)), 1),
        }


if __name__ == "__main__":
    router = DataTierRouter()
    print("=== Data Tier Routing Decisions ===\n")
    scenarios = [
        # Write → Spanner
        QueryContext(OperationType.WRITE,            "BankAccounts",   {"AccountId":"acct-001"}, True,  0,   1,      "t-bank"),
        # Point read → Spanner
        QueryContext(OperationType.POINT_READ,        "Transactions",   {"TransactionId":"tx-99"},True, 0,   1,      "t-bank"),
        # Recent aggregation → AlloyDB
        QueryContext(OperationType.AGGREGATE_RECENT,  "salesforce.customers", {}, False, 7,   5_000,  "t-saas"),
        # Historical → BigQuery
        QueryContext(OperationType.AGGREGATE_HIST,    "alti_raw.events", {}, False,    180, 10_000_000, "t-saas"),
        # Vector search → AlloyDB pgvector
        QueryContext(OperationType.VECTOR_SEARCH,     "document_embeddings", {}, False, 0, 10, "t-media"),
        # Large report → BigQuery
        QueryContext(OperationType.ANALYTICS_REPORT,  "alti_analytics.monthly_summary", {}, False, 365, 500_000, "t-bank"),
    ]
    for ctx in scenarios:
        decision = router.route(ctx)
        print(f"  {ctx.operation:25} | {ctx.table:30} | → {decision.tier:15} [{decision.consistency:20}] {decision.sla_ms:>6}ms | {decision.cost_estimate}")
        print(f"    ↳ {decision.rationale[:100]}")

    print("\n=== Spanner Write (Banking Ledger) ===")
    tx = router.spanner_write("t-bank", "Transactions", [
        {"TransactionId": "tx-001", "AccountId": "acct-42", "Amount": 500000, "Type": "DEBIT", "Status": "PENDING"}
    ])
    print(f"  Committed at: {tx.commit_ts} | tx_id: {tx.tx_id[:12]}")

    print("\n=== AlloyDB Operational Query ===")
    qr = router.alloydb_query("SELECT region, SUM(revenue) FROM sales WHERE created_at > NOW() - INTERVAL '30 days' GROUP BY region ORDER BY SUM(revenue) DESC")
    print(f"  Latency: {qr.latency_ms}ms | Rows: {qr.plan_rows}")

    print("\n=== pgvector Embedding Search ===")
    hits = router.alloydb_vector_search([0.1]*384, "document_embeddings", top_k=5)
    for h in hits:
        print(f"  Rank {h['rank']}: distance={h['distance']} similarity={h['similarity']}")

    print(f"\n=== Tier Stats ===")
    print(json.dumps(router.tier_stats(), indent=2))
