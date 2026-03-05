# AlloyDB for PostgreSQL (LangGraph Swarm Memory & pgvector storage)

resource "google_alloydb_cluster" "swarm_memory_cluster" {
  cluster_id = "omni-swarm-memory-${var.environment}"
  location   = var.gcp_region
  
  network_config {
    network = "projects/${var.project_id}/global/networks/default"
  }

  automated_backup_policy {
    location      = var.gcp_region
    backup_window = "03:00:00"
    enabled       = true
    
    weekly_schedule {
      days_of_week = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
      start_times {
        hours   = 3
        minutes = 0
        seconds = 0
        nanos   = 0
      }
    }
  }

  initial_user {
    user     = "swarm_admin"
    password = random_password.alloydb_pass.result
  }
}

resource "google_alloydb_instance" "swarm_memory_primary" {
  cluster       = google_alloydb_cluster.swarm_memory_cluster.name
  instance_id   = "omni-swarm-memory-primary-${var.environment}"
  instance_type = "PRIMARY"

  machine_config {
    cpu_count = 2 # Enough for RAG state persistence scaffolding
  }
}

# Generate a strong password securely for the Swarm Admin
resource "random_password" "alloydb_pass" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Optional: Output the connection string IP to be injected into the LLM Gateway
output "alloydb_ip_address" {
  value = google_alloydb_instance.swarm_memory_primary.ip_address
}
