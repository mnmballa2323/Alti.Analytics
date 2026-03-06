# infra/terraform/modules/data/main.tf
# BigQuery datasets + column-level ACLs, Cloud Storage buckets (CMEK),
# Cloud Spanner instance, AlloyDB cluster, Memorystore Redis

# ── BigQuery datasets ─────────────────────────────────────────────────────────
locals {
  bq_datasets = {
    "alti_raw"        = "Raw ingested data — all sources"
    "alti_analytics"  = "Transformed analytics-ready tables"
    "alti_ml"         = "Feature stores and ML training data"
    "alti_streaming"  = "Real-time streaming window tables"
    "alti_audit"      = "Compliance audit logs"
    "alti_federated"  = "Federated analytics cross-org views"
  }
}

resource "google_bigquery_dataset" "datasets" {
  for_each                   = local.bq_datasets
  dataset_id                 = "${each.key}_${replace(var.environment, "-", "_")}"
  friendly_name              = each.value
  location                   = var.bigquery_location
  project                    = var.project_id
  delete_contents_on_destroy = false

  default_encryption_configuration {
    kms_key_name = var.kms_key_id
  }

  access {
    role          = "OWNER"
    special_group = "projectOwners"
  }
  access {
    role          = "READER"
    special_group = "projectReaders"
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ── Cloud Storage buckets ─────────────────────────────────────────────────────
locals {
  buckets = {
    "alti-models"      = { location = var.primary_region,   purpose = "ML model artifacts and weights" }
    "alti-exports"     = { location = var.primary_region,   purpose = "Dashboard exports PDF/PPTX/CSV" }
    "alti-backups"     = { location = "US",                 purpose = "Cross-region database backups" }
    "alti-tts-audio"   = { location = var.primary_region,   purpose = "TTS audio output files" }
    "alti-doc-uploads" = { location = var.primary_region,   purpose = "Document Intelligence uploads" }
    "alti-iceberg"     = { location = var.primary_region,   purpose = "Apache Iceberg table snapshots" }
    "alti-edge-sync"   = { location = var.primary_region,   purpose = "Edge agent sync payloads" }
  }
}

resource "google_storage_bucket" "buckets" {
  for_each                    = local.buckets
  name                        = "${each.key}-${var.project_id}-${var.environment}"
  location                    = each.value.location
  project                     = var.project_id
  force_destroy               = false
  uniform_bucket_level_access = true

  encryption {
    default_kms_key_name = var.kms_key_id
  }

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition { age = 365 }
    action    { type = "SetStorageClass" storage_class = "NEARLINE" }
  }

  lifecycle_rule {
    condition { age = 1095 }
    action    { type = "SetStorageClass" storage_class = "COLDLINE" }
  }

  labels = {
    purpose     = replace(each.value.purpose, " ", "-")
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ── Cloud Spanner ─────────────────────────────────────────────────────────────
resource "google_spanner_instance" "alti" {
  name             = "alti-${var.environment}-spanner"
  config           = var.environment == "prod" ? "nam-eur-asia1" : "regional-${var.primary_region}"
  display_name     = "Alti Analytics Spanner [${var.environment}]"
  processing_units = var.spanner_processing_units
  project          = var.project_id

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "google_spanner_database" "alti" {
  instance = google_spanner_instance.alti.name
  name     = "alti-main"
  project  = var.project_id

  ddl = [
    # Banking ledger
    <<-DDL
    CREATE TABLE BankAccounts (
      AccountId     STRING(36)  NOT NULL,
      TenantId      STRING(36)  NOT NULL,
      CustomerId    STRING(36)  NOT NULL,
      AccountType   STRING(20)  NOT NULL,
      CurrencyCode  STRING(3)   NOT NULL,
      BalanceUnits  INT64       NOT NULL,
      Status        STRING(20)  NOT NULL,
      CreatedAt     TIMESTAMP   NOT NULL OPTIONS (allow_commit_timestamp=true),
      UpdatedAt     TIMESTAMP   NOT NULL OPTIONS (allow_commit_timestamp=true),
    ) PRIMARY KEY (TenantId, AccountId)
    DDL
    ,
    <<-DDL
    CREATE TABLE Transactions (
      TenantId      STRING(36)  NOT NULL,
      AccountId     STRING(36)  NOT NULL,
      TransactionId STRING(36)  NOT NULL,
      Amount        INT64       NOT NULL,
      Type          STRING(20)  NOT NULL,
      Status        STRING(20)  NOT NULL,
      CreatedAt     TIMESTAMP   NOT NULL OPTIONS (allow_commit_timestamp=true),
    ) PRIMARY KEY (TenantId, AccountId, TransactionId),
    INTERLEAVE IN PARENT BankAccounts ON DELETE CASCADE
    DDL
    ,
    # Healthcare records
    <<-DDL
    CREATE TABLE Patients (
      TenantId      STRING(36)  NOT NULL,
      PatientId     STRING(36)  NOT NULL,
      MRN           STRING(50)  NOT NULL,
      EncryptedPII  BYTES(MAX)  NOT NULL,
      DateOfBirth   DATE        NOT NULL,
      Status        STRING(20)  NOT NULL,
      CreatedAt     TIMESTAMP   NOT NULL OPTIONS (allow_commit_timestamp=true),
    ) PRIMARY KEY (TenantId, PatientId)
    DDL
    ,
    <<-DDL
    CREATE TABLE ClinicalEvents (
      TenantId      STRING(36)  NOT NULL,
      PatientId     STRING(36)  NOT NULL,
      EventId       STRING(36)  NOT NULL,
      EventType     STRING(50)  NOT NULL,
      DiagnosisCode STRING(20),
      Facility      STRING(100),
      CreatedAt     TIMESTAMP   NOT NULL OPTIONS (allow_commit_timestamp=true),
    ) PRIMARY KEY (TenantId, PatientId, EventId),
    INTERLEAVE IN PARENT Patients ON DELETE CASCADE
    DDL
    ,
    # Global inventory
    <<-DDL
    CREATE TABLE Products (
      TenantId      STRING(36)  NOT NULL,
      ProductId     STRING(36)  NOT NULL,
      SKU           STRING(100) NOT NULL,
      Name          STRING(255) NOT NULL,
      Region        STRING(10)  NOT NULL,
      UpdatedAt     TIMESTAMP   NOT NULL OPTIONS (allow_commit_timestamp=true),
    ) PRIMARY KEY (TenantId, ProductId)
    DDL
    ,
    <<-DDL
    CREATE TABLE InventoryLevels (
      TenantId      STRING(36)  NOT NULL,
      ProductId     STRING(36)  NOT NULL,
      LocationId    STRING(36)  NOT NULL,
      Quantity      INT64       NOT NULL,
      ReservedQty   INT64       NOT NULL DEFAULT (0),
      UpdatedAt     TIMESTAMP   NOT NULL OPTIONS (allow_commit_timestamp=true),
    ) PRIMARY KEY (TenantId, ProductId, LocationId),
    INTERLEAVE IN PARENT Products ON DELETE CASCADE
    DDL
    ,
    # Indexes
    "CREATE INDEX BankAccounts_ByCustomer ON BankAccounts (TenantId, CustomerId)",
    "CREATE INDEX Transactions_ByDate ON Transactions (TenantId, CreatedAt DESC)",
    "CREATE INDEX ClinicalEvents_ByType ON ClinicalEvents (TenantId, EventType, CreatedAt DESC)",
  ]

  encryption_config {
    kms_key_name = var.kms_key_id
  }
}

# ── AlloyDB ───────────────────────────────────────────────────────────────────
resource "google_alloydb_cluster" "alti" {
  provider   = google-beta
  cluster_id = "alti-${var.environment}-alloydb"
  location   = var.primary_region
  project    = var.project_id

  network_config {
    network = var.vpc_network_id
  }

  encryption_config {
    kms_key_name = var.kms_key_id
  }

  automated_backup_policy {
    enabled  = true
    location = var.primary_region
    weekly_schedule {
      days_of_week = ["MONDAY", "WEDNESDAY", "FRIDAY"]
      start_times { hours = 2; minutes = 0 }
    }
    quantity_based_retention {
      count = 14
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "google_alloydb_instance" "primary" {
  provider      = google-beta
  cluster       = google_alloydb_cluster.alti.name
  instance_id   = "alti-${var.environment}-primary"
  instance_type = "PRIMARY"

  machine_config {
    cpu_count = var.alloydb_cpu_count
  }

  database_flags = {
    "pg_stat_statements.track"     = "ALL"
    "log_min_duration_statement"   = "1000"
    "alloydb.enable_pgvector"      = "ON"   # Vector search for embeddings
    "max_connections"              = "1000"
    "shared_buffers"               = "8GB"
    "effective_cache_size"         = "24GB"
  }
}

resource "google_alloydb_instance" "read_pool" {
  provider      = google-beta
  cluster       = google_alloydb_cluster.alti.name
  instance_id   = "alti-${var.environment}-read-pool"
  instance_type = "READ_POOL"

  machine_config {
    cpu_count = var.alloydb_cpu_count / 2
  }

  read_pool_config {
    node_count = var.environment == "prod" ? 3 : 1
  }
}

# ── Memorystore Redis (CRDT pub/sub + caching) ───────────────────────────────
resource "google_redis_instance" "alti" {
  name               = "alti-${var.environment}-redis"
  tier               = var.environment == "prod" ? "STANDARD_HA" : "BASIC"
  memory_size_gb     = var.environment == "prod" ? 8 : 2
  region             = var.primary_region
  auth_enabled       = true
  transit_encryption_mode = "SERVER_AUTHENTICATION"
  redis_version      = "REDIS_7_0"
  location_id        = "${var.primary_region}-a"
  alternative_location_id = var.environment == "prod" ? "${var.primary_region}-b" : null
  authorized_network = var.vpc_network_id
  project            = var.project_id

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

output "spanner_instance_id" { value = google_spanner_instance.alti.name }
output "spanner_database_id" { value = google_spanner_database.alti.name }
output "alloydb_cluster_id"  { value = google_alloydb_cluster.alti.name }
output "alloydb_primary_ip"  { value = google_alloydb_instance.primary.ip_address }
output "redis_host"          { value = google_redis_instance.alti.host }
output "bq_datasets"         { value = { for k, v in google_bigquery_dataset.datasets : k => v.dataset_id } }
output "gcs_buckets"         { value = { for k, v in google_storage_bucket.buckets : k => v.name } }

variable "project_id"             {}
variable "primary_region"         {}
variable "secondary_region"       {}
variable "bigquery_location"      { default = "US" }
variable "environment"            {}
variable "kms_key_id"             {}
variable "private_services_range" {}
variable "vpc_network_id"         { default = "" }
variable "spanner_processing_units" { default = 1000 }
variable "alloydb_cpu_count"      { default = 8 }
