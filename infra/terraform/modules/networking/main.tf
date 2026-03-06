# infra/terraform/modules/networking/main.tf
# VPC, subnets, Cloud NAT, Private Service Access,
# Serverless VPC Connector, and VPC Service Controls

resource "google_compute_network" "alti_vpc" {
  name                    = "alti-${var.environment}-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id
}

resource "google_compute_subnetwork" "primary" {
  name                     = "alti-${var.environment}-primary"
  ip_cidr_range            = "10.0.0.0/20"
  region                   = var.primary_region
  network                  = google_compute_network.alti_vpc.id
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.48.0.0/14"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.52.0.0/20"
  }
  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_subnetwork" "secondary" {
  name                     = "alti-${var.environment}-secondary"
  ip_cidr_range            = "10.1.0.0/20"
  region                   = var.secondary_region
  network                  = google_compute_network.alti_vpc.id
  private_ip_google_access = true
}

# ── Cloud Router + NAT (for outbound from Cloud Run) ─────────────────────────
resource "google_compute_router" "nat_router" {
  name    = "alti-${var.environment}-router"
  region  = var.primary_region
  network = google_compute_network.alti_vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "alti-${var.environment}-nat"
  router                             = google_compute_router.nat_router.name
  region                             = var.primary_region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# ── Private Service Access (for AlloyDB, Spanner private endpoint) ────────────
resource "google_compute_global_address" "private_services" {
  name          = "alti-${var.environment}-psa"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.alti_vpc.id
}

resource "google_service_networking_connection" "private_service_connection" {
  network                 = google_compute_network.alti_vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
}

# ── Serverless VPC Connector (Cloud Run → VPC) ────────────────────────────────
resource "google_vpc_access_connector" "connector" {
  name          = "alti-${var.environment}-connector"
  region        = var.primary_region
  network       = google_compute_network.alti_vpc.name
  ip_cidr_range = "10.8.0.0/28"
  min_instances = 2
  max_instances = 10
}

# ── Firewall rules ────────────────────────────────────────────────────────────
resource "google_compute_firewall" "deny_all_ingress" {
  name      = "alti-${var.environment}-deny-all-ingress"
  network   = google_compute_network.alti_vpc.name
  priority  = 65534
  direction = "INGRESS"
  deny { protocol = "all" }
  source_ranges = ["0.0.0.0/0"]
}

resource "google_compute_firewall" "allow_internal" {
  name      = "alti-${var.environment}-allow-internal"
  network   = google_compute_network.alti_vpc.name
  priority  = 1000
  direction = "INGRESS"
  allow { protocol = "tcp" }
  allow { protocol = "udp" }
  allow { protocol = "icmp" }
  source_ranges = ["10.0.0.0/8"]
}

resource "google_compute_firewall" "allow_health_checks" {
  name      = "alti-${var.environment}-allow-health-checks"
  network   = google_compute_network.alti_vpc.name
  priority  = 1000
  direction = "INGRESS"
  allow { protocol = "tcp" }
  source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
}

output "network_id"             { value = google_compute_network.alti_vpc.id }
output "network_name"           { value = google_compute_network.alti_vpc.name }
output "primary_subnet_id"      { value = google_compute_subnetwork.primary.id }
output "vpc_connector_id"       { value = google_vpc_access_connector.connector.id }
output "private_services_range" { value = google_compute_global_address.private_services.name }

variable "project_id"       {}
variable "primary_region"   {}
variable "secondary_region" {}
variable "environment"      {}
