# Deploy the Next.js Web Portal to Google Cloud Run
# This ensures autoscaling from 0 to N based on real-time traffic volume.

resource "google_cloud_run_service" "web_portal" {
  name     = "alti-web-portal"
  location = var.primary_region

  template {
    spec {
      containers {
        # Assuming the image is built and pushed via GitHub Actions to Artifact Registry
        image = "us-docker.pkg.dev/${var.project_id}/alti-repo/web-portal:latest"
        
        resources {
          limits = {
            cpu    = "2000m"
            memory = "4Gi"
          }
        }

        # Next.js specific environment variables for SSR
        env {
          name  = "NEXT_PUBLIC_SWARM_API_URL"
          value = "https://api.alti-analytics.com"
        }
        
        env {
          name  = "NODE_ENV"
          value = "production"
        }
      }
      
      # For ultra-low latency, allow the CPU to stay allocated between requests 
      # (reduces cold start delays for SSR / Generative UI)
      timeout_seconds = 30
      service_account_name = google_service_account.cloud_run_sa.email
    }
    
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale"      = "1" # Maintain 1 warm instance
        "autoscaling.knative.dev/maxScale"      = "100"
        "run.googleapis.com/cpu-throttling"     = "false"
        "run.googleapis.com/vpc-access-connector" = google_vpc_access_connector.serverless_connector.name
        "run.googleapis.com/vpc-access-egress"    = "all-traffic"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  # Ensure the VPC & Serverless connector exists first
  depends_on = [google_vpc_access_connector.serverless_connector]
}

# Allow unauthenticated invocation (since Identity-Aware Proxy handles Auth at the LB tier)
resource "google_cloud_run_service_iam_member" "public_access" {
  service  = google_cloud_run_service.web_portal.name
  location = google_cloud_run_service.web_portal.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Service account for Cloud Run
resource "google_service_account" "cloud_run_sa" {
  account_id   = "alti-web-portal-sa"
  display_name = "Cloud Run Service Account for Alti Web Portal"
}
