# Google Cloud Key Management Service (KMS) - Sovereign Encryption

# 1. Create a Global Key Ring
resource "google_kms_key_ring" "alti_sovereign_keyring" {
  name     = "alti-sovereign-keyring-${var.environment}"
  location = "global"

  lifecycle {
    prevent_destroy = true # Safeguard against destroying keys encrypting live data
  }
}

# 2. Create the Customer-Managed Encryption Key (CMEK) for BigQuery Data Warehouse
resource "google_kms_crypto_key" "bq_cmek" {
  name            = "alti-bq-cmek-${var.environment}"
  key_ring        = google_kms_key_ring.alti_sovereign_keyring.id
  rotation_period = "7776000s" # Rotate every 90 days

  lifecycle {
    prevent_destroy = true
  }
}

# 3. Create the CMEK for Google Cloud Storage (Data Lakes)
resource "google_kms_crypto_key" "gcs_cmek" {
  name            = "alti-gcs-cmek-${var.environment}"
  key_ring        = google_kms_key_ring.alti_sovereign_keyring.id
  rotation_period = "7776000s"

  lifecycle {
    prevent_destroy = true
  }
}

# 4. Identity & Access Management (IAM) for Keys
# Allow the BigQuery Service Agent to use the CMEK to encrypt/decrypt table data
resource "google_kms_crypto_key_iam_binding" "bq_crypto_binding" {
  crypto_key_id = google_kms_crypto_key.bq_cmek.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"

  members = [
    "serviceAccount:bq-${data.google_project.current.number}@bigquery-encryption.iam.gserviceaccount.com",
  ]
}

# Data source required to get the project number dynamically for service accounts
data "google_project" "current" {
  project_id = var.project_id
}
