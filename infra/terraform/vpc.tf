# VPC Network
resource "google_compute_network" "vpc" {
  name                    = "alti-analytics-${var.environment}-vpc"
  auto_create_subnetworks = false
}

# Subnets
resource "google_compute_subnetwork" "private_subnet" {
  name          = "alti-analytics-${var.environment}-private"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.gcp_region
  network       = google_compute_network.vpc.id
  
  private_ip_google_access = true
}

resource "google_compute_subnetwork" "data_subnet" {
  name          = "alti-analytics-${var.environment}-data"
  ip_cidr_range = "10.0.2.0/24"
  region        = var.gcp_region
  network       = google_compute_network.vpc.id
  
  private_ip_google_access = true
}

# Cloud NAT for outbound internet from private subnets
resource "google_compute_router" "router" {
  name    = "alti-analytics-${var.environment}-router"
  region  = var.gcp_region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "alti-analytics-${var.environment}-nat"
  router                             = google_compute_router.router.name
  region                             = google_compute_router.router.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
