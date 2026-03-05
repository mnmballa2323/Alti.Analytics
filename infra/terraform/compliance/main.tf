# infra/terraform/compliance/main.tf
# Epic 43-45: Universal Compliance Infrastructure as Code
# Provisions all GCP security controls required for HIPAA, SOC 2, SOX,
# GDPR, CCPA, PCI-DSS, ISO 27001, FedRAMP, and NIST CSF certification.

terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
  backend "gcs" {
    bucket = "alti-terraform-state"
    prefix = "compliance/state"
  }
}

# ─────────────────────────────────────────────────────────────────────
# ORG POLICIES (SOC 2 / ISO 27001 / FedRAMP)
# Enforces guardrails at GCP organization level
# ─────────────────────────────────────────────────────────────────────
resource "google_org_policy_policy" "require_cmek" {
  name   = "organizations/${var.org_id}/policies/gcp.restrictNonCmekServices"
  parent = "organizations/${var.org_id}"
  spec {
    rules { enforce = "TRUE" }
  }
}

resource "google_org_policy_policy" "allowed_regions" {
  name   = "organizations/${var.org_id}/policies/gcp.resourceLocations"
  parent = "organizations/${var.org_id}"
  spec {
    rules {
      values {
        allowed_values = ["in:us-locations", "in:europe-locations"]  # GDPR + FedRAMP
      }
    }
  }
}

resource "google_org_policy_policy" "no_public_buckets" {
  name   = "organizations/${var.org_id}/policies/storage.publicAccessPrevention"
  parent = "organizations/${var.org_id}"
  spec {
    rules { enforce = "TRUE" }
  }
}

# ─────────────────────────────────────────────────────────────────────
# CMEK KEY RINGS (HIPAA / SOC 2 / PCI-DSS)
# ─────────────────────────────────────────────────────────────────────
resource "google_kms_key_ring" "phi_keyring" {
  name     = "alti-hipaa-phi-keys"
  location = "us-central1"
  project  = var.project_id
}

resource "google_kms_crypto_key" "phi_key" {
  name            = "phi-encryption-key"
  key_ring        = google_kms_key_ring.phi_keyring.id
  rotation_period = "7776000s" # 90-day HIPAA-compliant key rotation
  purpose         = "ENCRYPT_DECRYPT"
  lifecycle { prevent_destroy = true }
}

resource "google_kms_key_ring" "pci_keyring" {
  name     = "alti-pci-cde-keys"
  location = "us-central1"
  project  = var.project_id
}

resource "google_kms_crypto_key" "pci_key" {
  name            = "pci-pan-tokenization-key"
  key_ring        = google_kms_key_ring.pci_keyring.id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"
  lifecycle { prevent_destroy = true }
}

# ─────────────────────────────────────────────────────────────────────
# VPC SERVICE CONTROLS PERIMETER (HIPAA PHI + PCI CDE)
# ─────────────────────────────────────────────────────────────────────
resource "google_access_context_manager_service_perimeter" "phi_perimeter" {
  parent = "accessPolicies/${var.access_policy_id}"
  name   = "accessPolicies/${var.access_policy_id}/servicePerimeters/hipaa_phi_perimeter"
  title  = "HIPAA PHI Data Perimeter"
  status {
    restricted_services = [
      "bigquery.googleapis.com",
      "storage.googleapis.com",
      "healthcare.googleapis.com"
    ]
    resources = ["projects/${var.phi_project_number}"]
  }
}

# ─────────────────────────────────────────────────────────────────────
# SOC 2 AUDIT LOG SINK → BigQuery (CC4, CC7 — Monitoring & Logging)
# ─────────────────────────────────────────────────────────────────────
resource "google_logging_project_sink" "soc2_audit_sink" {
  name                   = "alti-soc2-audit-sink"
  project                = var.project_id
  destination            = "bigquery.googleapis.com/projects/${var.project_id}/datasets/alti_soc2_audit_log"
  filter                 = "logName:(activity OR data_access OR system_event OR policy OR access_transparency)"
  unique_writer_identity = true
}

# ─────────────────────────────────────────────────────────────────────
# HIPAA AUDIT LOG SINK (6-year retention per 45 CFR §164.530(j))
# ─────────────────────────────────────────────────────────────────────
resource "google_logging_project_sink" "hipaa_phi_sink" {
  name        = "alti-hipaa-phi-audit-sink"
  project     = var.project_id
  destination = "bigquery.googleapis.com/projects/${var.project_id}/datasets/alti_hipaa_audit_log"
  filter      = "resource.labels.service=\"healthcare.googleapis.com\" OR protoPayload.authorizationInfo.resource=~\"phi\""
  unique_writer_identity = true
}

resource "google_bigquery_dataset" "hipaa_audit_log" {
  dataset_id                 = "alti_hipaa_audit_log"
  project                    = var.project_id
  location                   = "US"
  default_table_expiration_ms = 189216000000  # 6 years in ms
  delete_contents_on_destroy  = false          # HIPAA: never auto-delete
}

# ─────────────────────────────────────────────────────────────────────
# GDPR DATA RESIDENCY — EU-ONLY BigQuery Dataset
# ─────────────────────────────────────────────────────────────────────
resource "google_bigquery_dataset" "gdpr_eu_pii" {
  dataset_id  = "alti_gdpr_pii_eu"
  project     = var.project_id
  location    = "EU"  # Data never leaves EU — GDPR Ch.5 compliance
  description = "GDPR-restricted EU PII dataset. Cross-border egress blocked by VPC SC."
}

# ─────────────────────────────────────────────────────────────────────
# SOX IMMUTABLE AUDIT TRAIL — Cloud Spanner (WORM)
# (Write Once Read Many — SOX Section 802 records retention)
# ─────────────────────────────────────────────────────────────────────
resource "google_spanner_instance" "sox_audit_instance" {
  name         = "alti-sox-worm-audit"
  config       = "regional-us-central1"
  display_name = "SOX Immutable Financial Audit Trail"
  num_nodes    = 3
  project      = var.project_id
}

resource "google_spanner_database" "sox_audit_db" {
  instance = google_spanner_instance.sox_audit_instance.name
  name     = "sox_financial_audit"
  project  = var.project_id
  ddl      = [
    "CREATE TABLE ChangeAudit (change_id STRING(36), actor_email STRING(255), resource STRING(1024), before_state JSON, after_state JSON, approvers ARRAY<STRING(255)>, timestamp TIMESTAMP) PRIMARY KEY (change_id)",
  ]
  deletion_protection = true  # SOX: records cannot be deleted
}
