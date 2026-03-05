# Cloud SQL (PostgreSQL)
resource "google_sql_database_instance" "postgres" {
  name             = "alti-analytics-${var.environment}-pg"
  database_version = "POSTGRES_15"
  region           = var.gcp_region

  settings {
    tier = "db-custom-8-32768" # 8 vCPU, 32GB RAM
    
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }
    
    backup_configuration {
      enabled    = true
      start_time = "03:00"
    }

    # High availability for production
    availability_type = var.environment == "prod" ? "REGIONAL" : "ZONAL"
  }
  
  deletion_protection = var.environment == "prod" ? true : false
}

resource "google_sql_database" "database" {
  name     = "altianalytics"
  instance = google_sql_database_instance.postgres.name
}
