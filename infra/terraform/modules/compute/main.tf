# infra/terraform/modules/compute/main.tf
# Cloud Run services (one per Epic service), Cloud Tasks queues,
# Cloud Scheduler jobs, Pub/Sub topics + subscriptions

locals {
  # All Alti.Analytics microservices — one Cloud Run service each
  services = {
    "api-gateway"         = { cpu = "2", memory = "2Gi",  port = 8080, concurrency = 200 }
    "swarm-orchestrator"  = { cpu = "4", memory = "8Gi",  port = 8080, concurrency = 50  }
    "nl2sql"              = { cpu = "4", memory = "8Gi",  port = 8080, concurrency = 100 }
    "knowledge-graph"     = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 100 }
    "cost-intelligence"   = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 80  }
    "streaming-analytics" = { cpu = "4", memory = "8Gi",  port = 8080, concurrency = 200 }
    "data-catalog"        = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 100 }
    "time-travel"         = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 80  }
    "collaboration"       = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 150 }
    "mlops"               = { cpu = "4", memory = "8Gi",  port = 8080, concurrency = 50  }
    "federated-analytics" = { cpu = "4", memory = "8Gi",  port = 8080, concurrency = 50  }
    "industry-templates"  = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 100 }
    "storytelling"        = { cpu = "4", memory = "8Gi",  port = 8080, concurrency = 80  }
    "scenario-engine"     = { cpu = "4", memory = "8Gi",  port = 8080, concurrency = 100 }
    "voice-multimodal"    = { cpu = "4", memory = "8Gi",  port = 8080, concurrency = 80  }
    "data-quality"        = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 100 }
    "multilingual"        = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 200 }
    "global-compliance"   = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 100 }
    "data-sovereignty"    = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 100 }
    "currency-intelligence"={ cpu = "2", memory = "4Gi",  port = 8080, concurrency = 200 }
    "regional-models"     = { cpu = "8", memory = "16Gi", port = 8080, concurrency = 50  }
    "edge-intelligence"   = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 100 }
    "vertex-agent"        = { cpu = "4", memory = "8Gi",  port = 8080, concurrency = 100 }
    "spanner-alloydb"     = { cpu = "2", memory = "4Gi",  port = 8080, concurrency = 200 }
  }
}

resource "google_cloud_run_v2_service" "services" {
  for_each = local.services
  name     = "alti-${var.environment}-${each.key}"
  location = var.primary_region
  project  = var.project_id

  ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${var.primary_region}-docker.pkg.dev/${var.project_id}/alti/alti-${each.key}:latest"

      resources {
        limits = {
          cpu    = each.value.cpu
          memory = each.value.memory
        }
        cpu_idle          = false
        startup_cpu_boost = true
      }

      ports {
        container_port = each.value.port
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "REGION"
        value = var.primary_region
      }
      # Mount secrets from Secret Manager
      dynamic "env" {
        for_each = var.secrets
        content {
          name = upper(replace(env.key, "-", "_"))
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
    }

    max_instance_request_concurrency = each.value.concurrency

    annotations = {
      "autoscaling.knative.dev/minScale" = tostring(var.min_instances)
      "autoscaling.knative.dev/maxScale" = tostring(var.max_instances)
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ── Cloud Tasks queues ────────────────────────────────────────────────────────
locals {
  task_queues = [
    "tenant-onboarding",
    "report-generation",
    "erasure-requests",
    "breach-notifications",
    "pipeline-remediation",
    "edge-sync",
    "scenario-compute",
    "model-retraining",
  ]
}

resource "google_cloud_tasks_queue" "queues" {
  for_each = toset(local.task_queues)
  name     = "alti-${var.environment}-${each.value}"
  location = var.primary_region
  project  = var.project_id

  rate_limits {
    max_concurrent_dispatches = 100
    max_dispatches_per_second = 500
  }

  retry_config {
    max_attempts  = 5
    max_backoff   = "3600s"
    min_backoff   = "10s"
    max_doublings = 5
  }
}

# ── Cloud Scheduler jobs ──────────────────────────────────────────────────────
locals {
  scheduler_jobs = {
    "fx-rate-refresh"       = { schedule = "*/5 * * * *",  description = "Refresh FX rates every 5m" }
    "data-quality-check"    = { schedule = "*/5 * * * *",  description = "Data quality checks every 5m" }
    "model-drift-check"     = { schedule = "0 */6 * * *",  description = "Edge model drift detection every 6h" }
    "report-scheduled"      = { schedule = "0 7 * * 1-5",  description = "Scheduled reports — weekdays 7am" }
    "catalog-refresh"       = { schedule = "0 */2 * * *",  description = "Data catalog refresh every 2h" }
    "privacy-budget-reset"  = { schedule = "0 0 1 * *",    description = "Reset monthly privacy budgets" }
    "spanner-backup"        = { schedule = "0 2 * * *",    description = "Daily Spanner backup at 2am UTC" }
    "cost-forecast"         = { schedule = "0 6 * * *",    description = "Daily cost forecast at 6am UTC" }
  }
}

resource "google_cloud_scheduler_job" "jobs" {
  for_each    = local.scheduler_jobs
  name        = "alti-${var.environment}-${each.key}"
  description = each.value.description
  schedule    = each.value.schedule
  time_zone   = "UTC"
  region      = var.primary_region
  project     = var.project_id

  http_target {
    uri         = "https://alti-${var.environment}-api-gateway-${var.project_id}.run.app/internal/scheduler/${each.key}"
    http_method = "POST"
    oidc_token {
      service_account_email = var.service_account_email
    }
  }

  retry_config {
    retry_count = 3
  }
}

# ── Pub/Sub topics ────────────────────────────────────────────────────────────
locals {
  pubsub_topics = [
    "fraud-events",
    "iot-sensors",
    "api-latency",
    "live-revenue",
    "hospital-vitals",
    "edge-sync-events",
    "compliance-alerts",
    "model-predictions",
  ]
}

resource "google_pubsub_topic" "topics" {
  for_each = toset(local.pubsub_topics)
  name     = "alti-${var.environment}-${each.value}"
  project  = var.project_id

  message_storage_policy {
    allowed_persistence_regions = [var.primary_region]
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "google_pubsub_subscription" "subscriptions" {
  for_each = toset(local.pubsub_topics)
  name     = "alti-${var.environment}-${each.value}-sub"
  topic    = google_pubsub_topic.topics[each.key].name
  project  = var.project_id

  ack_deadline_seconds       = 60
  message_retention_duration = "86400s"  # 24h

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.topics["compliance-alerts"].id
    max_delivery_attempts = 5
  }
}

output "service_urls" {
  value = { for k, v in google_cloud_run_v2_service.services : k => v.uri }
}

variable "project_id"            {}
variable "primary_region"        {}
variable "environment"           {}
variable "vpc_connector_id"      {}
variable "service_account_email" {}
variable "secrets"               { type = map(string) }
variable "min_instances"         { default = 1 }
variable "max_instances"         { default = 100 }
