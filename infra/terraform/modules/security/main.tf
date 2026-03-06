# infra/terraform/modules/security/main.tf
# Cloud KMS (CMEK), IAM service accounts, Workload Identity Federation,
# Cloud Armor WAF policy, Secret Manager secrets, VPC Service Controls

# ── CMEK: Cloud KMS key ring + key ───────────────────────────────────────────
resource "google_kms_key_ring" "alti" {
  name     = "alti-${var.environment}-keyring"
  location = "global"
  project  = var.project_id
}

resource "google_kms_crypto_key" "alti_key" {
  name            = "alti-${var.environment}-key"
  key_ring        = google_kms_key_ring.alti.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }
}

# ── Service accounts ──────────────────────────────────────────────────────────
resource "google_service_account" "cloud_run" {
  account_id   = "alti-${var.environment}-run-sa"
  display_name = "Alti Cloud Run Service Account [${var.environment}]"
  project      = var.project_id
}

resource "google_service_account" "dataflow" {
  account_id   = "alti-${var.environment}-dataflow-sa"
  display_name = "Alti Dataflow Service Account [${var.environment}]"
  project      = var.project_id
}

resource "google_service_account" "vertex" {
  account_id   = "alti-${var.environment}-vertex-sa"
  display_name = "Alti Vertex AI Service Account [${var.environment}]"
  project      = var.project_id
}

resource "google_service_account" "ci_cd" {
  account_id   = "alti-${var.environment}-cicd-sa"
  display_name = "Alti CI/CD Service Account [${var.environment}]"
  project      = var.project_id
}

# ── IAM bindings (least privilege) ───────────────────────────────────────────
locals {
  run_sa_roles = [
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser",
    "roles/spanner.databaseUser",
    "roles/alloydb.databaseUser",
    "roles/secretmanager.secretAccessor",
    "roles/pubsub.publisher",
    "roles/pubsub.subscriber",
    "roles/cloudtasks.enqueuer",
    "roles/aiplatform.user",
    "roles/storage.objectViewer",
    "roles/cloudtrace.agent",
  ]
  vertex_sa_roles = [
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser",
    "roles/aiplatform.serviceAgent",
    "roles/storage.objectAdmin",
  ]
  dataflow_sa_roles = [
    "roles/dataflow.worker",
    "roles/bigquery.dataEditor",
    "roles/pubsub.subscriber",
    "roles/storage.objectAdmin",
  ]
  cicd_sa_roles = [
    "roles/run.developer",
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountUser",
    "roles/cloudbuild.builds.editor",
  ]
}

resource "google_project_iam_member" "run_sa" {
  for_each = toset(local.run_sa_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "vertex_sa" {
  for_each = toset(local.vertex_sa_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.vertex.email}"
}

resource "google_project_iam_member" "dataflow_sa" {
  for_each = toset(local.dataflow_sa_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_project_iam_member" "cicd_sa" {
  for_each = toset(local.cicd_sa_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.ci_cd.email}"
}

# ── Secret Manager ────────────────────────────────────────────────────────────
locals {
  secrets = [
    "gemini-api-key",
    "stripe-api-key",
    "salesforce-client-secret",
    "slack-webhook-url",
    "smtp-password",
    "spanner-connection-string",
    "alloydb-password",
    "redis-auth-string",
  ]
}

resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(local.secrets)
  secret_id = "alti-${var.environment}-${each.value}"
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ── Cloud Armor WAF ──────────────────────────────────────────────────────────
resource "google_compute_security_policy" "waf" {
  name    = "alti-${var.environment}-waf"
  project = var.project_id

  # OWASP Top 10 pre-configured rules
  rule {
    action   = "deny(403)"
    priority = 1000
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('xss-v33-stable')"
      }
    }
    description = "Block XSS attacks"
  }

  rule {
    action   = "deny(403)"
    priority = 1001
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('sqli-v33-stable')"
      }
    }
    description = "Block SQL injection"
  }

  rule {
    action   = "deny(403)"
    priority = 1002
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('rfi-v33-stable')"
      }
    }
    description = "Block Remote File Inclusion"
  }

  rule {
    action   = "deny(403)"
    priority = 1003
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('lfi-v33-stable')"
      }
    }
    description = "Block Local File Inclusion"
  }

  # Rate limiting: 1000 req/min per IP
  rule {
    action   = "throttle"
    priority = 2000
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 1000
        interval_sec = 60
      }
    }
    description = "Rate limit: 1000 req/min per IP"
  }

  # Default allow
  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default allow rule"
  }
}

output "kms_key_id"    { value = google_kms_crypto_key.alti_key.id }
output "run_sa_email"  { value = google_service_account.cloud_run.email }
output "vertex_sa_email" { value = google_service_account.vertex.email }
output "waf_policy_id" { value = google_compute_security_policy.waf.id }
output "secret_ids"    { value = { for k, v in google_secret_manager_secret.secrets : k => v.id } }

variable "project_id"  {}
variable "environment" {}
variable "network_id"  {}
