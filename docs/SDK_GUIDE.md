# SDK Guide — Python & TypeScript SDKs

> Official SDK documentation for the Alti Analytics Platform.

---

## Python SDK

### Installation
```bash
pip install alti-sdk
# With optional extras:
pip install "alti-sdk[pandas]"    # pandas DataFrame results
pip install "alti-sdk[streaming]" # SSE streaming support
```

### Quick Start
```python
import asyncio
from alti_sdk import AltiClient

async def main():
    async with AltiClient(
        api_key="alti_live_your_key_here",
        tenant_id="t-your-tenant",
        locale="en-US",
    ) as client:
        # Natural language query
        result = await client.nl2sql.query("Top 10 customers by ARR this quarter")
        for row in result.result:
            print(row)

asyncio.run(main())
```

---

### Configuration

```python
from alti_sdk import AltiClient, AltiConfig

client = AltiClient(
    api_key="alti_live_...",       # Required. Set ALTI_API_KEY env var instead.
    tenant_id="t-bank",            # Required. Set ALTI_TENANT_ID env var instead.
    locale="en-US",                # Default: "en-US". Supports 50 languages.
    base_url="https://api.alti.ai",# Override for custom deployments.
    timeout=30.0,                  # Request timeout in seconds.
    max_retries=3,                 # Retry on 429/502/503 with exponential backoff.
    retry_backoff=2.0,             # Base multiplier for exponential backoff (seconds).
)
```

Environment variables (takes precedence over constructor):
```bash
export ALTI_API_KEY="alti_live_your_key"
export ALTI_TENANT_ID="t-your-tenant"
export ALTI_LOCALE="en-US"
```

---

### NL2SQL

```python
# Simple query
result = await client.nl2sql.query("Monthly ARR by region for last 6 months")
print(result.sql)           # Generated SQL
print(result.result)        # List of dicts
print(result.explanation)   # AI explanation of the SQL

# With options
result = await client.nl2sql.query(
    query="ARR by region",
    locale="fr-FR",          # Query in French
    database="analytics",
    explain=True,
    context={"fiscal_start_month": "April"}
)

# Streaming results (large datasets)
async for row in client.nl2sql.stream("SELECT * FROM large_table LIMIT 100000"):
    process(row)

# Submit a correction (RLHF)
await client.nl2sql.correct(
    query_id=result.query_id,
    correct_sql="SELECT ... FROM correct_table ...",
    note="Should use arr_snapshots, not subscriptions"
)

# Convert result to pandas DataFrame
import pandas as pd
result = await client.nl2sql.query("Sales by product")
df = result.to_dataframe()   # requires pip install "alti-sdk[pandas]"
print(df.describe())
```

---

### Analytics (Grounded AI)

```python
# Ask a business question
answer = await client.analytics.ask(
    question="What caused the EMEA churn spike in February?",
    use_internet_grounding=True,
    max_citations=5
)
print(answer.answer)
for citation in answer.citations:
    print(f"  [{citation['title']}] {citation['uri']}")

# Run a scenario simulation
scenario = await client.analytics.scenario(
    "What happens to ARR over 12 months if we reduce churn by 2% in EMEA?"
)
print(scenario.summary)
print(scenario.projections)  # month-by-month projections

# Get executive brief
brief = await client.analytics.brief(period="week", audience="CEO")
print(brief.narrative)
```

---

### Currency & FX

```python
# Get exchange rate
rate = await client.currency.rate("USD", "JPY")
print(f"1 USD = {rate.rate:.2f} JPY")

# Convert amount
converted = await client.currency.convert(1_000_000, from_="EUR", to="USD")
print(f"€1M = ${converted.result:,.2f}")

# Multi-currency exposure
exposure = await client.currency.exposure(reporting_currency="USD")
for ccy, amount in exposure.exposures.items():
    print(f"  {ccy}: ${amount:,.0f}")
```

---

### RAG Document Queries

