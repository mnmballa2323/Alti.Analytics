# infra/terraform/environments/prod/terraform.tfvars
# ─────────────────────────────────────────────────────────────────────────────
# Production environment configuration
# Apply with:
#   terraform workspace select prod
#   terraform apply -var-file=environments/prod/terraform.tfvars
# ─────────────────────────────────────────────────────────────────────────────

project_id       = "alti-analytics-prod"
primary_region   = "us-central1"
secondary_region = "europe-west1"
environment      = "prod"
tenant_id        = "alti-platform-prod"

# Cloud Spanner: 3 nodes (3000 PU) for production throughput
spanner_processing_units = 3000

# AlloyDB: 16 vCPU primary + 8 vCPU × 3 read pool nodes
alloydb_cpu_count = 16

# Cloud Run: never scale to zero in production
cloud_run_min_instances = 2
cloud_run_max_instances = 1000

# BigQuery: multi-region for global resilience
bigquery_location = "US"

# Security: VPC Service Controls + CMEK mandatory in prod
enable_vpc_service_controls = true
enable_cmek                 = true

# Alerting
alert_email = "oncall@alti.ai"
