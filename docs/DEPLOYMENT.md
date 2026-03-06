# Deployment Guide — Alti Analytics Platform

> **Infrastructure as Code with Terraform** | GCP-only deployment | Cloud Run + Spanner + BigQuery + Vertex AI

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Repository Structure](#repository-structure)
3. [Initial GCP Setup](#initial-gcp-setup)
4. [Terraform Deployment](#terraform-deployment)
5. [Environment Configuration](#environment-configuration)
6. [CI/CD Pipeline](#cicd-pipeline)
7. [Post-Deploy Validation](#post-deploy-validation)
8. [Canary Deployment](#canary-deployment)
9. [Rollback Procedures](#rollback-procedures)
10. [Disaster Recovery](#disaster-recovery)

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| `gcloud` CLI | ≥ 463.0 | `curl https://sdk.cloud.google.com \| bash` |
| Terraform | ≥ 1.8.0 | https://developer.hashicorp.com/terraform/install |
| Docker | ≥ 20.10 | https://docs.docker.com/get-docker/ |
| Python | ≥ 3.11 | https://python.org |
| Node.js | ≥ 18 | https://nodejs.org |

```bash
# Authenticate gcloud
gcloud auth login
gcloud auth application-default login

# Verify authentication
gcloud config list
```

---

## Repository Structure

```
Alti.Analytics/
├── infra/terraform/
│   ├── modules/
│   │   ├── cloud-run/         # Cloud Run service module
│   │   ├── spanner/           # Cloud Spanner instance + databases
│   │   ├── alloydb/           # AlloyDB cluster + primary instance
│   │   ├── bigquery/          # BigQuery datasets + tables
│   │   ├── vertex-ai/         # Vertex AI services
│   │   ├── networking/        # VPC, subnets, NAT, Service Controls
│   │   ├── security/          # IAM, KMS, Secret Manager
│   │   └── observability/     # Logging, monitoring, Chronicle SIEM
│   ├── environments/
│   │   ├── dev/               # Development environment
│   │   ├── staging/           # Staging environment
│   │   └── prod/              # Production environment
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── services/                  # Application code per service
│   ├── nl2sql/
│   ├── streaming-analytics/
│   ├── ai-governance/
│   └── ... (24 services total)
├── frontend/
│   └── design-system/
├── docs/
└── .cloudbuild/               # Cloud Build pipeline definitions
```

---

## Initial GCP Setup

### 1. Create GCP Project

```bash
export PROJECT_ID="alti-analytics-prod"
export BILLING_ACCOUNT="XXXXXX-XXXXXX-XXXXXX"
export REGION="us-central1"

# Create project
gcloud projects create $PROJECT_ID --name="Alti Analytics Production"

# Link billing
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT

# Set default project
gcloud config set project $PROJECT_ID
```

### 2. Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  spanner.googleapis.com \
  alloydb.googleapis.com \
  bigquery.googleapis.com \
  aiplatform.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudkms.googleapis.com \
  vpcaccess.googleapis.com \
  servicenetworking.googleapis.com \
  iap.googleapis.com \
  cloudtrace.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  securitycenter.googleapis.com \
  chronicle.googleapis.com \
  trafficdirector.googleapis.com
```

### 3. Create Terraform State Bucket

```bash
# Create GCS bucket for Terraform state
gsutil mb -p $PROJECT_ID \
  -c STANDARD \
  -l $REGION \
  gs://alti-tfstate-$PROJECT_ID

# Enable versioning for state recovery
gsutil versioning set on gs://alti-tfstate-$PROJECT_ID
```

### 4. Create CI/CD Service Account

```bash
gcloud iam service-accounts create cicd-sa \
  --display-name="Alti CI/CD Service Account"

SA_EMAIL="cicd-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Minimal roles for CI/CD
for ROLE in \
  roles/run.developer \
  roles/artifactregistry.writer \
  roles/cloudbuild.builds.builder \
  roles/storage.objectAdmin; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="$ROLE"
done
```

---

## Terraform Deployment

### Configure Variables

```bash
cp infra/terraform/environments/prod/terraform.tfvars.example \
   infra/terraform/environments/prod/terraform.tfvars
```

Edit `terraform.tfvars`:
```hcl
# infra/terraform/environments/prod/terraform.tfvars

project_id              = "alti-analytics-prod"
region                  = "us-central1"
environment             = "prod"

# Cloud Spanner
spanner_instance_config = "regional-us-central1"
spanner_processing_units = 1000       # 1 node = 1000 PU

# AlloyDB
alloydb_cpu_count       = 16
alloydb_read_pool_nodes = 2

# BigQuery
bq_location             = "US"

# Vertex AI
vertex_region           = "us-central1"

# Security
enable_vpc_sc           = true
enable_cmek             = true
key_rotation_days       = 90

# Alerting
pagerduty_key           = ""          # Set in Secret Manager instead
slack_webhook_url       = ""          # Set in Secret Manager instead
```

### Deploy Infrastructure

```bash
cd infra/terraform

# Initialize (with remote state)
terraform init \
  -backend-config="bucket=alti-tfstate-${PROJECT_ID}" \
  -backend-config="prefix=terraform/prod"

# Create workspace
terraform workspace new prod

# Preview changes
terraform plan \
  -var-file=environments/prod/terraform.tfvars \
  -out=prod.tfplan

# Apply (takes ~25 minutes for full stack)
terraform apply prod.tfplan
```

### Terraform Modules Summary

| Module | Resources Created |
|---|---|
| `networking` | VPC, 3 subnets, Cloud NAT, VPC Service Controls perimeter |
| `security` | Cloud KMS key ring (6 keys), 18 service accounts, IAM bindings |
| `spanner` | Instance (1000 PU), 5 databases, schema migrations |
| `alloydb` | Cluster, primary instance (16 vCPU/128GB), read pool (2 nodes) |
| `bigquery` | 6 datasets, column-level security, row-level policies |
| `vertex-ai` | Agent Builder store, Vector Search index (768-dim), Workbench |
| `cloud-run` | 24 services, min/max instances, mTLS config, IAM invoker bindings |
| `observability` | Log sinks, dashboards, alert policies, SLO configs, Chronicle SIEM |

---

## Environment Configuration

### Secret Manager (Post-Terraform)

```bash
# Store secrets (do NOT put these in .tfvars)
echo -n "your-pagerduty-key" | gcloud secrets create pagerduty-key \
  --data-file=- --project=$PROJECT_ID

echo -n "your-slack-webhook" | gcloud secrets create slack-webhook \
  --data-file=- --project=$PROJECT_ID

echo -n "your-openai-or-third-party-key" | gcloud secrets create external-ai-key \
  --data-file=- --project=$PROJECT_ID
```

### Cloud Run Environment Variables

Cloud Run services read configuration from Secret Manager at startup. Key variables:

| Variable | Secret | Description |
|---|---|---|
| `SPANNER_PROJECT` | — | GCP project ID |
| `SPANNER_INSTANCE` | — | Spanner instance name |
| `ALLOYDB_DSN` | `alloydb-dsn` | AlloyDB connection string |
| `ANTHROPIC_KEY` | `anthropic-key` | External AI services |
| `PAGERDUTY_KEY` | `pagerduty-key` | Incident management |
| `STRIPE_SECRET` | `stripe-secret-key` | Billing integration |
| `CHRONICLE_INGESTION_URL` | `chronicle-url` | SIEM ingestion endpoint |

---

## CI/CD Pipeline

### Cloud Build Pipeline Stages

```yaml
# .cloudbuild/pipeline.yaml
steps:
  # 1. Run unit tests
  - name: 'python:3.11'
    entrypoint: bash
    args: ['-c', 'pip install -r requirements.txt && pytest tests/ -x -q']

  # 2. Security scan (container)
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${_IMAGE}', '.']
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args: ['gcloud', 'artifacts', 'docker', 'images', 'scan', '${_IMAGE}']

  # 3. Push to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${_IMAGE}']

  # 4. Canary deploy (5% traffic)
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - gcloud
      - run
      - deploy
      - '${_SERVICE}'
      - '--image=${_IMAGE}'
      - '--region=us-central1'
      - '--no-traffic'

  # 5. SLO validation (k6, 5 minutes)
  - name: 'grafana/k6'
    args: ['run', '.cloudbuild/slo_smoke_test.js']
    env:
      - 'BASE_URL=${_CANARY_URL}'
      - 'TRAFFIC_PCT=5'

  # 6. Promote to 100% if SLO passes
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - gcloud
      - run
      - services
      - update-traffic
      - '${_SERVICE}'
      - '--to-latest'
      - '--region=us-central1'
```

### Deployment Triggers

| Trigger | Branch | Action |
|---|---|---|
| PR opened | any | Run tests + security scan (no deploy) |
| Merge to `main` | `main` | Deploy to dev |
| Tag `v*.*.*-rc*` | — | Deploy to staging |
| Tag `v*.*.*` | — | Deploy to prod (canary → promote) |

---

## Post-Deploy Validation

After every production deployment, run:

```bash
# 1. Service health checks
for SERVICE in nl2sql streaming-analytics ai-governance access-control; do
  URL=$(gcloud run services describe $SERVICE --region=us-central1 --format='value(status.url)')
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL/health")
  echo "$SERVICE: HTTP $STATUS"
done

# 2. SLO baseline check
gcloud monitoring slo-status list \
  --project=$PROJECT_ID \
  --filter="type=request_based" \
  --format="table(displayName,currentValue,goal)"

# 3. Spanner connectivity
gcloud spanner databases execute-sql alti-main \
  --instance=alti-prod \
  --sql="SELECT COUNT(*) FROM tenants"

# 4. BigQuery smoke test
bq query --nouse_legacy_sql \
  "SELECT COUNT(*) FROM \`alti-analytics-prod.alti_raw.events\`"
```

---

## Canary Deployment

For high-risk changes, use a manual canary:

```bash
# Deploy new version without receiving traffic
gcloud run deploy SERVICE_NAME \
  --image=IMAGE_URL \
  --no-traffic \
  --tag=canary

# Shift 5% traffic to canary
gcloud run services update-traffic SERVICE_NAME \
  --to-tags=canary=5

# Monitor for 30 minutes
watch -n 30 'gcloud monitoring time-series list \
  --filter="metric.type=run.googleapis.com/request/count" \
  --format="table(metric.labels.response_code_class,points[0].value.int64_value)"'

# If healthy, promote to 100%
gcloud run services update-traffic SERVICE_NAME --to-latest

# If issues, rollback to stable
gcloud run services update-traffic SERVICE_NAME --to-tags=stable=100
```

---

## Rollback Procedures

### Immediate Rollback (< 5 minutes)

```bash
# Roll back a single service to previous revision
gcloud run services update-traffic SERVICE_NAME \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region=us-central1

# List available revisions
gcloud run revisions list --service=SERVICE_NAME --region=us-central1
```

### Terraform Rollback

```bash
# Revert to previous Terraform state
terraform state pull > current.tfstate
git checkout HEAD~1 infra/terraform/
terraform plan -var-file=environments/prod/terraform.tfvars
terraform apply -var-file=environments/prod/terraform.tfvars
```

---

## Disaster Recovery

### RTO/RPO Targets

| Component | RTO | RPO | Strategy |
|---|---|---|---|
| Cloud Run services | < 5 min | 0 | Multi-region with traffic director |
| Cloud Spanner | < 10 min | < 5 sec | Multi-region instance (TrueTime) |
| AlloyDB | < 15 min | < 1 min | Cross-region replica |
| BigQuery | < 1 hour | 7 days | Time travel + backups |
| Vertex AI models | < 30 min | 24 hours | Model registry versioning |

### Backup Schedule

```bash
# Spanner backups (automated by Terraform)
# Daily at 02:00 UTC, retained 30 days

# AlloyDB backups (automated)
# Continuous WAL archiving → point-in-time recovery up to 35 days

# BigQuery backups (time travel)
# 7-day time travel enabled on all datasets
# SELECT * FROM `table` FOR SYSTEM_TIME AS OF TIMESTAMP '2026-01-01 00:00:00'
```

### Failover Runbook

In the event of a full region failure (`us-central1`):

1. Update Cloud DNS to point to DR region (`us-east1`)
2. Promote AlloyDB cross-region replica to primary
3. Update Cloud Run services to use DR Spanner replica
4. Notify tenants (automated email via Cloud Tasks)
5. Estimated recovery: < 30 minutes
