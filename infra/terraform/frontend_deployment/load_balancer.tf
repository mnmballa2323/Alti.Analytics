# Global External HTTP(S) Load Balancer to front the Cloud Run service.
# This enables Cloud CDN (Global Edge Caching) and Cloud Armor (WAF).

# ---------------------------------------------------------
# Serverless Network Endpoint Group (NEG)
# ---------------------------------------------------------
resource "google_compute_region_network_endpoint_group" "cloudrun_neg" {
  name                  = "alti-web-portal-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.primary_region
  
  cloud_run {
    service = google_cloud_run_service.web_portal.name
  }
}

# ---------------------------------------------------------
# Backend Service (with Cloud CDN enabled)
# ---------------------------------------------------------
resource "google_compute_backend_service" "web_portal_backend" {
  name                  = "alti-web-portal-backend"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL"

  # Enable Cloud CDN for extreme TTFB reduction on static Next.js assets
  enable_cdn = true
  cdn_policy {
    cache_mode               = "CACHE_ALL_STATIC"
    default_ttl              = 3600
    client_ttl               = 3600
    max_ttl                  = 86400
    serve_while_stale        = 86400
  }

  # Attach Cloud Armor WAF Policy
  security_policy = google_compute_security_policy.cloud_armor_policy.id

  backend {
    group = google_compute_region_network_endpoint_group.cloudrun_neg.id
  }
}

# ---------------------------------------------------------
# Cloud Armor Web Application Firewall (WAF)
# ---------------------------------------------------------
resource "google_compute_security_policy" "cloud_armor_policy" {
  name        = "alti-global-waf-policy"
  description = "Cloud Armor policy mitigating OWASP Top 10 and DDoS"

  # Rule 1: Allow all by default (unless caught by specific deny rules below)
  rule {
    action   = "allow"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default Allow"
  }

  # Rule 2: SQL Injection & Cross-Site Scripting (XSS) Protection
  rule {
    action   = "deny(403)"
    priority = "1000"
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('sqli-v33-stable') || evaluatePreconfiguredExpr('xss-v33-stable')"
      }
    }
    description = "Block SQLi and XSS attacks"
  }
}

# ---------------------------------------------------------
# URL Map & Frontend Routing
# ---------------------------------------------------------
resource "google_compute_url_map" "default" {
  name            = "alti-global-url-map"
  default_service = google_compute_backend_service.web_portal_backend.id
}

resource "google_compute_target_https_proxy" "default" {
  name             = "alti-https-proxy"
  url_map          = google_compute_url_map.default.id
  ssl_certificates = [google_compute_managed_ssl_certificate.default.id]
}

resource "google_compute_global_forwarding_rule" "default" {
  name                  = "alti-global-frontend"
  target                = google_compute_target_https_proxy.default.id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL"
}

# ---------------------------------------------------------
# Managed SSL Certificate
# ---------------------------------------------------------
resource "google_compute_managed_ssl_certificate" "default" {
  name = "alti-managed-cert"
  
  managed {
    domains = ["app.alti-analytics.com"] # Prod Domain
  }
}
