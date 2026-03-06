# Complete Changelog — Alti Analytics Platform

> **91 Epics across 30 Phases** | Production on Google Cloud Platform

---

## v30.0.0 — Phase 30: Generative BI, TB-Scale RAG & Premium UI/UX
*Released: 2026-03-05*

### Epic 89 — Generative BI & Self-Service Dashboard Builder
- Natural language → complete dashboard JSON schema in seconds
- 13 chart-type selection rules (LINE, HEATMAP, SANKEY, FUNNEL, TREEMAP, WATERFALL, CHOROPLETH, SCATTER, HISTOGRAM, BAR, DONUT, METRIC_CARD, TABLE)
- 15 canonical metric aliases resolved via semantic layer
- Audience detection: BOARD, EXECUTIVE, ANALYST, OPERATIONAL
- 12-column responsive grid layout engine (metric cards row 0, charts below)
- AI-generated per-widget insights
- Scheduled PDF email delivery (cron-based)
- One-click share tokens

### Epic 90 — TB-Scale RAG Pipeline for Heavy Commercial Data
- Hierarchical document ingestion: PDF, DOCX, XLSX, HTML, JSON, EMAIL, CSV at TB scale
- Per-type chunking strategies (SECTION, TABLE_UNIT never split, TOPIC_SEG for 100+ page docs, SLIDING_WIN)
- 10% semantic overlap between chunks to preserve context boundaries
- Dense retrieval: Vertex AI text-embedding-004 (768-dim)
- Sparse retrieval: BM25 with IDF term weights (k1=1.5, b=0.75)
- Reciprocal Rank Fusion (K=60): combines dense + sparse signals
- Cross-encoder reranker: +15% NDCG@10 on enterprise benchmarks
- Gemini 1.5 Pro long-context mode: stuffs all context when < 800k tokens
- Query decomposition: multi-jurisdiction, multi-period, multi-entity parallel sub-queries

### Epic 91 — Premium UI/UX Design System
- 50+ CSS custom property design tokens
- Glassmorphism surfaces: backdrop-filter blur(20px) saturate(180%)
- 10-color data visualization palette
- Full component library: glass cards, gradient buttons, glow inputs, semantic badges
- KPI metric cards with top-gradient reveal animation on hover
- Multi-turn AI chat UI with streaming typing indicator and citation pills
- Data explorer: schema browser, column type pills, SQL editor with syntax highlighting
- Sidebar with active indicator rail and collapsible icon-only mode
- 8 micro-animation classes with staggered children delays
- WCAG 2.1 AA compliance (focus-visible rings, 4.5:1+ contrast everywhere)
- Full light mode via `[data-theme="light"]` CSS variable override

---

## v29.0.0 — Phase 29: Embedded Analytics & Customer 360 CDP
*Released: 2026-03-05*

### Epic 87 — Embedded Analytics & White-Label Component SDK
- 5 Web Components: `<alti-query-bar>`, `<alti-metric-card>`, `<alti-anomaly-feed>`, `<alti-narrative>`, `<alti-dashboard>`
- CSP-safe iframe-free embedding via signed RS256 JWT tokens and postMessage
- 18 CSS custom property design tokens for full brand control
- Per-tenant white-label theming (colors, fonts, radii — all overridable)
- Works natively in React, Vue, Angular, and plain HTML
- Live anomaly feed with 4-second real-time refresh
- AltiEmbed.init() 3-line drop-in for any web application

### Epic 88 — Customer 360 & Identity Resolution CDP
- Probabilistic identity resolution: confidence = 1 - Π(1 - signal_weight)
- 8 signal types: EMAIL_EXACT (1.0), PHONE_EXACT (0.98), CUSTOMER_ID (1.0), PAYMENT_CARD (0.95), DEVICE_FINGERPRINT (0.80), NAME_FUZZY (0.65), ADDRESS_PARTIAL (0.70), IP_CLUSTER (0.45)
- Customer 360 aggregation from 5 data domains (CRM, behavioral, financial, support, AI-derived)
- Journey stage classification: SIGNUP → ONBOARDING → ACTIVATION → ADOPTION → EXPANSION → ADVOCACY
- NBA (Next Best Action) 8-rule priority matrix
- Behavioral cohort analysis with lift factor and p-value (significant at p < 0.05)
- Customer journey path discovery: 4 archetypal paths with median ARR impact

---

