# Identity-Aware Proxy (IAP) - Zero Trust Access
# Protects the Frontend Web Portal from unauthorized internet access

# 1. Enable IAP on the Backend Service (Fronting the Next.js App)
resource "google_compute_backend_service" "web_portal_backend" {
  name                  = "alti-web-portal-backend-${var.environment}"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL"

  # Bind IAP Authentication
  iap {
    enabled              = true
    oauth2_client_id     = var.iap_oauth2_client_id
    oauth2_client_secret = var.iap_oauth2_client_secret
  }
}

# 2. Define Context-Aware Access Policy (BeyondCorp)
# Only allow specific Google Workspace users / Service Accounts to bypass the IAP
resource "google_iap_web_backend_service_iam_binding" "iap_access_binding" {
  project             = data.google_project.current.project_id
  web_backend_service = google_compute_backend_service.web_portal_backend.name
  role                = "roles/iap.httpsResourceAccessor"

  members = [
    # Authorized human engineers
    "group:alti-platform-admins@example.com",
    
    # Authorized Service Accounts (e.g., CI/CD or the Swarm itself)
    "serviceAccount:alti-swarm-operator@${data.google_project.current.project_id}.iam.gserviceaccount.com"
  ]
}

# 3. Global HTTP(S) Load Balancer configuration (Abridged scaffolding)
resource "google_compute_url_map" "default" {
  name            = "alti-url-map-${var.environment}"
  default_service = google_compute_backend_service.web_portal_backend.id
}
