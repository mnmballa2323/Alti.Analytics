# Data Architecture Guide — Alti Analytics Platform

> The data tier is the backbone of the platform. Every service reads/writes through the data tier router, which selects the optimal storage engine per operation.

---

## Data Tier Router Decision Logic

```
Operation Type?
├── WRITE (any data) ──────────────────► Cloud Spanner
│     └─ ACID transactions, strong consistency, globally distributed
│
├── STRONG READ (financial, compliance)► Cloud Spanner
│     └─ TrueTime-bounded reads, no staleness
│
├── ANALYTICS READ (last 7 days) ──────► AlloyDB
│     └─ Columnar engine, pgvector, OLAP-optimized joins
│
├── VECTOR / SEMANTIC SEARCH ──────────► AlloyDB (pgvector) + Vertex AI Vector Search
│     └─ 768-dim cosine similarity on embeddings
│
├── HISTORICAL DATA (> 7 days) ────────► BigQuery
│     └─ Petabyte-scale, serverless SQL, columnar storage
│
├── ML TRAINING DATA ──────────────────► BigQuery
│     └─ Exported to GCS → Vertex AI Pipelines
│
└── CACHE / RATE LIMITS ───────────────► Memorystore Redis
      └─ TTL-based, pub/sub for real-time events
```

---

## Cloud Spanner

### Instance Configuration

| Setting | Value |
|---|---|
| Instance | `alti-prod` |
| Configuration | `regional-us-central1` (multi-region: `nam6` for prod) |
| Processing Units | 1,000 (1 node) baseline, auto-scale to 10,000 |
| Databases | `alti-main`, `alti-banking`, `alti-healthcare`, `alti-sports`, `alti-tenant-meta` |

### Key Schema Patterns

**Multi-tenant isolation via partition key:**
```sql
-- Every table has tenant_id as first primary key component
CREATE TABLE subscriptions (
  tenant_id        STRING(36) NOT NULL,
  subscription_id  STRING(36) NOT NULL,
  customer_id      STRING(36) NOT NULL,
  monthly_amount   FLOAT64,
  currency_code    STRING(3),
  status           STRING(32),  -- ACTIVE|CANCELLED|PAUSED
  start_date       DATE,
  updated_at       TIMESTAMP OPTIONS (allow_commit_timestamp = true),
) PRIMARY KEY (tenant_id, subscription_id);
```

**Interleaved tables for locality:**
```sql
-- BankAccounts interleaved in Customers → co-located on same Spanner node
CREATE TABLE BankAccounts (
  tenant_id    STRING(36) NOT NULL,
  customer_id  STRING(36) NOT NULL,
  account_id   STRING(36) NOT NULL,
  ...
) PRIMARY KEY (tenant_id, customer_id, account_id),
  INTERLEAVE IN PARENT Customers ON DELETE CASCADE;
```

**Change streams for audit:**
```sql
-- Capture all writes to financial tables for audit log
CREATE CHANGE STREAM FinancialAuditStream
FOR BankAccounts, Transactions, Loans
OPTIONS (value_capture_type = 'NEW_ROW');
```

---

## AlloyDB

### Cluster Configuration

| Setting | Value |
|---|---|
| Cluster | `alti-prod` |
| Region | `us-central1` |
| Primary | 16 vCPU, 128 GB RAM |
| Read Pool | 2 nodes (auto-scale to 8) |
| Storage | 2 TB, auto-grow |
| PostgreSQL Version | 15 |
| Extensions | `pgvector`, `pg_trgm`, `uuid-ossp`, `pg_stat_statements` |

### pgvector for Semantic Search

```sql
-- Create vector column for customer embeddings
ALTER TABLE customers
ADD COLUMN embedding vector(768);  -- 768-dim Vertex AI text-embedding-004

-- HNSW index for fast ANN search
CREATE INDEX ON customers USING hnsw (embedding vector_cosine_ops)
WITH (m=16, ef_construction=200);

-- Semantic customer search
SELECT
  customer_id, customer_name,
  1 - (embedding <=> query_vector) AS similarity
FROM customers
WHERE tenant_id = $1
ORDER BY embedding <=> query_vector
LIMIT 20;
```

### Row-Level Security

```sql
-- Every query automatically filtered to tenant
CREATE POLICY tenant_isolation ON customers
  USING (tenant_id = current_setting('app.tenant_id'));

ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
-- All queries now automatically scoped: no cross-tenant leaks possible
```

---

## BigQuery

### Dataset Organization

| Dataset | Tables | Purpose | Retention |
|---|---|---|---|
| `alti_raw` | 12 | Raw ingested events (append-only) | 2 years |
| `alti_analytics` | 28 | Aggregated metrics, daily snapshots | 5 years |
| `alti_ml` | 15 | Feature tables, label tables, training exports | 3 years |
| `alti_compliance` | 8 | Audit logs, consent records, DSAR records | 7 years |
| `alti_rag` | 3 | Document chunks, embeddings, retrieval stats | Indefinite |
| `alti_tenant_{id}` | Varies | Per-tenant isolated analytics | Per SLA |

### Partitioning & Clustering

