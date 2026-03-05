# BigQuery Dataset
resource "google_bigquery_dataset" "analytics_dw" {
  dataset_id                  = "alti_analytics_${var.environment}"
  friendly_name               = "Alti Analytics Enterprise DWH"
  description                 = "Primary database for Alti.Analytics structured reporting and ML serving"
  location                    = "US" # Multi-region US
  
  # Default table expiration set to 0 for unlimited
  
  default_encryption_configuration {
    kms_key_name = google_kms_crypto_key.bq_cmek.id
  }
}

# Example Table (Audit Log)
resource "google_bigquery_table" "audit_log" {
  dataset_id = google_bigquery_dataset.analytics_dw.dataset_id
  table_id   = "audit_log"

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  schema = <<EOF
[
  {
    "name": "timestamp",
    "type": "TIMESTAMP",
    "mode": "REQUIRED",
    "description": "Event time"
  },
  {
    "name": "user_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "ID of user performing action"
  },
  {
    "name": "action",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Action taken"
  }
]
]
EOF
}

# BigQuery Data Transfer Service (DTS) - AWS S3 to BigQuery
# Automatically syncs historical CSV exports from partner S3 buckets
resource "google_bigquery_data_transfer_config" "s3_historical_import" {
  display_name           = "historical-s3-game-logs-import"
  location               = "US"
  data_source_id         = "amazon_s3"
  schedule               = "every 24 hours"
  destination_dataset_id = google_bigquery_dataset.analytics_dw.dataset_id

  params = {
    destination_table_name_template = "legacy_game_logs_{run_date}"
    data_path                       = "s3://partner-sports-historical-data/archives/*.csv"
    access_key_id                   = var.aws_access_key_id
    secret_access_key              = var.aws_secret_access_key
    file_format                     = "CSV"
    max_bad_records                 = "100"
    ignore_unknown_values           = "true"
  }
}