## v28.0.0 — Phase 28: Autonomous Intelligence & Developer Ecosystem
*Released: 2026-03-05*

### Epic 84 — Autonomous Agent Workflows & RLHF
- 5 pre-built autonomous workflows: Churn Anomaly Response, Fraud Auto-Block, Monday CEO Brief, SLO Breach Auto-Diagnose, Data Quality Remediation
- RLHF continuous learning: corrections trigger Vertex AI fine-tuning at 50-correction threshold
- Institutional memory: per-tenant vocabulary, fiscal calendars, past reasoning traces
- Proactive insight surfacing: scheduled briefs, immediate anomaly push, threshold-based alerts

### Epic 85 — Public Developer API, Python/TS SDKs & Webhooks
- 22 API paths across 11 tag groups
- OpenAPI 3.1 specification with Swagger UI at docs.alti.ai
- Python SDK: async client with retry logic, streaming, pandas integration
- TypeScript SDK: full type safety, tree-shakable exports
- HMAC-SHA256 webhook signatures with 3-retry exponential backoff
- Developer sandbox at sandbox.alti.ai

### Epic 86 — Universal Semantic Layer & Data Mesh
- 10 canonical metrics resolving by name OR alias across 7 industries
- "ARR", "Annual Recurring Revenue", "yearly revenue" → all same SQL
- 3 data products with owner, SLA, freshness contract, schema change notifications
- Breaking-change notifications fire to subscribers before code breaks
- Metric consistency validator: alerts when same metric returns different values

---

## v27.0.0 — Phase 27: Security, AI Governance & Responsible AI
*Released: 2026-03-05*

### Epic 81 — Zero-Trust Security Architecture
- SPIFFE mTLS across all 24 Cloud Run services via Traffic Director
- Security Command Center Premium: continuous vulnerability scanning
- Chronicle SIEM: streaming GCP audit logs and Cloud Armor events
- SOAR playbooks: 6 automated threat categories (DATA_EXFILTRATION, LATERAL_MOVEMENT, PRIVILEGE_ESCALATION, CREDENTIAL_THEFT, IMPOSSIBLE_TRAVEL, INJECTION_ATTACK)
- < 60 second detection-to-automated-response SLA

### Epic 82 — AI Explainability & Responsible AI
- SHAP feature attributions for every regulated model prediction via Vertex Explainable AI
- Fairness monitoring: equalized odds detection with demographic disparity alerts
- Immutable AI audit trail: every prediction logged with inputs, outputs, SHAP, human decisions
- EU AI Act compliance layer: risk classification, conformity assessments, prohibited use case blocking

### Epic 83 — Fine-Grained Access Control & PAM
- Column-level dynamic data masking (CLEAR/MASKED/HASHED/REDACTED/NULL per role)
- ABAC policy engine: role + department + clearance + data classification
- Access request and approval workflow with mandatory justification
- Break-glass PAM: time-bound emergency access, mandatory audit, auto-revocation

---

## v26.0.0 — Phase 26: Enterprise Productization & GCP Production
*Released: 2026-03-04*

### Epic 78 — Tenant Control Plane & Metered Billing
- 5-tier pricing model (Starter $299/mo → Custom)
- Metered billing: BigQuery bytes, AI tokens, API calls, active users
- Stripe integration for automated invoicing
- Self-service onboarding portal with 22-step provisioning workflow

### Epic 79 — SRE Engine & Error Budget Management
- SLO contracts for all 24 services (availability + p99 latency)
- Error budget burn rate escalation (2x/5x/10x thresholds)
- k6 SLO smoke test suite in CI/CD pipeline
- Automated incident creation (PagerDuty) on budget exhaustion

### Epic 80 — Connector Marketplace
- 40+ pre-built connectors: Salesforce, Snowflake, Epic EHR, Bloomberg, SAP, AWS S3, Stripe, Zendesk
- Connector health dashboard with SLA reporting
- Custom connector SDK for internal data sources

---

## v25.0.0 — Phase 25: GCP Production Foundation & Terraform IaC
*Released: 2026-03-04*

### Epic 75 — Terraform IaC Complete
- All 24 Cloud Run services defined in Terraform
- Cloud Spanner + AlloyDB + BigQuery provisioned declaratively
- Vertex AI services (Agent Builder, Vector Search, Workbench)
- VPC Service Controls, Cloud Armor WAF, Cloud KMS CMEK
- Remote state in GCS with locking via Terraform GCS backend