All large tables:
- **Partitioned** by `event_date` (DATE) — query only scans needed partitions
- **Clustered** by `tenant_id, event_type` — co-located data for common filters

```sql
CREATE TABLE alti_raw.events
PARTITION BY DATE(event_timestamp)
CLUSTER BY tenant_id, event_type
OPTIONS(
  require_partition_filter = TRUE,    -- Prevents full table scans
  partition_expiration_days = 730     -- 2-year retention
)
AS SELECT ...
```

### Row-Level Security (Column Masking)

```sql
-- Finance analysts see masked customer PII
CREATE ROW ACCESS POLICY finance_data_policy
ON alti_analytics.customer_metrics
GRANT TO ("group:finance@company.com")
FILTER USING (classification IN ('PUBLIC','INTERNAL'));
```

---

## Memorystore (Redis)

### Usage Patterns

| Use Case | TTL | Key Pattern |
|---|---|---|
| API rate limit counters | 60s | `rl:{tenant_id}:{api_key}:{minute}` |
| NL2SQL result cache | 300s | `cache:nl2sql:{query_hash}:{locale}` |
| FX rate cache | 5s | `fx:{from}:{to}` |
| Tenant config cache | 3600s | `tenant:{tenant_id}:config` |
| Session tokens | 86400s | `session:{token_hash}` |
| Pub/Sub: anomaly events | — | Channel: `anomalies:{tenant_id}` |

---

## Semantic Layer (Canonical Metrics)

### The Problem

Without a semantic layer, every team writes their own SQL for the same metric:

```sql
-- Finance team's ARR query
SELECT SUM(annual_contract_value) FROM deals WHERE status='closed'

-- Engineering dashboard's ARR query
SELECT SUM(monthly_amount * 12) FROM subscriptions WHERE active=true

-- Executive report's ARR query
SELECT SUM(arr_amount) FROM arr_snapshots WHERE snapshot_date = LAST_DAY(...)

-- All three return DIFFERENT NUMBERS for "ARR"
```

### The Solution: One Canonical Definition

```python
# In semantic_layer.py
METRICS = {
    "arr": {
        "display_name": "Annual Recurring Revenue",
        "aliases": ["Annual Recurring Revenue", "ARR", "yearly revenue", "annual revenue"],
        "sql": """
            SELECT SUM(monthly_amount * 12)
            FROM `{project}.alti_tenant_{tenant_id}.subscriptions`
            WHERE status = 'ACTIVE'
              AND DATE(period_start) <= CURRENT_DATE()
              AND (DATE(period_end) >= CURRENT_DATE() OR period_end IS NULL)
        """,
        "unit": "$",
        "grain": "monthly",
        "certified_by": "Finance Team",
        "industries": ["saas","banking","healthcare","sports","retail"]
    }
}
```

Now every access path — NL2SQL, SDK, embedded analytics, Generative BI — uses **identical SQL** for ARR. No more discrepancies.

### 10 Canonical Metrics

| Metric ID | Display Name | Industries | SQL Source |
|---|---|---|---|
| `arr` | Annual Recurring Revenue | saas, banking | `subscriptions` |
| `nrr` | Net Revenue Retention | saas | `subscriptions` cohort |
| `churn_rate` | Customer Churn Rate | saas, banking | `subscriptions` |
| `ltv` | Customer Lifetime Value | all | `subscriptions + costs` |
| `cac` | Customer Acquisition Cost | all | `marketing_costs + revenue` |
| `dau` | Daily Active Users | digital | `user_sessions` |
| `nps` | Net Promoter Score | all | `nps_responses` |
| `readmission_rate` | 30-Day Readmission Rate | healthcare | `patient_admissions` |
| `hcahps` | Patient Satisfaction Score | healthcare | `hcahps_surveys` |
| `win_pct` | Win Percentage | sports | `match_results` |

---

## Data Lineage

Every dataset in the platform has a full lineage graph:

```
[Raw Source: Salesforce CRM]
    │ Dataflow pipeline (hourly)
    ▼
[alti_raw.crm_events]
    │ dbt transformation (daily)
    ▼
[alti_analytics.customer_metrics]
    ├── [churn_model.features]  → Vertex AI training
    ├── [customer_360.unified]  → Customer 360 API
    └── [arr metric SQL]        → Semantic layer
```

Lineage is tracked in the data catalog and surfaced in the Data Explorer UI.

---

## Data Quality Gates

Every dataset has automated quality checks that run after each pipeline execution:

| Check Type | Example | Action if Fails |
|---|---|---|
| `not_null` | `customer_id IS NOT NULL` | Pipeline halted, alert fired |
| `unique` | No duplicate `subscription_id` | Alert, quarantine duplicates |
| `accepted_values` | `status IN ('ACTIVE','CANCELLED','PAUSED')` | Alert, log violations |
| `referential_integrity` | `customer_id` exists in `customers` | Alert, orphan records quarantined |
| `freshness` | `MAX(created_at) > NOW() - INTERVAL 25 HOUR` | Alert if data is stale |
| `volume` | Row count within 3σ of trailing 30-day average | Alert on unexpected drop/spike |

Quality checks run via Cloud Composer (Airflow) and results are stored in `alti_analytics.data_quality_results`.
