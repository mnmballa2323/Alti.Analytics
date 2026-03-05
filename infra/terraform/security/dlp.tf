# infra/terraform/security/dlp.tf

# Epic 18: Generative Zero-Touch Governance
# Natively binds Google Cloud Data Loss Prevention (DLP) to the Alti.Analytics 
# Dataflow pipelines and LangGraph Swarm for autonomous PII redaction.

resource "google_data_loss_prevention_inspect_template" "enterprise_pii_template" {
  parent = "projects/${var.project_id}/locations/global"
  description = "Mandatory PII/PHI redaction template for the Alti.Analytics Omniverse"
  display_name = "Global PII Detection"

  inspect_config {
    info_types {
      name = "EMAIL_ADDRESS"
    }
    info_types {
      name = "CREDIT_CARD_NUMBER"
    }
    info_types {
      name = "US_SOCIAL_SECURITY_NUMBER"
    }
    info_types {
      name = "PHONE_NUMBER"
    }
    info_types {
      name = "AU_MEDICARE_NUMBER" # Example of global compliance
    }
    
    min_likelihood = "LIKELY"
    
    limits {
      max_findings_per_request = 100
    }
  }
}

resource "google_data_loss_prevention_deidentify_template" "enterprise_redaction_template" {
  parent = "projects/${var.project_id}/locations/global"
  description = "Global Redaction rules substituting sensitive bytes with safe tokens."
  display_name = "Global PII Redaction"

  deidentify_config {
    info_type_transformations {
      transformations {
        info_types { name = "CREDIT_CARD_NUMBER" }
        primitive_transformation {
          replace_config {
            new_value {
              string_value = "[REDACTED_FINANCIAL_PAN]"
            }
          }
        }
      }
      transformations {
        info_types { name = "US_SOCIAL_SECURITY_NUMBER" }
        primitive_transformation {
          replace_with_info_type_config {}
        }
      }
    }
  }
}
