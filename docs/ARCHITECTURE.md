# Architecture Guide — Alti Analytics Platform

## Table of Contents
1. [System Overview](#system-overview)
2. [Service Mesh & Communication](#service-mesh--communication)
3. [Data Architecture](#data-architecture)
4. [AI & ML Architecture](#ai--ml-architecture)
5. [Security Architecture](#security-architecture)
6. [Observability Architecture](#observability-architecture)
7. [Multi-Tenancy Model](#multi-tenancy-model)
8. [Global Deployment](#global-deployment)
9. [Service Dependency Map](#service-dependency-map)

---

## System Overview

Alti Analytics is built as a **cloud-native microservices platform** on Google Cloud Platform. Every component is stateless, containerized in Cloud Run, and communicates over mTLS-secured service mesh with SPIFFE identities.

### Design Principles

| Principle | Implementation |
|---|---|
| **Stateless services** | All state in Cloud Spanner, AlloyDB, or BigQuery — never in-process |
| **Zero-trust networking** | Every service-to-service call verified by SPIFFE SVID + mTLS |
| **Data sovereignty** | Per-tenant data isolation with VPC Service Controls + CMEK |
| **Least privilege** | Separate service accounts per Cloud Run service, minimal IAM bindings |
| **Declarative IaC** | All infrastructure in Terraform, no manual GCP console changes |
| **Canary-first deploys** | 5% traffic split, SLO validation, auto-rollback on breach |

---

## Service Mesh & Communication

### mTLS with SPIFFE Identity

Every service registers a SPIFFE Verifiable Identity Document (SVID) with 24-hour rotation:

```
spiffe://alti.ai/service/nl2sql
spiffe://alti.ai/service/streaming-analytics
spiffe://alti.ai/service/ai-governance
... (24 services total)
```

Traffic Director enforces the service mesh allow-list. Any unauthorized call:
1. Is rejected with a 401 at the sidecar
2. Fires a `LATERAL_MOVEMENT` threat event to the ZeroTrustEngine
3. Triggers an automated SOAR playbook response within 60 seconds

### Synchronous vs. Async Patterns

| Pattern | Technology | Used For |
|---|---|---|
| Sync REST | HTTPS/2 over mTLS | Real-time queries (NL2SQL, analytics) |
| Async tasks | Cloud Tasks | Tenant provisioning, report generation |
| Event streaming | Pub/Sub | Anomaly events, audit log ingestion |
| Scheduled | Cloud Scheduler | Autonomous briefings, SLO sweeps |
| Streaming results | Server-Sent Events | NL2SQL streaming, narrative generation |

---

## Data Architecture

### Data Tier Router Decision Tree

```
Incoming Operation
├── WRITE (any table) → Cloud Spanner (global ACID transactions)
├── STRONG READ (financial, compliance) → Cloud Spanner
├── RECENT ANALYTICS (< 7 days) → AlloyDB (OLAP-optimized)
├── VECTOR SEARCH (semantic similarity) → AlloyDB + pgvector
├── HISTORICAL DATA (> 7 days) → BigQuery (petabyte-scale)
├── ML TRAINING → BigQuery (exports to Vertex AI)
└── CACHE / RATE LIMITS → Memorystore Redis
```

### BigQuery Datasets

| Dataset | Purpose | Retention |
|---|---|---|
| `alti_raw` | Raw ingested events | 2 years |
| `alti_analytics` | Aggregated metrics | 5 years |
| `alti_ml` | ML training data | 3 years |
| `alti_compliance` | Audit logs, consent records | 7 years (regulatory) |
| `alti_rag` | Document chunks + embeddings | Indefinite |
| `alti_tenant_{id}` | Per-tenant isolated dataset | Per-tenant SLA |

### Cloud Spanner Schema (Key Tables)

```sql
-- Multi-tenancy: every table partitioned by tenant_id
CREATE TABLE tenants (
  tenant_id STRING(36) NOT NULL,
  org_name  STRING(256),
  tier      STRING(32),   -- STARTER|GROWTH|ENTERPRISE|CUSTOM
  region    STRING(64),
  created_at TIMESTAMP,
) PRIMARY KEY (tenant_id);

-- Banking: interleaved with tenants for locality
CREATE TABLE BankAccounts (
  tenant_id    STRING(36) NOT NULL,
  account_id   STRING(36) NOT NULL,
  customer_id  STRING(36) NOT NULL,
  balance_units INT64,     -- stored in minor currency units
  currency_code STRING(3),
  last_updated  TIMESTAMP OPTIONS (allow_commit_timestamp = true),
) PRIMARY KEY (tenant_id, account_id),
  INTERLEAVE IN PARENT tenants ON DELETE CASCADE;

-- Healthcare (similar interleaving for patients, admissions)
-- Sports (matches, players, seasons)
-- Inventory (products, warehouses, movements)
```

### AlloyDB Configuration

- **pgvector** extension for 768-dim semantic vector storage
- Primary instance: 16 vCPU, 128GB RAM (production)
- Read pool: 2 nodes, auto-scaled to 8
- Used for: operational analytics, customer 360 queries, vector similarity search

---

## AI & ML Architecture

### Agent Swarm (551+ Agents)

The swarm is organized into **6 tiers**:

| Tier | Agents | Examples |
|---|---|---|
| **Orchestration** | 4 | Master Orchestrator, Router, Consensus Engine |
| **Analytics** | 80+ | NL2SQL, Storytelling, Causal AI, Anomaly Detection |
| **Industry** | 120+ | Banking (40), Healthcare (32), Sports (24), Manufacturing (28) |
| **Data** | 60+ | Catalog, Lineage, Quality, Schema Evolution |
| **Compliance** | 40+ | GDPR, HIPAA, PDPA, Basel III, EU AI Act |
| **Infrastructure** | 20+ | SRE, Cost Optimization, Security |

### Vertex AI Integration

| Vertex AI Service | Usage |
|---|---|
| **Agent Builder** | Grounded answers with Google Search + enterprise data stores |
| **Gemini 1.5 Pro** | Long-context RAG synthesis (1M token context window) |
| **text-embedding-004** | 768-dim document embeddings for RAG vector search |
| **Explainable AI** | SHAP feature attributions for every regulated model prediction |
| **Vector Search** | ANN retrieval over 1B+ document chunk embeddings |
| **Workbench** | Data scientist notebooks with T4 GPU |
| **Pipelines** | RLHF fine-tuning job orchestration |

### RLHF Continuous Learning Pipeline

```
User corrects NL2SQL output
        │
        ▼
correction stored to BigQuery (alti_rl.corrections)
        │
        ▼ (daily batch at 02:00 UTC)
corrections aggregated into fine-tuning dataset
correction count ≥ 50 for model?
        │ YES
        ▼
Vertex AI fine-tuning job launched
        │
        ▼
New model evaluated on holdout set
AUC improves > 0.5%?
        │ YES              │ NO
        ▼                  ▼
Promote to STAGING    Discard, continue
SLO validation (k6)   accumulating corrections
        │ PASS
        ▼
Promote to PRODUCTION
```

---

## Security Architecture

### Zero-Trust Layers

```
Internet Request
    │
    ▼
Cloud Armor WAF (OWASP rules, rate limiting, DDoS protection)
    │
    ▼
API Gateway (JWT validation, API key verification, tenant resolution)
    │
    ▼
mTLS Service Mesh (Traffic Director, SPIFFE/SPIRE)
    │
    ▼ (per service)
ABAC Policy Engine (role + dept + clearance + data classification)
    │
    ▼ (per column)
Dynamic Data Masking (CLEAR|MASKED|HASHED|REDACTED|NULL per role)
    │
    ▼
Data Layer (Spanner / AlloyDB / BigQuery with CMEK)
```

### ABAC Decision Matrix

| Subject Role | PHI Data | PII Data | Financial | Aggregate |
|---|---|---|---|---|
| `doctor`, `nurse` | CLEAR | CLEAR | REDACTED | CLEAR |
| `billing` | REDACTED | MASKED | CLEAR | CLEAR |
| `analyst` | NULL | HASHED | MASKED | CLEAR |
| `engineer` | NULL | HASHED | HASHED | MASKED |
| `compliance` | MASKED | MASKED | CLEAR | CLEAR |
| `admin` | MASKED | CLEAR | CLEAR | CLEAR |

### EU AI Act Risk Classification

| Use Case | Risk Class | Obligations |
|---|---|---|
| Credit Scoring | HIGH_RISK | Art. 9/10/13/14/15/43/61 |
| Fraud Detection | HIGH_RISK | Art. 9/10/13/14/15/43/61 |
| Patient Readmission | HIGH_RISK | Art. 9/10/13/14/15/43/61 |
| Hiring Screening | HIGH_RISK | Art. 9/10/13/14/15/43/61 |
| Customer Churn | LIMITED_RISK | Transparency only |
| Demand Forecasting | MINIMAL_RISK | None |
| Social Scoring | UNACCEPTABLE | **PROHIBITED — blocked** |
| Facial Recognition | UNACCEPTABLE | **PROHIBITED — blocked** |

---

## Observability Architecture

### SLO Portfolio (24 Services)

Every service has a defined SLO contract:

| Service | Availability SLO | Latency SLO (p99) | Error Budget |
|---|---|---|---|
| `nl2sql` | 99.9% | < 2,000ms | 43.8 min/month |
| `streaming-analytics` | 99.95% | < 200ms | 21.9 min/month |
| `currency-intelligence` | 99.95% | < 100ms | 21.9 min/month |
| `ai-governance` | 99.9% | < 500ms | 43.8 min/month |
| All others | 99.9% | < 1,000ms | 43.8 min/month |

### Error Budget Burn Rate Escalation

| Burn Rate | Budget Consumed | Action |
|---|---|---|
| < 2x | < 10% | No action |
| 2–5x | 10–30% | Slack `#sre-alerts` notification |
| 5–10x | 30–60% | PagerDuty page, deployment freeze |
| > 10x | > 60% | P1 incident, executive notification |

### Distributed Tracing

Every request carries a W3C `traceparent` header propagated through all 24 services. A typical NL2SQL trace looks like:

```
api-gateway [12ms]
  └─ auth-service [8ms]
       └─ nl2sql [820ms]
            ├─ spanner-alloydb [94ms]   (schema fetch)
            └─ vertex-ai [680ms]        (model call)
  └─ storytelling [340ms]
       └─ nl2sql (cache hit) [12ms]
```

---

## Multi-Tenancy Model

### Isolation Levels

| Resource | Isolation Model |
|---|---|
| BigQuery | Per-tenant dataset (`alti_tenant_{id}`) with row-level security |
| Spanner | Row-level: every table includes `tenant_id` partition key |
| AlloyDB | Row Security Policy enforced on all queries |
| Cloud Storage | Per-tenant CMEK bucket |
| Secret Manager | Per-tenant secret namespace |
| Pub/Sub | Per-tenant topic prefix |
| API keys | Tenant-scoped, rate-limited per tier |

### Pricing Tiers

| Tier | Price/month | Users | BQ | AI Tokens | SLA |
|---|---|---|---|---|---|
| Starter | $299 | 5 | 1 TB | 100K | 99.5% |
| Growth | $999 | 25 | 5 TB | 500K | 99.9% |
| Professional | $2,499 | 100 | 20 TB | 2M | 99.9% |
| Enterprise | $4,999 | Unlimited | 100 TB | 10M | 99.95% |
| Custom | Negotiated | Unlimited | Unlimited | Unlimited | 99.99% |

---

## Global Deployment

### Supported Regions

| Region | Cloud Spanner | AlloyDB | BigQuery | Data Sovereignty |
|---|---|---|---|---|
| `us-central1` | ✅ | ✅ | ✅ US multi-region | US data never leaves US |
| `europe-west1` | ✅ | ✅ | ✅ EU multi-region | EU data never leaves EU (GDPR) |
| `asia-southeast1` | ✅ | ✅ | ✅ APAC | PDPA compliant (SG) |
| `northamerica-northeast1` | ✅ | ✅ | ✅ CA | PIPEDA compliant |
| `me-central1` | ✅ | planned | ✅ | ME data sovereignty |

### Language Support (NL2SQL + All AI)

50 languages supported natively with regional fine-tuned models:

Arabic, Bengali, Chinese (Simplified/Traditional), Czech, Danish, Dutch, English, Finnish, French, German, Greek, Hebrew, Hindi, Hungarian, Indonesian, Italian, Japanese, Korean, Malay, Norwegian, Persian, Polish, Portuguese (BR/PT), Romanian, Russian, Spanish, Swahili, Swedish, Thai, Turkish, Ukrainian, Urdu, Vietnamese, and 16 additional languages.

---

## Service Dependency Map

```
                    ┌─────────────────┐
                    │   API Gateway   │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
    ┌─────▼─────┐    ┌──────▼──────┐   ┌──────▼──────┐
    │  nl2sql   │    │  vertex-    │   │  streaming  │
    │           │    │  agent      │   │  analytics  │
    └─────┬─────┘    └──────┬──────┘   └──────┬──────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                    ┌────────▼────────┐
                    │  data-tier-     │
                    │  router         │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────┐
         │                   │               │
   ┌─────▼─────┐    ┌────────▼──────┐ ┌─────▼──────┐
   │  Cloud    │    │   AlloyDB     │ │  BigQuery  │
   │  Spanner  │    │  + pgvector   │ │            │
   └───────────┘    └───────────────┘ └────────────┘
```

For the complete dependency graph, see [docs/service-dependencies.json](service-dependencies.json).
