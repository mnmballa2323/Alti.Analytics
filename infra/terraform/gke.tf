# GKE Cluster
resource "google_container_cluster" "primary" {
  name     = "alti-analytics-${var.environment}-gke"
  location = var.gcp_region

  remove_default_node_pool = true
  initial_node_count       = 1

  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.private_subnet.name

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  confidential_nodes {
    enabled = true
  }
}

# Node Pools
resource "google_container_node_pool" "system_pool" {
  name       = "system-pool"
  location   = var.gcp_region
  cluster    = google_container_cluster.primary.name
  node_count = 1

  node_config {
    machine_type = "e2-standard-4"
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}

resource "google_container_node_pool" "app_pool" {
  name       = "app-pool"
  location   = var.gcp_region
  cluster    = google_container_cluster.primary.name
  
  autoscaling {
    total_min_node_count = 1
    total_max_node_count = 10
  }

  node_config {
    machine_type = "n2-standard-8"
    spot         = true
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}

# Confidential Computing Node Pool (AMD SEV)
# Runs the LangGraph Swarm (Memory IN-USE encryption)
resource "google_container_node_pool" "confidential_swarm_pool" {
  name       = "confidential-swarm-pool"
  location   = var.gcp_region
  cluster    = google_container_cluster.primary.name
  
  autoscaling {
    total_min_node_count = 1
    total_max_node_count = 5
  }

  node_config {
    machine_type = "n2d-standard-8" # N2D required for AMD EPYC Confidential Computing
    
    # Force Pods to specifically request this hardened enclave
    taint {
      key    = "confidential-enclave"
      value  = "true"
      effect = "NO_SCHEDULE"
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}