```python
# Query documents
response = await client.rag.query(
    "What were the material weaknesses in our Q3 2025 Basel III report?",
    top_k=50,
    rerank=True,
    filters={"department": "compliance"}
)
print(response.answer)
for cite in response.citations:
    print(f"  [{cite['doc_title']}] page {cite['page']}")

# Ingest a document
doc = await client.rag.ingest(
    source_uri="gs://my-bucket/contract.pdf",
    doc_type="PDF",
    title="Master Service Agreement 2025",
    department="legal",
    classification="CONFIDENTIAL"
)
print(f"Ingested: {doc.doc_id} ({doc.chunks_est} chunks)")

# List corpus
docs = await client.rag.list_documents(department="finance")
print(f"{len(docs)} documents in finance corpus")
```

---

### Generative BI

```python
# Generate a dashboard from a description
dashboard = await client.dashboards.generate(
    prompt=(
        "CFO dashboard: ARR waterfall, NRR trend vs last year, "
        "CAC by channel as donut, LTV by tier treemap. "
        "Schedule Monday 8am to cfo@company.com."
    ),
    audience="BOARD"
)
print(f"Dashboard: {dashboard.title}")
for widget in dashboard.widgets:
    print(f"  {widget.title} [{widget.chart_type}] — {widget.insight}")

# Export as PDF
pdf_bytes = await client.dashboards.export(dashboard.dashboard_id, format="PDF")
with open("report.pdf", "wb") as f:
    f.write(pdf_bytes)
```

---

### Customer 360

```python
# Resolve identity across sources
identity = await client.customer360.resolve({
    "crm":      {"name": "Jennifer Whitmore", "email": "j.whitmore@bank.com"},
    "payments": {"name": "J. Whitmore", "card_last4": "4291"},
    "support":  {"email": "j.whitmore@bank.com"}
})
print(f"Identity: {identity.canonical_name} (confidence: {identity.confidence:.1%})")

# Get full C360 profile
profile = await client.customer360.get(identity.identity_id)
print(f"ARR: ${profile.crm.arr:,.0f} | Health: {profile.crm.health}")
print(f"Journey: {profile.ai_insights.journey_stage}")
print(f"Next Action: {profile.ai_insights.next_best_action}")
print(f"Churn probability: {profile.ai_insights.churn_probability:.0%}")
```

---

### Webhooks

```python
# Subscribe to events
sub = await client.webhooks.subscribe(
    url="https://hooks.myapp.com/alti",
    events=["anomaly.detected", "fraud.flagged", "slo.breach"],
    secret="my-signing-secret"
)
print(f"Subscription: {sub.subscription_id}")

# In your webhook handler, verify signature:
from alti_sdk import WebhookVerifier

verifier = WebhookVerifier(secret="my-signing-secret")
payload = verifier.verify(
    body=request.body,
    signature=request.headers["X-Alti-Signature"]
)
# payload is the decoded event dict if valid, raises InvalidSignatureError if not
```

---

### Error Handling

```python
from alti_sdk.exceptions import (
    AltiAuthError,        # 401 - Invalid API key
    AltiPermissionError,  # 403 - ABAC policy denied access
    AltiRateLimitError,   # 429 - Rate limit exceeded (includes retry_after)
    AltiNotFoundError,    # 404 - Resource not found
    AltiServerError,      # 5xx - Server error
    AltiTimeoutError,     # Request timed out
)

try:
    result = await client.nl2sql.query("ARR by region")
except AltiPermissionError as e:
    print(f"Access denied: {e.detail}")
    # Column masked or table access denied by ABAC
except AltiRateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except AltiServerError as e:
    print(f"Server error {e.status}: {e.message}")
```

---

## TypeScript / JavaScript SDK

### Installation
```bash
npm install @alti/sdk
# or
yarn add @alti/sdk
```

