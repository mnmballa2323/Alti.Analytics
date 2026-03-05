# Security Command Center (SCC) - Continuous Threat Detection
# Routes high-severity threats directly to the Swarm for Autonomous Investigation

# 1. Pub/Sub Topic to receive SCC Findings
resource "google_pubsub_topic" "scc_threat_alerts" {
  name = "scc-threat-alerts-${var.environment}"
}

# 2. SCC Notification Config
# Filters for HIGH or CRITICAL severity active threats (e.g., Malware, Exfiltration, Privilege Escalation)
resource "google_scc_notification_config" "swarm_threat_routing" {
  config_id    = "swarm-autonomous-threat-routing-${var.environment}"
  organization = var.gcp_organization_id
  description  = "Routes critical Security Command Center alerts to the LangGraph Swarm"
  pubsub_topic = google_pubsub_topic.scc_threat_alerts.id

  streaming_config {
    filter = "state = \"ACTIVE\" AND (severity = \"HIGH\" OR severity = \"CRITICAL\")"
  }
}

# 3. Eventarc Trigger (Connecting SCC Pub/Sub to the Swarm Webhook)
# Note: Requires the LLM Gateway application to be deployed as a Cloud Run service receiving Eventarc
resource "google_eventarc_trigger" "scc_to_swarm" {
  name     = "scc-to-swarm-trigger-${var.environment}"
  location = var.gcp_region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.pubsub.topic.v1.messagePublished"
  }
  
  transport {
    pubsub {
      topic = google_pubsub_topic.scc_threat_alerts.name
    }
  }

  destination {
    cloud_run_service {
      service = "llm-gateway-service-${var.environment}" # Points to the LangGraph Swarm
      region  = var.gcp_region
      path    = "/v1/events/anomaly"
    }
  }

  service_account = "alti-eventarc-invoker@${var.project_id}.iam.gserviceaccount.com"
}
