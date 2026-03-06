# infra/terraform/modules/ai/main.tf
# Vertex AI: Model Registry, Endpoints, Agent Builder datastores,
# Workbench instance, Artifact Registry for container images

# ── Artifact Registry ────────────────────────────────────────────────────────
resource "google_artifact_registry_repository" "alti" {
  repository_id = "alti-${var.environment}"
  location      = var.primary_region
  format        = "DOCKER"
  project       = var.project_id
  description   = "Alti Analytics container images [${var.environment}]"

  cleanup_policies {
    id     = "keep-last-10"
    action = "KEEP"
    most_recent_versions { keep_count = 10 }
  }
}

# ── Vertex AI Workbench ───────────────────────────────────────────────────────
resource "google_workbench_instance" "alti" {
  provider = google-beta
  name     = "alti-${var.environment}-workbench"
  location = "${var.primary_region}-a"
  project  = var.project_id

  gce_setup {
    machine_type = var.environment == "prod" ? "n1-standard-8" : "n1-standard-4"
    accelerator_configs {
      type       = "NVIDIA_TESLA_T4"
      core_count = 1
    }
    boot_disk {
      disk_size_gb = 200
      disk_type    = "PD_SSD"
    }
    metadata = {
      "terraform" = "true"
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ── Vertex AI Model Registry endpoints ───────────────────────────────────────
locals {
  model_endpoints = [
    "nl2sql-production",
    "churn-risk-production",
    "fraud-detection-production",
    "anomaly-detection-production",
    "readmission-risk-production",
    "demand-forecast-production",
  ]
}

resource "google_vertex_ai_endpoint" "endpoints" {
  for_each     = toset(local.model_endpoints)
  name         = "alti-${var.environment}-${each.value}"
  display_name = "Alti ${each.value} [${var.environment}]"
  location     = var.primary_region
  project      = var.project_id

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ── Vertex AI Agent Builder: Data Stores ─────────────────────────────────────
resource "google_discovery_engine_data_store" "catalog" {
  provider                    = google-beta
  project                     = var.project_id
  location                    = "global"
  data_store_id               = "alti-${var.environment}-catalog"
  display_name                = "Alti Data Catalog — Enterprise Search"
  industry_vertical           = "GENERIC"
  content_config              = "CONTENT_REQUIRED"
  solution_types              = ["SOLUTION_TYPE_SEARCH"]
  create_advanced_site_search = false

  document_processing_config {
    default_parsing_config {
      digital_parsing_config {}
    }
  }
}

resource "google_discovery_engine_data_store" "knowledge" {
  provider                    = google-beta
  project                     = var.project_id
  location                    = "global"
  data_store_id               = "alti-${var.environment}-knowledge"
  display_name                = "Alti Knowledge Graph — Agent Grounding"
  industry_vertical           = "GENERIC"
  content_config              = "CONTENT_REQUIRED"
  solution_types              = ["SOLUTION_TYPE_CHAT"]
  create_advanced_site_search = false
}

# ── Vertex AI Search App ──────────────────────────────────────────────────────
resource "google_discovery_engine_search_engine" "alti" {
  provider       = google-beta
  engine_id      = "alti-${var.environment}-search"
  collection_id  = "default_collection"
  location       = "global"
  display_name   = "Alti Enterprise Search"
  project        = var.project_id
  data_store_ids = [google_discovery_engine_data_store.catalog.data_store_id]

  search_engine_config {
    search_tier    = "SEARCH_TIER_ENTERPRISE"
    search_add_ons = ["SEARCH_ADD_ON_LLM"]
  }

  common_config {
    company_name = "Alti Analytics"
  }
}

# ── Cloud Monitoring: Alerting policies ──────────────────────────────────────
resource "google_monitoring_notification_channel" "email" {
  display_name = "Alti Ops Email"
  type         = "email"
  project      = var.project_id
  labels = {
    email_address = var.alert_email
  }
}

resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "[${upper(var.environment)}] High Cloud Run Error Rate"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Error rate > 1%"
    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" metric.label.response_code_class!=\"2xx\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.01
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields    = ["resource.labels.service_name"]
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]

  alert_strategy {
    auto_close = "86400s"
  }
}

resource "google_monitoring_alert_policy" "spanner_latency" {
  display_name = "[${upper(var.environment)}] Spanner High Latency"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Spanner p99 latency > 500ms"
    condition_threshold {
      filter          = "metric.type=\"spanner.googleapis.com/api/request_latencies\" resource.type=\"spanner_instance\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 500
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_PERCENTILE_99"
        cross_series_reducer = "REDUCE_MAX"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

output "artifact_registry_url" { value = "${var.primary_region}-docker.pkg.dev/${var.project_id}/alti-${var.environment}" }
output "workbench_url"         { value = google_workbench_instance.alti.proxy_uri }
output "catalog_datastore_id"  { value = google_discovery_engine_data_store.catalog.data_store_id }
output "knowledge_datastore_id"{ value = google_discovery_engine_data_store.knowledge.data_store_id }
output "search_engine_id"      { value = google_discovery_engine_search_engine.alti.engine_id }
output "endpoint_ids"          { value = { for k, v in google_vertex_ai_endpoint.endpoints : k => v.name } }

variable "project_id"     {}
variable "primary_region" {}
variable "environment"    {}
variable "alert_email"    { default = "" }
