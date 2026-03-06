# infra/terraform/variables.tf

variable "project_id" {
  description = "GCP project ID for the Alti.Analytics deployment"
  type        = string
}

variable "primary_region" {
  description = "Primary GCP region"
  type        = string
  default     = "us-central1"
}

variable "secondary_region" {
  description = "Secondary GCP region for DR and multi-region HA"
  type        = string
  default     = "europe-west1"
}

variable "environment" {
  description = "Deployment environment: prod | staging | dev"
  type        = string
  validation {
    condition     = contains(["prod", "staging", "dev"], var.environment)
    error_message = "environment must be prod, staging, or dev."
  }
}

variable "tenant_id" {
  description = "Primary tenant identifier"
  type        = string
  default     = "alti-platform"
}

variable "spanner_processing_units" {
  description = "Cloud Spanner processing units (1000 = 1 node)"
  type        = number
  default     = 1000
}

variable "alloydb_cpu_count" {
  description = "vCPUs for AlloyDB primary instance"
  type        = number
  default     = 8
}

variable "cloud_run_min_instances" {
  type    = number
  default = 1
}

variable "cloud_run_max_instances" {
  type    = number
  default = 100
}

variable "bigquery_location" {
  type    = string
  default = "US"
}

variable "enable_vpc_service_controls" {
  description = "Enable VPC Service Controls data perimeter"
  type        = bool
  default     = true
}

variable "enable_cmek" {
  description = "Enable Customer-Managed Encryption Keys"
  type        = bool
  default     = true
}

variable "alert_email" {
  description = "Email for monitoring alerts and breach notifications"
  type        = string
}
