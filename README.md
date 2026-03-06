# Alti Analytics Platform

> **The world's most comprehensive AI analytics platform.** 30 Phases · 91 Epics · 551+ Specialized AI Agents · Deployed on Google Cloud Platform · Works in any country, any language.

[![GCP](https://img.shields.io/badge/GCP-Deployed-blue?logo=google-cloud)](https://cloud.google.com)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC?logo=terraform)](https://terraform.io)
[![License](https://img.shields.io/badge/License-Apache%202.0-green)](LICENSE)
[![OpenAPI](https://img.shields.io/badge/API-OpenAPI%203.1-85EA2D?logo=swagger)](docs/API_REFERENCE.md)

---

## What is Alti Analytics?

Alti Analytics is an **enterprise-grade, multi-tenant AI analytics platform** that transforms any enterprise's data into natural-language insights, autonomous workflows, and real-time intelligence — across **50 languages**, **10+ industry verticals**, and deployable in **any sovereign jurisdiction** with full regulatory compliance.

### Core Capabilities at a Glance

| Capability | Description |
|---|---|
| 🧠 **NL2SQL** | Ask questions in any of 50 languages, get instant SQL results with explanation |
| 🤖 **551+ AI Agents** | Specialized swarm agents covering every business domain and industry |
| 📊 **Generative BI** | Describe a dashboard in English — platform generates the full layout, charts, and SQL |
| 🔍 **TB-Scale RAG** | Query terabytes of enterprise documents (PDFs, contracts, EHR) with cited answers |
| 🌍 **Global Intelligence** | Operates natively in 50 languages with data sovereignty enforcement |
| 🔐 **Zero-Trust Security** | SPIFFE mTLS, SOAR auto-remediation, ABAC column masking, break-glass PAM |
| ⚖️ **AI Governance** | EU AI Act conformity, SHAP explanations, fairness monitoring, SR 11-7 compliance |
| 👤 **Customer 360 CDP** | Probabilistic identity resolution across CRM, web, payments, support |
| 🪟 **Embedded Analytics** | White-label Web Components drop-in for any web application |
| ⚡ **Autonomous Workflows** | Event-driven agents that investigate, report, act — no human needed |

---

## Quick Start

### Prerequisites
- Google Cloud project with billing enabled
- Terraform ≥ 1.8
- Python ≥ 3.11
- Node.js ≥ 18 (for TypeScript SDK / embedded analytics)
- `gcloud` CLI authenticated

### 1. Clone & Configure
```bash
git clone https://github.com/your-org/Alti.Analytics.git
cd Alti.Analytics

# Copy and configure your environment
cp infra/terraform/environments/prod/terraform.tfvars.example \
   infra/terraform/environments/prod/terraform.tfvars
# Edit terraform.tfvars with your GCP project ID
```

### 2. Deploy Infrastructure
```bash
cd infra/terraform
terraform init -backend-config="bucket=YOUR_STATE_BUCKET"
terraform workspace new prod
terraform plan -var-file=environments/prod/terraform.tfvars
terraform apply -var-file=environments/prod/terraform.tfvars
```

### 3. Query the Platform (Python SDK)
```python
pip install alti-sdk

import asyncio
from alti_sdk import AltiClient

async def main():
    async with AltiClient(api_key="alti_live_your_key_here") as client:
        # Natural language query
        result = await client.nl2sql.query(
            "Show me top 10 customers by ARR this quarter",
            locale="en-US"
        )
        print(result.sql)
        print(result.result)

        # Grounded AI answer
        answer = await client.analytics.ask(
            "What caused the churn spike in EMEA last month?"
        )
        print(answer.answer)
        for cite in answer.citations:
            print(f"  [{cite['title']}]")

asyncio.run(main())
```

### 4. Embed Analytics in Your App
```html
<!-- 3 lines to embed in any web application -->
<script src="https://cdn.alti.ai/embed/v30.js"></script>
<script>
  AltiEmbed.init({
    apiKey: 'alti_live_your_key_here',
    tenantId: 't-your-tenant',
    theme: { colorPrimary: '#003087' }  // your brand color
  });
</script>

<alti-dashboard cols="3">
  <alti-metric-card metric="arr"></alti-metric-card>
  <alti-metric-card metric="churn_rate"></alti-metric-card>
  <alti-query-bar placeholder="Ask your data..."></alti-query-bar>
</alti-dashboard>
```

---

## Platform Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ALTI ANALYTICS PLATFORM                           │
├─────────────────────┬───────────────────────────┬──────────────────────────┤
│   FRONTEND / EMBED  │    DEVELOPER ECOSYSTEM     │      AUTONOMOUS LAYER    │
│  Web Components SDK │  OpenAPI 3.1 · Python SDK  │  RLHF · Workflow Engine │
│  White-label themes │  TypeScript SDK · Webhooks │  Institutional Memory   │
├─────────────────────┴───────────────────────────┴──────────────────────────┤
│                          24-SERVICE MICROSERVICES                          │
│  NL2SQL · Streaming · Compliance · FX/Currency · Storytelling · Consensus │
│  MLOps · Scenario Engine · Causal AI · Knowledge Graph · Edge Intelligence │
│  Observability · Tenant Control Plane · AI Governance · ABAC/PAM           │
│  Zero Trust · Generative BI · RAG Engine · Customer 360 · Semantic Layer  │
├─────────────────────────────────────────────────────────────────────────────┤
│                           AI / ML LAYER                                    │
│  551+ Swarm Agents · Vertex AI Agent Builder · Vertex Explainable AI      │
│  NL2SQL (50 languages) · Knowledge Graph · Regional Fine-Tuning            │
│  Gemini 1.5 Pro (1M ctx) · text-embedding-004 · Customer 360 CDP          │
├─────────────────────────────────────────────────────────────────────────────┤
│                          DATA TIER ROUTER                                  │
│  Cloud Spanner (writes/strong reads) │ AlloyDB (analytics/vector search)  │
│  BigQuery (historical/reporting/ML)  │ Memorystore Redis (cache/pub-sub)  │
│  Cloud Storage (raw data, documents) │ Vertex AI Vector Search (RAG)      │
├─────────────────────────────────────────────────────────────────────────────┤
│                        GCP INFRASTRUCTURE (Terraform IaC)                  │
│  Cloud Run · Artifact Registry · Cloud Build CI/CD · Cloud Armor WAF      │
│  VPC Service Controls · Cloud KMS CMEK · Secret Manager · Cloud Tasks     │
│  Security Command Center · Chronicle SIEM · Traffic Director (mTLS)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

See [Architecture Deep Dive](docs/ARCHITECTURE.md) for full system design.

---

## Industry Verticals

| Industry | Key Capabilities |
|---|---|
| 🏦 **Banking / FinTech** | Basel III reporting, fraud detection, FX consolidation, credit scoring with SHAP, FCRA/ECOA compliance |
| 🏥 **Healthcare** | HIPAA-compliant, FHIR-native, patient readmission AI, HCAHPS analytics, Epic EHR connector |
| 🏭 **Manufacturing** | PLM/SCADA integration, OEE monitoring, supply chain anomaly, edge intelligence |
| ⚽ **Sports & Media** | Player performance analytics, fan engagement, win probability models, broadcast metrics |
| 🏪 **Retail / FMCG** | Customer journey, demand forecasting, inventory anomaly, loyalty analytics |
| 🏛️ **Government** | Data sovereignty, multi-jurisdictional compliance, public sector reporting |
| 💊 **Pharmaceuticals** | Clinical trial RAG, drug interaction analysis, regulatory submission support |
| 🏗️ **Real Estate** | Property valuation models, market intelligence, portfolio risk |

---

## Key Services

| Service | Path | Description |
|---|---|---|
| `nl2sql` | `services/nl2sql/` | 50-language NL→SQL with streaming |
| `streaming-analytics` | `services/streaming-analytics/` | Real-time event pipelines |
| `global-compliance` | `services/global-compliance/` | GDPR/HIPAA/PDPA/LGPD/etc. |
| `currency-intelligence` | `services/currency-intelligence/` | Multi-currency FX & hedging |
| `zero-trust` | `services/zero-trust/` | SPIFFE mTLS, SOAR, SCC |
| `ai-governance` | `services/ai-governance/` | SHAP, EU AI Act, fairness |
| `access-control` | `services/access-control/` | ABAC, column masking, PAM |
| `autonomous-agents` | `services/autonomous-agents/` | Event workflows + RLHF |
| `developer-api` | `services/developer-api/` | OpenAPI, Python/TS SDKs, webhooks |
| `semantic-layer` | `services/semantic-layer/` | Canonical metrics + data mesh |
| `embedded-analytics` | `services/embedded-analytics/` | White-label Web Components SDK |
| `customer-360` | `services/customer-360/` | Identity resolution + CDP |
| `generative-bi` | `services/generative-bi/` | NL→Dashboard generator |
| `rag-engine` | `services/rag-engine/` | TB-scale multi-vector RAG |
| `observability` | `services/observability/` | SRE engine, SLOs, tracing |
| `tenant-control-plane` | `services/tenant-control-plane/` | Multi-tenant billing & onboarding |
| `spanner-alloydb` | `services/spanner-alloydb/` | Data tier router |
| `vertex-agent` | `services/vertex-agent/` | Grounded AI with live data |

---

## Documentation

| Document | Description |
|---|---|
| [Architecture Guide](docs/ARCHITECTURE.md) | Full system design, data flow diagrams, service dependencies |
| [API Reference](docs/API_REFERENCE.md) | Complete REST API for all 24 services |
| [Security Guide](docs/SECURITY.md) | Zero-trust, mTLS, ABAC, PAM, AI governance |
| [Deployment Guide](docs/DEPLOYMENT.md) | Terraform IaC, GCP setup, CI/CD pipeline |
| [SDK Guide](docs/SDK_GUIDE.md) | Python + TypeScript SDK, webhook integration |
| [RAG Configuration](docs/RAG_GUIDE.md) | TB-scale document ingestion and retrieval |
| [AI Governance](docs/AI_GOVERNANCE.md) | EU AI Act, SHAP, fairness, SR 11-7, FDA |
| [Data Architecture](docs/DATA_ARCHITECTURE.md) | BigQuery, Spanner, AlloyDB, semantic layer |
| [Changelog](docs/CHANGELOG.md) | Full release history across all 30 phases |
| [Runbook](docs/RUNBOOK.md) | Operational runbook for SRE on-call engineers |

---

## Compliance & Certifications

| Standard | Status | Details |
|---|---|---|
| **EU AI Act** | Compliant | High-risk AI system documentation, conformity assessments for all models |
| **GDPR / CCPA** | Compliant | Right to erasure, data subject requests, consent management |
| **HIPAA** | Compliant | PHI encryption, BAA support, audit logging, access controls |
| **SR 11-7** | Compliant | Model risk documentation, validation, adverse action notices |
| **SOC 2 Type II** | In Progress | Controls mapped, audit scheduled |
| **ISO 27001** | In Progress | Information security management system established |
| **PCI DSS** | Compliant | Card data tokenization, network segmentation, audit trails |
| **FIPS 140-2** | Compliant | Cloud KMS CMEK with FIPS-validated modules |

---

## Infrastructure at a Glance

- **Cloud**: Google Cloud Platform (GCP) exclusively
- **IaC**: Terraform with remote state in GCS
- **Compute**: Cloud Run (serverless, auto-scaling)
- **Database**: Cloud Spanner (global) + AlloyDB (regional) + BigQuery (analytics)
- **AI**: Vertex AI (Agent Builder, Explainable AI, Vector Search)
- **Security**: VPC Service Controls, Cloud KMS CMEK, Cloud Armor WAF
- **Observability**: Cloud Logging, Cloud Trace, Cloud Monitoring, Chronicle SIEM
- **CI/CD**: Cloud Build with canary deployments and k6 SLO validation

---

## Release History

| Version | Phases | Epics | Description |
|---|---|---|---|
| **v30.0.0** | 30 | 91 | Generative BI, TB-scale RAG, Premium UI/UX |
| **v29.0.0** | 29 | 88 | Embedded Analytics SDK, Customer 360 CDP |
| **v28.0.0** | 28 | 86 | Autonomous Workflows, RLHF, Developer API |
| **v27.0.0** | 27 | 83 | Zero-Trust, AI Governance, ABAC/PAM |
| **v26.0.0** | 26 | 80 | Enterprise Productization, SRE, Multi-tenant |
| **v25.0.0** | 25 | 77 | GCP Production Foundation, Terraform IaC |
| ...see [CHANGELOG](docs/CHANGELOG.md) for full history | | | |

---

## License

Apache License 2.0 — see [LICENSE](LICENSE)

---

*Built with ❤️ on Google Cloud Platform · 30 Phases · 91 Epics · Production-ready*
