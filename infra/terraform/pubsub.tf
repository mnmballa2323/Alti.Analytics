# Cloud Pub/Sub
resource "google_pubsub_topic" "events" {
  name = "alti-analytics-${var.environment}-events-v1"

  message_retention_duration = "86400s" # 1 day

  # Message storage policy for data locality if needed
  message_storage_policy {
    allowed_persistence_regions = [
      var.gcp_region,
    ]
  }
}

resource "google_pubsub_subscription" "flink_processor" {
  name  = "alti-analytics-${var.environment}-flink-sub"
  topic = google_pubsub_topic.events.name

  ack_deadline_seconds = 60
  
  expiration_policy {
    ttl = "" # Never expire
  }
  
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  enable_message_ordering    = true
  enable_exactly_once_delivery = true
}

# Dead Letter Topic
resource "google_pubsub_topic" "events_dlq" {
  name = "alti-analytics-${var.environment}-events-dlq"
}
