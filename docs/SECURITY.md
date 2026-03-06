# Security Guide — Alti Analytics Platform

> **Security posture**: Zero-Trust · SPIFFE mTLS · SOAR auto-remediation · ABAC column masking · Break-glass PAM · EU AI Act compliant · SR 11-7 compliant

---

## Table of Contents
1. [Zero-Trust Architecture](#zero-trust-architecture)
2. [mTLS Service Mesh](#mtls-service-mesh)
3. [SOAR Threat Response](#soar-threat-response)
4. [ABAC Access Control](#abac-access-control)
5. [Column-Level Data Masking](#column-level-data-masking)
6. [Privileged Access Management (PAM)](#privileged-access-management-pam)
7. [AI Governance & Explainability](#ai-governance--explainability)
8. [Infrastructure Security](#infrastructure-security)
9. [Incident Response](#incident-response)
10. [Compliance Matrix](#compliance-matrix)

---

## Zero-Trust Architecture

The platform implements a **never trust, always verify** model across all layers.

### Principles Applied

| Principle | Implementation |
|---|---|
| Verify explicitly | JWT + mTLS on every request, regardless of network location |
| Least privilege | Service accounts scoped to individual Cloud Run services |
| Assume breach | SOAR playbooks auto-respond before human review |
| Micro-segmentation | VPC Service Controls perimeter per environment |

### Trust Boundaries

```
UNTRUSTED ZONE          │   DMILITARIZED ZONE     │   TRUSTED ZONE
(Internet)              │   (API Gateway / WAF)   │   (Service Mesh)
                        │                         │
External User           │   Cloud Armor WAF        │   24 Cloud Run Services
  │ HTTPS + API Key     │   JWT validation         │   mTLS (SPIFFE SVIDs)
  └──────────────────►  │  ──────────────────────► │   ABAC authorization
                        │   Rate limiting          │   Column masking
                        │   OWASP Top 10 rules     │   Row-level security
```

---

## mTLS Service Mesh

### SPIFFE Identity Registry

All 24 services receive SPIFFE Verifiable Identity Documents (SVIDs) at pod startup. SVIDs rotate every 24 hours.

```python
# Example SVID assignment (zero_trust_engine.py)
SPIFFE_REGISTRY = {
    "api-gateway":          "spiffe://alti.ai/service/api-gateway",
    "nl2sql":               "spiffe://alti.ai/service/nl2sql",
    "streaming-analytics":  "spiffe://alti.ai/service/streaming-analytics",
    "ai-governance":        "spiffe://alti.ai/service/ai-governance",
    "access-control":       "spiffe://alti.ai/service/access-control",
    # ... all 24 services
}
```

### Service Mesh Allow-List

Only explicitly permitted direction pairs are allowed:

| Caller | Target | Permitted |
|---|---|---|
| `api-gateway` | Any service | ✅ |
| `nl2sql` | `spanner-alloydb` | ✅ |
| `nl2sql` | `streaming-analytics` | ❌ DENY → lateral movement alert |
| `streaming-analytics` | `vertex-agent` | ❌ DENY → lateral movement alert |
| `ai-governance` | `spanner-alloydb` | ✅ |
| Any | `zero-trust` | ✅ (for event reporting) |

Any unauthorized call fires a **LATERAL_MOVEMENT** threat event and triggers SOAR response within 60 seconds.

---

## SOAR Threat Response

### Threat Categories & Playbooks

| Category | Severity | Detection | Auto Actions |
|---|---|---|---|
| `DATA_EXFILTRATION` | CRITICAL | > 10GB in < 10 min | Isolate tenant, disable SA, create SCC finding, P1 PagerDuty |
| `LATERAL_MOVEMENT` | HIGH | Unauthorized service-to-service call | Block call, revoke token, Slack `#security-alerts` |
| `PRIVILEGE_ESCALATION` | CRITICAL | `roles/owner` granted outside Terraform | Disable SA, kill sessions, P1 PagerDuty |
| `CREDENTIAL_THEFT` | CRITICAL | Secret Manager secret accessed from unknown IP | Rotate secret, disable SA, P1 PagerDuty |
| `IMPOSSIBLE_TRAVEL` | CRITICAL | Same user in 2 distant locations < 1 hour | Revoke token, kill sessions, block IP |
| `INJECTION_ATTACK` | HIGH | SQL injection pattern in NL2SQL input | Block request, log payload, rate-limit IP |

### Response SLA

- **Detection to automated action**: < 60 seconds
- **Human notification**: < 5 minutes (PagerDuty)
- **SCC finding created**: < 30 seconds

---

## ABAC Access Control

### Policy Evaluation Order

Policies are evaluated in order. First matching policy wins.

```
P-001: Deny cross-tenant access (tenant_id mismatch)
P-002: Deny SECRET classification to non-admins
P-003: Deny PHI access to non-clinical roles
P-004: Deny RESTRICTED data without MFA
P-005: Deny EXPORT without clearance level 3+
P-100: Default PERMIT (all other conditions)
```

### Subject Attributes

Every access decision considers:
- `user_id` — authenticated identity
- `roles` — e.g. `["doctor","nurse"]` or `["analyst"]`
- `department` — e.g. `"cardiology"`, `"finance"`
- `clearance` — integer 1–5
- `mfa_verified` — boolean (required for RESTRICTED data)
- `ip_address` — for geo-anomaly detection
- `tenant_id` — must match resource tenant_id

---

## Column-Level Data Masking

### Masking Profiles

| Profile | Behavior | Example |
|---|---|---|
| `CLEAR` | Raw value returned | `john.smith@bank.com` |
| `MASKED` | First 2 + last 2 chars visible | `jo***th` |
| `HASHED` | SHA-256 first 16 chars | `a3f8d1c9b2e40712` |
| `REDACTED` | Literal "REDACTED" | `REDACTED` |
| `NULL` | Field omitted from response | *(field absent)* |

### Column Masking Rules by Role

| Table | Column | doctor/nurse | billing | analyst | engineer |
|---|---|---|---|---|---|
| `patients` | `encrypted_pii` | CLEAR | REDACTED | NULL | NULL |
| `patients` | `date_of_birth` | CLEAR | MASKED | HASHED | HASHED |
| `patients` | `mrn` | CLEAR | MASKED | HASHED | NULL |
| `bank_accounts` | `account_number` | — | CLEAR | MASKED | HASHED |
| `transactions` | `amount` | — | CLEAR | CLEAR | MASKED |
| `customers` | `ssn` | — | — | NULL | NULL |
| `customers` | `email` | — | — | MASKED | HASHED |

Masking is applied **at query time** — raw values are never transmitted to unauthorized roles.

---

## Privileged Access Management (PAM)

### Break-Glass Access

Emergency privileged access requires:
1. An **active PagerDuty incident ID** (verified programmatically)
2. A written justification
3. Approval is automatic for P1 incidents — human approval for P2+

```python
# Example: on-call engineer accessing production during an incident
session = abac_engine.break_glass(
    engineer_id="sre-oncall-007",
    tenant_id="t-bank",
    incident_id="INC-2026-0391",    # must reference active incident
    justification="Spanner corruption — inspecting raw rows for recovery",
    duration_hours=4,
    resources=["spanner-alloydb","data-catalog"]
)
# Every action within the session is logged:
abac_engine.log_break_glass_action(session, "SELECT", "BankAccounts", 142)
# Auto-revoked after duration_hours:
abac_engine.revoke_break_glass(session, "incident resolved")
```

### Audit Trail

Every break-glass session writes to:
- **Cloud Audit Log** (tamper-proof, WORM)
- **BigQuery** `alti_compliance.pam_sessions` table
- **Security Command Center** as an activity log
- **Slack `#security-pam`** channel (real-time notification)

Audit entries are retained for **7 years** (regulatory requirement).

---

## AI Governance & Explainability

### SHAP Explanations (Every Prediction)

Every model prediction includes a SHAP breakdown:

```json
{
  "use_case": "credit_scoring",
  "raw_score": 0.73,
  "decision": "DENIED",
  "shap_explanation": {
    "base_value": 0.35,
    "top_positive": [
      ["credit_utilization", 0.19],
      ["payment_history",    0.14],
      ["recent_inquiries",   0.03]
    ],
    "top_negative": [
      ["credit_age", -0.04]
    ],
    "human_readable": "Score: 73% (baseline: 35%). Factors that increased this score: credit utilization (+0.19), payment history (+0.14). Factors that decreased this score: credit age (-0.04)."
  },
  "human_review_required": true,
  "regulation": ["EU_AI_ACT", "SR_11_7", "FCRA", "ECOA"]
}
```

### Prohibited Features (SR 11-7)

The following features are **blocked** from use in regulated models:

| Use Case | Prohibited Features |
|---|---|
| `credit_scoring` | race, ethnicity, religion, national_origin, sex, marital_status, age, disability |
| `hiring_screening` | race, ethnicity, religion, national_origin, sex, marital_status, age, disability |
| `insurance_pricing` | race, religion, national_origin |

If a prohibited feature is detected in a prediction request, the prediction is **blocked** and a compliance alert is fired.

---

## Infrastructure Security

### Network Security

| Control | Implementation |
|---|---|
| VPC Service Controls | Enforced perimeter around all GCP services |
| Private Google Access | VMs reach GCP APIs without public internet |
| Cloud NAT | Outbound internet via NAT (no inbound public IPs) |
| Firewall rules | Deny all ingress except load balancer health checks |
| Cloud Armor WAF | OWASP Top 10 rules + IP rate limiting (1000 req/min) |

### Encryption

| Data State | Encryption |
|---|---|
| Data at rest | Cloud KMS CMEK (90-day auto-rotation) |
| Data in transit | TLS 1.3 (minimum) for all external, mTLS for internal |
| BigQuery | Per-dataset CMEK |
| Cloud Storage | Per-bucket CMEK |
| Spanner | CMEK with KMS key ring per environment |
| Secret Manager | Managed encryption + access logging |

### IAM Least Privilege (Service Accounts)

| Service Account | Roles (Minimal) |
|---|---|
| `cloud-run-sa` | `roles/datastore.user`, `roles/bigquery.dataViewer` |
| `dataflow-sa` | `roles/dataflow.worker`, `roles/storage.objectAdmin` |
| `vertex-ai-sa` | `roles/aiplatform.user`, `roles/bigquery.dataViewer` |
| `cicd-sa` | `roles/run.developer`, `roles/artifactregistry.writer` |

No service account has `roles/owner` or `roles/editor`.

---

## Incident Response

### Runbook: Security Incident

1. **Initial triage** (SRE on-call, automated via SOAR)
   - SOAR playbook fires within 60 seconds of detection
   - Automatic isolation actions prevent lateral spread
   - PagerDuty incident created

2. **Assessment** (15 minutes)
   - Security team joins war room (Slack `#incident-XXXX`)
   - Blast radius determined using Cloud Audit Logs + Chronicle SIEM
   - Chronicle intelligence correlated with Mandiant threat feeds

3. **Containment** (< 1 hour)
   - Affected service account disabled
   - Tenant isolated if exfiltration detected
   - Network-level blocks applied via Cloud Armor

4. **Eradication** (< 4 hours)
   - Root cause identified
   - Vulnerable code/config remediated
   - Credentials rotated

5. **Recovery** (< 8 hours)
   - Service restored in canary mode (5% traffic)
   - SLO monitored for 30 minutes before full traffic restore

6. **Post-Incident Review** (within 5 business days)
   - Blameless PIR document written
   - Action items tracked to completion

---

## Compliance Matrix

| Regulation | Scope | Controls | Status |
|---|---|---|---|
| **GDPR** | EU personal data | Consent management, right to erasure, DPA agreements | ✅ Compliant |
| **HIPAA** | US health data (PHI) | Encryption, BAA, audit logs, minimum necessary | ✅ Compliant |
| **EU AI Act** | High-risk AI systems | Conformity assessment, SHAP, human oversight, audit trail | ✅ Compliant |
| **SR 11-7** | US banking models | Model documentation, validation, adverse action notices | ✅ Compliant |
| **FCRA/ECOA** | US credit decisions | SHAP adverse action notices, prohibited feature blocking | ✅ Compliant |
| **PDPA** | Singapore data | Data residency in SG region, consent records | ✅ Compliant |
| **LGPD** | Brazilian data | Data subject rights, DPO appointment | ✅ Compliant |
| **PCI DSS** | Payment card data | Card data tokenization, network segmentation | ✅ Compliant |
| **FDA 21 CFR 11** | Clinical AI records | Tamper-proof audit logs, human review workflows | ✅ Compliant |
| **SOC 2 Type II** | Service controls | Controls mapped, audit in progress | 🔄 In Progress |
| **ISO 27001** | Information security | ISMS established, gap assessment complete | 🔄 In Progress |