### Epic 76 — CI/CD Pipeline with Canary Deployments
- Cloud Build pipeline: test → build → push → canary 5% → SLO check → promote
- Automatic rollback if error rate > 1% during canary window
- Container images stored in Artifact Registry
- Signed images with Binary Authorization

### Epic 77 — Vertex AI Agent Builder + Grounded RAG
- Agent Builder store connected to BigQuery and Cloud Storage
- Grounding with Google Search for market/competitor data
- Hybrid grounding: enterprise data + web for comprehensive answers
- Agent Builder traces stored for debugging and RLHF

---

## v24.0.0 — Phase 24: Edge Intelligence & Offline Analytics
*Released: 2026-03-04*

### Epic 72 — Edge Intelligence
- 12 lightweight models (< 50MB) deployable on-device
- Offline-capable analytics with local SQLite cache
- Automated sync with conflict resolution on reconnect
- Edge-to-cloud model updates without full deployment

### Epic 73 — Regional AI Models
- Fine-tuned NL2SQL models per region (EU, US-EAST, APAC, MENA)
- Regional fiscal calendar knowledge injected per locale
- Regulatory domain expertise per jurisdiction
- Federated training: regional improvements without cross-border data movement

### Epic 74 — Multi-Cloud Data Federation
- Query data residing in AWS S3, Azure Blob, and GCP Storage simultaneously
- BigQuery Omni for cross-cloud analytics without data movement
- Federation adapter for Snowflake and Databricks catalogs

---

## v23.0.0 — Phase 23: Data Sovereignty & Global Compliance
*Released: 2026-02-28*

### Epic 69 — Data Residency Enforcement
- Per-tenant region pinning (data never leaves designated region)
- VPC Service Controls perimeter enforced at API level
- Routing logic: requests automatically directed to correct regional cluster
- Data sovereignty attestation reports per jurisdiction

### Epic 70 — Global Regulatory Compliance Engine
- 23 regulations implemented: GDPR, HIPAA, PDPA, LGPD, PIPEDA, PCI DSS, Basel III, EU AI Act, SR 11-7, FCRA, ECOA, FDA 21 CFR 11, APRA CPS 234, and more
- Automated DSR (Data Subject Request) fulfillment in < 72 hours (GDPR requirement)
- Consent management ledger in Cloud Spanner (immutable)

### Epic 71 — 50-Language Support
- NL2SQL in 50 languages with native locale handling
- Regional date/number formatting (fiscal calendars, decimal separators)
- Script-aware processing (Arabic RTL, CJK tokenization)
- Per-language prompt engineering and answer quality testing

---

## v20.0.0 — Phase 20: Advanced AI Capabilities
*Released: 2026-02-15*

### Epics 58–64: Causal AI, Knowledge Graph, Scenario Engine
- Causal discovery: PC algorithm + DoWhy for root cause chains
- Property graph (Neo4j-compatible) over business entities
- Monte Carlo scenario simulation with confidence intervals
- Voice-to-insight pipeline (Speech-to-Text → NL2SQL → TTS)
- Multi-currency hedging recommendations across 50+ currencies
- Federated analytics across 4 verticals

---

## v15.0.0 — Phase 15: Multi-Industry AI Swarm  
*Released: 2026-01-15*

### Epics 40–50: Industry Specialist Agents
- Banking: 40+ agents (fraud, AML, credit, regulatory)
- Healthcare: 32+ agents (FHIR, HIPAA, clinical AI)
- Sports: 24+ agents (performance, scouting, fan)
- Manufacturing: 28+ agents (OEE, supply chain, quality)
- Retail: 20+ agents (demand, loyalty, inventory)

---

## v10.0.0 — Phase 10: Foundation AI Platform
*Released: 2025-12-01*

### Epics 25–35: Core AI Capabilities
- NL2SQL v1.0 (English only, BigQuery-targeted)
- First swarm agents: analytics, compliance, data catalog
- Streaming analytics pipeline with pub/sub
- Basic anomaly detection
- Initial multi-tenant data isolation

---

## v1.0.0 — Phase 1: Initial Foundation
*Released: 2025-09-01*

- Cloud Spanner + AlloyDB + BigQuery initial setup
- First Cloud Run service deployment
- Terraform foundation modules
- Basic tenant isolation

---

*This changelog covers all 91 Epics across 30 Phases of the Alti Analytics Platform.*
