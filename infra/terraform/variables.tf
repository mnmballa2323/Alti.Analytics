variable "project_id" {
  description = "The GCP Project ID"
  type        = string
}

variable "gcp_organization_id" {
  description = "The GCP Organization ID (Required for Security Command Center)"
  type        = string
  default     = "123456789012" # Mock org ID
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

# Cross-Cloud Import Variables (for BigQuery DTS)
variable "aws_access_key_id" {
  description = "AWS IAM Access Key with read permissions to the partner S3 bucket"
  type        = string
  sensitive   = true
  default     = "MOCK_AWS_ACCESS_KEY"
}

variable "aws_secret_access_key" {
  description = "AWS IAM Secret Key with read permissions to the partner S3 bucket"
  type        = string
  sensitive   = true
  default     = "MOCK_AWS_SECRET_KEY"
}

# --- IAP Identity Variables ---
variable "iap_oauth2_client_id" {
  description = "OAuth2 Client ID for Identity-Aware Proxy (BeyondCorp)"
  type        = string
  default     = "MOCK_IAP_CLIENT_ID"
}

variable "iap_oauth2_client_secret" {
  description = "OAuth2 Client Secret for Identity-Aware Proxy (BeyondCorp)"
  type        = string
  sensitive   = true
  default     = "MOCK_IAP_CLIENT_SECRET"
}
