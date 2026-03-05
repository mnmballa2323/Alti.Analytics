variable "project_id" {
  description = "The GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "Primary GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the GCP VPC"
  type        = string
  default     = "10.0.0.0/16"
}
