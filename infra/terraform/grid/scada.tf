# infra/terraform/grid/scada.tf
# Epic 27: Autonomous National Infrastructure
# Provisions the secure GKE cluster and VPC firewall rules for the SCADA bridge.
# The SCADA ingestion pods run in an air-gapped, fully isolated GKE namespace.

resource "google_container_cluster" "scada_cluster" {
  name     = "alti-scada-grid-cluster"
  location = var.region
  project  = var.project_id
  
  # Air-gapped SCADA cluster — no public endpoint exposure
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = true
    master_ipv4_cidr_block  = "192.168.100.0/28"
  }
  
  # Dedicated node pool for DNP3/OPC-UA parsing workloads
  node_pool {
    name               = "scada-ingestion-pool"
    initial_node_count = 3
    
    node_config {
      machine_type = "n2-standard-8"
      disk_size_gb = 200
      
      # Workload Identity for secure BigQuery/Pub-Sub writes
      workload_metadata_config {
        mode = "GKE_METADATA"
      }
    }
  }
}

resource "google_compute_firewall" "scada_dnp3_ingress" {
  name    = "alti-scada-dnp3-ingress"
  network = var.vpc_name
  project = var.project_id
  
  allow {
    protocol = "tcp"
    ports    = ["20000"] # DNP3 standard port
  }
  allow {
    protocol = "tcp"
    ports    = ["4840"] # OPC-UA standard port
  }
  
  # Strictly whitelist only known SCADA gateway IPs
  source_ranges = var.scada_gateway_ips
  target_tags   = ["scada-ingestion"]
}
