# BigQuery Dataset
resource "google_bigquery_dataset" "analytics_dw" {
  dataset_id                  = "alti_analytics_${var.environment}"
  friendly_name               = "Alti Analytics Enterprise DWH"
  description                 = "Primary database for Alti.Analytics structured reporting and ML serving"
  location                    = "US" # Multi-region US
  
  # Default table expiration set to 0 for unlimited
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
EOF
}
