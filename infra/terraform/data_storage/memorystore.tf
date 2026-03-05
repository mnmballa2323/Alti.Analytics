# Provision a highly available Google Cloud Memorystore (Redis) instance.
# Used by the FastAPI LLM Gateway to instantly serve semantically cached Intelligence 
# for repetitive telemetry signatures (saving Gemini token costs and LLM latency).

resource "google_redis_instance" "cache" {
  name           = "alti-semantic-cache"
  tier           = "STANDARD_HA" # High Availability across zones
  memory_size_gb = 5             # 5GB Memory for standard LLM semantic payload caching
  
  location_id             = var.primary_region_zone_a
  alternative_location_id = var.primary_region_zone_b

  # Security: Enforce in-transit encryption 
  transit_encryption_mode = "SERVER_AUTHENTICATION"

  # Versioning
  redis_version = "REDIS_6_X"
  
  # Network Binding
  authorized_network = google_compute_network.vpc_network.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  # Redis Configuration optimizations for eviction
  redis_configs = {
    maxmemory-policy = "allkeys-lru" # Evict least recently used keys when full
  }

  display_name = "Alti.Analytics LLM Semantic Cache API"
}

# Output the IP to be injected into the LLM Gateway environment variables
output "redis_host" {
  description = "The IP address of the Memorystore Redis Instance."
  value       = google_redis_instance.cache.host
}

output "redis_port" {
  description = "The port of the Memorystore Redis Instance."
  value       = google_redis_instance.cache.port
}
