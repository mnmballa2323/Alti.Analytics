# API Reference — Alti Analytics Platform

> **OpenAPI 3.1 Specification** | Base URL: `https://api.alti.ai` | Auth: Bearer token (API key) | Sandbox: `https://sandbox.alti.ai`

All requests require:
```http
Authorization: Bearer alti_live_YOUR_KEY
X-Tenant-Id: t-your-tenant-id
X-Locale: en-US
Content-Type: application/json
```

---

## Table of Contents

| Tag | Endpoints | Description |
|---|---|---|
| [NL2SQL](#nl2sql) | 4 | Natural language to SQL query |
| [Analytics](#analytics) | 3 | AI-grounded analytics answers |
| [Streaming](#streaming) | 2 | Real-time event streaming |
| [Currency](#currency) | 3 | FX rates and currency intelligence |
| [Compliance](#compliance) | 3 | Regulatory assessment |
| [Datasets](#datasets) | 3 | Data catalog and lineage |
| [Anomalies](#anomalies) | 3 | Anomaly detection and alerts |
| [Tenants](#tenants) | 3 | Tenant management |
| [Metrics](#metrics) | 3 | Semantic layer canonical metrics |
| [RAG](#rag-documents) | 4 | Document ingestion and retrieval |
| [Dashboards](#dashboards) | 3 | Generative BI dashboards |
| [Customer360](#customer-360) | 3 | Identity resolution and CDP |
| [Webhooks](#webhooks) | 3 | Webhook subscriptions |

---

## NL2SQL

### POST /api/nl2sql/query
Execute a natural-language query against your data.

**Request**
```json
{
  "query":        "Top 10 customers by ARR this quarter",
  "locale":       "en-US",
  "database":     "analytics",
  "context":      { "fiscal_year_start": "April" },
  "stream":       false,
  "explain":      true
}
```

**Response** `200 OK`
```json
{
  "query_id":    "qry-a1b2c3d4",
  "sql":         "SELECT customer_name, SUM(monthly_amount * 12) AS arr FROM subscriptions WHERE ...",
  "result":      [ { "customer_name": "Meridian Bank", "arr": 4200000 } ],
  "row_count":   10,
  "execution_ms": 340,
  "model_version":"nl2sql-v3.2",
  "locale":      "en-US",
  "explanation": "I joined the subscriptions table on customer_id and summed monthly_amount * 12 to get ARR, filtering to the current fiscal quarter.",
  "corrections_rlhf_url": "/api/nl2sql/correct/qry-a1b2c3d4"
}
```

**Errors**
| Status | Code | Meaning |
|---|---|---|
| 400 | `INVALID_QUERY` | Query could not be parsed |
| 403 | `FORBIDDEN_TABLE` | Access to requested table denied by ABAC policy |
| 422 | `SCHEMA_NOT_FOUND` | Referenced table/column does not exist |
| 429 | `RATE_LIMITED` | Tier rate limit exceeded |

---

### POST /api/nl2sql/query (streaming)
Same as above with `"stream": true`. Returns SSE stream:

```
Content-Type: text/event-stream

event: sql
data: {"sql": "SELECT customer_name, SUM..."}

event: row
data: {"customer_name": "Meridian Bank", "arr": 4200000}

event: row
data: {"customer_name": "St. Grace Hospital", "arr": 1800000}

event: done
data: {"row_count": 10, "execution_ms": 312}
```

---

### POST /api/nl2sql/correct
Submit a correction to improve the RLHF model.

**Request**
```json
{
  "query_id":     "qry-a1b2c3d4",
  "correct_sql":  "SELECT customer_name, SUM(arr_amount) FROM arr_snapshots WHERE ...",
  "correction_note": "ARR should come from arr_snapshots, not subscriptions table",
  "user_id":      "user-007"
}
```

**Response** `200 OK`
```json
{
  "correction_id": "cor-9f8e7d6c",
  "status":        "RECORDED",
  "model_id":      "nl2sql-v3.2",
  "corrections_til_finetune": 23
}
```

---

### GET /api/nl2sql/history
Returns the last 50 queries for the tenant.

```
GET /api/nl2sql/history?limit=20&from=2026-01-01
```

**Response** `200 OK`
```json
{
  "queries": [
    { "query_id": "qry-...", "query": "Top 10...", "executed_at": "2026-03-05T18:42:00Z", "row_count": 10 }
  ],
  "total": 1842
}
```

---

## Analytics

### POST /api/analytics/ask
AI-grounded answer to a business question, with citations.

**Request**
```json
{
  "question":   "What caused the churn spike in EMEA last month?",
  "agent_type": "ANALYTICS",
  "use_internet_grounding": true,
  "max_citations": 5
}
```

**Response** `200 OK`
```json
{
  "answer": "The EMEA churn rate increased from 2.1% to 4.9% in February 2026, driven primarily by three enterprise clients citing competitor pricing as the exit reason (42% of churned ARR). The spike correlates with a competitor product launch announcement on Feb 12. Affected CSM: Sarah Chen (3 accounts). Recommended action: executive-level retention outreach with competitive pricing analysis.",
  "citations": [
    { "title": "Internal CRM: Churn Records Feb 2026", "uri": "internal://crm/churn" },
    { "title": "TechCrunch: CompetitorX raises $200M", "uri": "https://techcrunch.com/..." }
  ],
  "confidence": 0.91,
  "agent_type": "ANALYTICS",
  "latency_ms": 2840
}
```

---

### POST /api/analytics/scenario
Run a scenario simulation.

**Request**
```json
{
  "scenario": "What happens to ARR if we reduce churn by 2% in EMEA?",
  "simulation_periods": 12,
  "currency": "USD"
}
```

---

### GET /api/analytics/brief
Request an AI-generated executive brief for the current period.

```
GET /api/analytics/brief?period=week&audience=CEO&locale=en-US
```

---

## Streaming

### POST /api/streaming/subscribe
Subscribe to a real-time event stream (SSE or WebSocket).

**Request**
```json
{
  "event_types": ["ANOMALY", "FRAUD_SIGNAL", "DATA_QUALITY", "SLO_BREACH"],
  "filters":     { "severity": ["HIGH","CRITICAL"], "region": "EMEA" }
}
```

**Response**: Returns a `stream_token` for connecting to `wss://stream.alti.ai/v1/events?token=`.

---

### GET /api/streaming/events
Returns recent events (REST polling alternative to streaming).

```
GET /api/streaming/events?type=ANOMALY&limit=20&since=2026-03-05T00:00:00Z
```

---

## Currency

### GET /api/currency/rate
Get the current FX rate between two currencies.

```
GET /api/currency/rate?from=USD&to=JPY
```

**Response** `200 OK`
```json
{
  "from":       "USD",
  "to":         "JPY",
  "rate":       149.83,
  "bid":        149.79,
  "ask":        149.87,
  "source":     "Reuters",
  "timestamp":  "2026-03-05T20:56:00Z",
  "cached_seconds": 5
}
```

---

### POST /api/currency/convert
Convert an amount with multi-currency consolidation.

**Request**
```json
{
  "amount": 1000000,
  "from":   "EUR",
  "to":     "USD",
  "date":   "2026-03-05"
}
```

---

### GET /api/currency/exposure
Get FX exposure analysis for the tenant across all currencies.

```
GET /api/currency/exposure?reporting_currency=USD
```

---

## Compliance

### POST /api/compliance/assess
Run a regulatory compliance assessment.

**Request**
```json
{
  "jurisdiction": "EU",
  "data_subjects": ["EU_residents"],
  "processing_purposes": ["analytics", "model_training"],
  "data_categories": ["personal_data", "financial_data"]
}
```

**Response** `200 OK`
```json
{
  "compliant":       false,
  "regulations":     ["GDPR", "EU_AI_ACT"],
  "violations":      [{ "article": "6", "description": "No valid lawful basis documented for model_training" }],
  "required_actions":["Document lawful basis", "Implement consent records"],
  "risk_score":      7.2
}
```

---

### GET /api/compliance/jurisdictions
Returns all supported jurisdictions and applicable regulations.

---

### POST /api/compliance/dsr
Process a Data Subject Request (erasure, portability, access).

**Request**
```json
{
  "request_type": "erasure",
  "subject_id":   "user-12345",
  "jurisdiction": "EU"
}
```

---

## Datasets

### GET /api/datasets
List all datasets in the tenant's data catalog.

```
GET /api/datasets?department=finance&classification=INTERNAL
```

---

### GET /api/datasets/{dataset_id}/lineage
Returns the full data lineage graph for a dataset.

```
GET /api/datasets/ds-001/lineage
```

**Response** `200 OK`
```json
{
  "dataset_id": "ds-001",
  "name": "salesforce.customers",
  "lineage": {
    "upstream":   [{ "id": "ds-src-001", "name": "Salesforce CRM raw export" }],
    "downstream": [{ "id": "ds-002", "name": "customer_360.unified" }, { "id": "ds-003", "name": "churn_model.features" }]
  }
}
```

---

### POST /api/datasets/{dataset_id}/validate
Run data quality checks on a dataset.

---

## Anomalies

### GET /api/anomalies
Returns recent anomalies detected by the platform.

```
GET /api/anomalies?severity=HIGH,CRITICAL&limit=50
```

---

### GET /api/anomalies/{anomaly_id}
Get detailed analysis for a specific anomaly.

---

### POST /api/anomalies/{anomaly_id}/acknowledge
Acknowledge and dismiss an anomaly.

---

## Tenants

### POST /api/tenants
Provision a new tenant (requires `roles/alti.admin`).

**Request**
```json
{
  "org_name":   "Meridian Bank",
  "tier":       "ENTERPRISE",
  "region":     "us-central1",
  "industry":   "banking",
  "admins":     ["admin@meridian.com"]
}
```

---

### GET /api/tenants/{tenant_id}
Get tenant details, usage, and billing.

---

### PUT /api/tenants/{tenant_id}
Update tenant configuration.

---

## Metrics

### GET /api/metrics
List all canonical metrics in the semantic layer.

---

### GET /api/metrics/{metric_id}
Get the current value of a canonical metric.

```
GET /api/metrics/arr?grain=monthly&date_range=last_quarter
```

**Response** `200 OK`
```json
{
  "metric_id":    "arr",
  "display_name": "Annual Recurring Revenue",
  "value":        48241000,
  "unit":         "$",
  "grain":        "monthly",
  "date_range":   "last_quarter",
  "sql":          "SELECT SUM(monthly_amount * 12) FROM subscriptions WHERE ...",
  "source":       "subscriptions",
  "certified_by": "Finance Team",
  "last_updated": "2026-03-05T00:00:00Z"
}
```

---

### POST /api/metrics/validate
Check that a metric resolves consistently across all access paths.

---

## RAG Documents

### POST /api/rag/ingest
Ingest a document into the RAG corpus.

**Request**
```json
{
  "source_uri":     "gs://my-bucket/annual-report-2025.pdf",
  "doc_type":       "PDF",
  "title":          "Annual Report 2025",
  "department":     "finance",
  "classification": "CONFIDENTIAL",
  "language":       "en-US"
}
```

**Response** `202 Accepted`
```json
{
  "doc_id":    "doc-a1b2c3d4",
  "status":    "INGESTING",
  "chunks_est": 847
}
```

---

### POST /api/rag/query
Query the document corpus with RAG.

**Request**
```json
{
  "query":   "What were the material weaknesses in our Q3 2025 Basel III report?",
  "top_k":   50,
  "rerank":  true,
  "filters": { "department": "compliance", "doc_date_after": "2025-01-01" }
}
```

**Response** `200 OK`
```json
{
  "answer":     "The Q3 2025 Basel III report identified two material weaknesses: ...",
  "citations":  [{ "doc_title": "Basel III Q3 2025", "section": "Risk Disclosures", "page": 34 }],
  "confidence": 0.94,
  "chunks_retrieved": 47,
  "model_used": "gemini-1.5-pro",
  "latency_ms": 842
}
```

---

### GET /api/rag/documents
List documents in the corpus.

---

### DELETE /api/rag/documents/{doc_id}
Remove a document from the corpus (also removes all chunks and embeddings).

---

## Dashboards

### POST /api/dashboards/generate
Generate a dashboard from a natural-language description.

**Request**
```json
{
  "prompt": "CFO dashboard: ARR waterfall, NRR trend vs last year, CAC by channel as donut. Schedule Monday 8am to cfo@company.com",
  "audience": "BOARD"
}
```

**Response** `200 OK`
```json
{
  "dashboard_id": "dash-abc123",
  "title":        "Arr & Nrr Executive Overview",
  "widgets":      [ { "id": "w-001", "chart_type": "METRIC_CARD", "metric_id": "arr", "size": "small" } ],
  "share_token":  "tok-xyz789",
  "scheduled_delivery": { "cron": "0 8 * * 1", "format": "PDF" }
}
```

---

### GET /api/dashboards/{dashboard_id}
Get dashboard schema.

---

### GET /api/dashboards/{dashboard_id}/export
Export dashboard as PDF or PNG.

```
GET /api/dashboards/dash-abc123/export?format=PDF
```

---

## Customer 360

### POST /api/customer360/resolve
Resolve identity across multiple data sources.

**Request**
```json
{
  "sources": {
    "crm":      { "name": "Jennifer Whitmore", "email": "j.whitmore@bank.com" },
    "payments": { "name": "J. Whitmore", "card_last4": "4291" },
    "support":  { "email": "j.whitmore@bank.com", "phone": "+1-617-555-0192" }
  }
}
```

**Response** `200 OK`
```json
{
  "identity_id":    "id-abc12345",
  "canonical_name": "Jennifer Whitmore",
  "canonical_email":"j.whitmore@bank.com",
  "confidence":     0.987,
  "signals":        3,
  "sources_matched":["crm","payments","support"]
}
```

---

### GET /api/customer360/{identity_id}
Get the full Customer 360 profile.

---

### GET /api/customer360/{identity_id}/journey
Get the customer journey event sequence.

---

## Webhooks

### POST /api/webhooks/subscribe
Create a webhook subscription.

**Request**
```json
{
  "url":    "https://hooks.myapp.com/alti",
  "events": ["anomaly.detected", "fraud.flagged", "slo.breach"],
  "secret": "my-webhook-signing-secret"
}
```

**Response** `201 Created`
```json
{
  "subscription_id": "sub-001",
  "url":             "https://hooks.myapp.com/alti",
  "events":          ["anomaly.detected", "fraud.flagged", "slo.breach"],
  "created_at":      "2026-03-05T20:56:00Z"
}
```

Webhook payloads are signed with HMAC-SHA256. Verify signatures:

```python
import hmac, hashlib
signature = request.headers.get("X-Alti-Signature")
expected  = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
assert hmac.compare_digest(signature, f"sha256={expected}")
```

---

### GET /api/webhooks/subscriptions
List all active subscriptions.

---

### DELETE /api/webhooks/subscriptions/{subscription_id}
Delete a webhook subscription.

---

## Rate Limits

| Tier | Requests/min | Requests/day |
|---|---|---|
| Starter | 60 | 10,000 |
| Growth | 300 | 50,000 |
| Professional | 1,000 | 200,000 |
| Enterprise | 5,000 | Unlimited |

Rate limit headers returned on every response:
```
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 287
X-RateLimit-Reset: 1741211760
```

## Error Format

All errors follow RFC 7807 Problem Details:

```json
{
  "type":     "https://api.alti.ai/errors/rate-limited",
  "title":    "Too Many Requests",
  "status":   429,
  "detail":   "You have exceeded the 300 req/min limit for the Growth tier.",
  "instance": "/api/nl2sql/query",
  "retry_after": 12
}
```
