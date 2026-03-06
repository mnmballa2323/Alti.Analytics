# infra/terraform/main.tf
# ─────────────────────────────────────────────────────────────────────────────
# Epic 75: Terraform Infrastructure as Code — Root Configuration
# Provisions the ENTIRE Alti.Analytics platform on GCP.
# One `terraform apply` deploys everything: networking, compute, data,
# security, and AI infrastructure across prod and staging environments.
#
# Usage:
#   terraform init
#   terraform workspace new prod
#   terraform apply -var-file=environments/prod/terraform.tfvars
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.20"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.20"
    }
  }
  # Remote state in GCS — separate bucket per environment
  backend "gcs" {
    bucket = "alti-terraform-state"
    prefix = "alti-analytics"
  }
}

provider "google" {
  project = var.project_id
  region  = var.primary_region
}

provider "google-beta" {
  project = var.project_id
  region  = var.primary_region
}

# ── Enable required GCP APIs ──────────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each           = toset(local.required_apis)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

locals {
  required_apis = [
    "run.googleapis.com",
    "bigquery.googleapis.com",
    "bigquerystorage.googleapis.com",
    "aiplatform.googleapis.com",
    "discoveryengine.googleapis.com",
    "spanner.googleapis.com",
    "alloydb.googleapis.com",
    "pubsub.googleapis.com",
    "cloudtasks.googleapis.com",
    "cloudscheduler.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "accesscontextmanager.googleapis.com",
    "iam.googleapis.com",
    "cloudkms.googleapis.com",
    "container.googleapis.com",
    "dataflow.googleapis.com",
    "speech.googleapis.com",
    "texttospeech.googleapis.com",
    "translate.googleapis.com",
    "documentai.googleapis.com",
    "redis.googleapis.com",
    "vpcaccess.googleapis.com",
  ]
}

# ── Module wiring ─────────────────────────────────────────────────────────────
module "networking" {
  source           = "./modules/networking"
  project_id       = var.project_id
  primary_region   = var.primary_region
  secondary_region = var.secondary_region
  environment      = var.environment
  depends_on       = [google_project_service.apis]
}

module "security" {
  source      = "./modules/security"
  project_id  = var.project_id
  environment = var.environment
  network_id  = module.networking.network_id
  depends_on  = [module.networking]
}

module "data" {
  source                 = "./modules/data"
  project_id             = var.project_id
  primary_region         = var.primary_region
  secondary_region       = var.secondary_region
  environment            = var.environment
  kms_key_id             = module.security.kms_key_id
  private_services_range = module.networking.private_services_range
  depends_on             = [module.security]
}

module "ai" {
  source         = "./modules/ai"
  project_id     = var.project_id
  primary_region = var.primary_region
  environment    = var.environment
  depends_on     = [module.data]
}

module "compute" {
  source                = "./modules/compute"
  project_id            = var.project_id
  primary_region        = var.primary_region
  environment           = var.environment
  vpc_connector_id      = module.networking.vpc_connector_id
  service_account_email = module.security.run_sa_email
  secrets               = module.security.secret_ids
  depends_on            = [module.ai]
}
