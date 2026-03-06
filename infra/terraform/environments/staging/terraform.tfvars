# infra/terraform/environments/staging/terraform.tfvars
# ─────────────────────────────────────────────────────────────────────────────
# Staging environment — mirrors prod architecture at reduced cost
# ─────────────────────────────────────────────────────────────────────────────

project_id       = "alti-analytics-staging"
primary_region   = "us-central1"
secondary_region = "europe-west1"
environment      = "staging"
tenant_id        = "alti-platform-staging"

# Spanner: 1 node (regional, not multi-region)
spanner_processing_units = 1000

# AlloyDB: 8 vCPU primary + 1 read pool node
alloydb_cpu_count = 8

# Cloud Run: scale-to-zero in staging to save cost
cloud_run_min_instances = 0
cloud_run_max_instances = 20

bigquery_location = "US"

# Security: VPC SC enabled, CMEK enabled
enable_vpc_service_controls = true
enable_cmek                 = true

alert_email = "eng@alti.ai"