### Quick Start
```typescript
import { AltiClient } from '@alti/sdk';

const client = new AltiClient({
  apiKey:   'alti_live_your_key_here',
  tenantId: 't-your-tenant',
  locale:   'en-US',
});

// Natural language query
const result = await client.nl2sql.query('Top 10 customers by ARR this quarter');
console.log(result.sql);
console.log(result.result);

// AI grounded answer
const answer = await client.analytics.ask(
  'What caused the EMEA churn spike in February?'
);
console.log(answer.answer);
answer.citations.forEach(c => console.log(`  [${c.title}]`));
```

---

### NL2SQL
```typescript
// With options
const result = await client.nl2sql.query('ARR by region', {
  locale:  'de-DE',         // In German
  explain: true,
});

// Streaming
const stream = client.nl2sql.stream('Monthly customer breakdown');
for await (const row of stream) {
  console.log(row);
}

// Submit correction
await client.nl2sql.correct({
  queryId:    result.queryId,
  correctSql: 'SELECT ... FROM arr_snapshots ...',
  note:       'Use arr_snapshots table, not subscriptions',
});
```

---

### RAG Queries
```typescript
const response = await client.rag.query(
  'Summarize all material EU AI Act obligations from our compliance documents',
  {
    topK:    50,
    rerank:  true,
    filters: { department: 'legal' },
  }
);
console.log(response.answer);
response.citations.forEach(c =>
  console.log(`  [${c.docTitle}] page ${c.page}`)
);
```

---

### Webhooks (In-Server Handler)
```typescript
import express from 'express';
import { WebhookVerifier } from '@alti/sdk';

const app = express();
const verifier = new WebhookVerifier({ secret: 'my-signing-secret' });

app.post('/hooks/alti', express.raw({ type: 'application/json' }), (req, res) => {
  const sig = req.headers['x-alti-signature'] as string;

  const event = verifier.verify(req.body, sig);
  // Will throw InvalidSignatureError if signature invalid

  console.log(`Event: ${event.type}`, event.payload);

  switch (event.type) {
    case 'anomaly.detected':
      handleAnomaly(event.payload);
      break;
    case 'fraud.flagged':
      handleFraud(event.payload);
      break;
  }
  res.status(200).json({ received: true });
});
```

---

### Embedded Analytics (Browser SDK)
```html
<!-- Load from CDN -->
<script src="https://cdn.alti.ai/embed/v30.js"></script>

<script>
AltiEmbed.init({
  apiKey:   'alti_live_your_key',
  tenantId: 't-your-tenant',
  locale:   'en-US',
  theme: {
    colorPrimary:    '#003087',  // Your brand primary
    colorBackground: '#f8fafc',  // Light mode
    colorText:       '#1e293b',
    fontFamily:      "'Roboto', sans-serif",
  }
});

// React to events
document.querySelector('alti-query-bar')
  .addEventListener('alti:result', e => {
    console.log('Query result:', e.detail);
  });
</script>

<!-- Components (work in React, Vue, or plain HTML) -->
<alti-dashboard cols="3">
  <alti-metric-card metric="arr"          locale="en-US"></alti-metric-card>
  <alti-metric-card metric="churn_rate"   locale="en-US"></alti-metric-card>
  <alti-metric-card metric="nrr"          locale="en-US"></alti-metric-card>
</alti-dashboard>

<alti-query-bar placeholder="Ask about your data..."></alti-query-bar>
<alti-anomaly-feed></alti-anomaly-feed>
<alti-narrative question="Summarize this week's business performance"></alti-narrative>
```

---

## SDK Changelog

| Version | Date | Changes |
|---|---|---|
| `3.0.0` | 2026-03-05 | Added `rag`, `dashboards`, `customer360` modules |
| `2.9.0` | 2026-02-06 | Added RLHF `nl2sql.correct()`, webhook signature verification |
| `2.8.0` | 2026-01-10 | Multi-currency support, FX streaming |
| `2.7.0` | 2025-12-15 | Knowledge graph, scenario engine |
| `2.0.0` | 2025-11-01 | Python SDK async rewrite, TypeScript SDK launch |
| `1.0.0` | 2025-09-01 | Initial SDK release |
