# Vertex AI Vector Search (formerly Matching Engine)

# 1. Provide the underlying Google Cloud Storage Bucket for vector indices
resource "google_storage_bucket" "vector_staging" {
  name          = "alti-analytics-${var.environment}-vector-staging"
  location      = "US" # Multi-region
  force_destroy = true
  
  uniform_bucket_level_access = true
}

# 2. Define the Vertex AI Vector Search Index
resource "google_vertex_ai_index" "omni_memory" {
  display_name = "omni-swam-memory-index"
  description  = "High-dimension index backing the LangGraph Swarm RAG capabilities"
  region       = var.gcp_region
  labels       = { env = var.environment }
  
  metadata {
    contents_delta_uri = "gs://${google_storage_bucket.vector_staging.name}/embeddings"
    config {
      dimensions = 768 # TextEmbedding-Gecko standard
      approximate_neighbors_count = 100
      distance_measure_type       = "DOT_PRODUCT_DISTANCE"
      feature_norm_type           = "UNIT_L2_NORM"
      
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count    = 500
          leaf_nodes_to_search_percent = 5
        }
      }
    }
  }
}

# 3. Create a Managed Endpoint for real-time semantic retrieval
resource "google_vertex_ai_index_endpoint" "memory_endpoint" {
  display_name = "omni-swarm-memory-endpoint"
  description  = "The endpoint our LLM Gateway queries to perform semantic search"
  region       = var.gcp_region
  network      = "projects/${var.project_id}/global/networks/default" # Assuming default VPC for scaffold
}

# 4. Bind the Index to the Endpoint
resource "google_vertex_ai_index_endpoint_deployed_index" "deployed_omni_memory" {
  index_endpoint = google_vertex_ai_index_endpoint.memory_endpoint.id
  index          = google_vertex_ai_index.omni_memory.id
  
  deployed_index_id = "omni_memory_deployed_v1"
  display_name      = "Active Omni Memory Replica"
  
  dedicated_resources {
    machine_spec {
      machine_type = "e2-standard-2" # Scalable instance for production RAG
    }
    min_replica_count = 1
    max_replica_count = 3
  }
}
