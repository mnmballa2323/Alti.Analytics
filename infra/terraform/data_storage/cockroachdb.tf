# CockroachDB - Globally Distributed SQL
# Replaces centralized Postgres/AlloyDB to provide synchronously replicated
# LangGraph Memory State across GCP, AWS, and Azure.

terraform {
  required_providers {
    cockroach = {
      source  = "cockroachdb/cockroach"
      version = "~> 1.0"
    }
  }
}

provider "cockroach" {
  # Authentication is handled via COCKROACH_API_KEY environment variable
}

# 1. Multi-Cloud CockroachDB Dedicated Cluster
resource "cockroach_cluster" "omni_state" {
  name           = "alti-omni-state-${var.environment}"
  cloud_provider = "GCP" # Base cloud, but nodes exist across all three
  cockroach_version = "v23.2"

  dedicated {
    storage_gib = 500
    machine_type = "m6gd.4xlarge" # High memory/storage throughput instances
  }

  # Multi-Region / Multi-Cloud Topology
  # Synchronous replication means a write must be acknowledged by a majority 
  # of these regions before returning to the Swarm.
  regions = [
    {
      name       = var.gcp_region # e.g., us-central1 (GCP)
      node_count = 3
    },
    {
      name       = var.aws_region # e.g., us-east-1 (AWS)
      node_count = 3
    },
    {
      name       = "eastus2"      # Azure
      node_count = 3
    }
  ]
}

# 2. Database Definition
resource "cockroach_database" "swarm_memory" {
  name       = "swarm_memory"
  cluster_id = cockroach_cluster.omni_state.id
}

# 3. SQL User for LangGraph Checkpointer
resource "cockroach_sql_user" "langgraph_operator" {
  name       = "langgraph_operator"
  cluster_id = cockroach_cluster.omni_state.id
  password   = var.cockroach_operator_password
}
