# Global DNS Routing (AWS Route 53)
# Acts as the omniscient traffic director for the Sovereign Omniverse.
# Balances inbound web traffic and API calls across GCP, AWS, and Azure.

# 1. Primary Public Hosted Zone
resource "aws_route53_zone" "primary_domain" {
  name = "alti-analytics.com"
}

# 2. Latency-Based Routing Policy (The Omniverse Router)
# Directs users to the cloud provider physically closest to them to minimize latency.
# In the event of a provider failure, health checks automatically failover to the surviving clouds.

# --- GCP Endpoint (us-central1) ---
resource "aws_route53_record" "gcp_frontend" {
  zone_id = aws_route53_zone.primary_domain.zone_id
  name    = "app.alti-analytics.com"
  type    = "A"
  ttl     = 60

  # Point to the GCP HTTP(S) Load Balancer IP
  records = [var.gcp_lb_ip]

  set_identifier = "gcp-primary"
  
  latency_routing_policy {
    region = var.aws_region # Route 53 maps external IPs to nearest AWS region equivalents
  }

  health_check_id = aws_route53_health_check.gcp_health.id
}

# --- AWS Endpoint (us-east-1) ---
resource "aws_route53_record" "aws_frontend" {
  zone_id = aws_route53_zone.primary_domain.zone_id
  name    = "app.alti-analytics.com"
  type    = "A"
  
  # Point to the AWS Application Load Balancer (ALB)
  alias {
    name                   = var.aws_alb_dns_name
    zone_id                = var.aws_alb_zone_id
    evaluate_target_health = true
  }

  set_identifier = "aws-secondary"
  
  latency_routing_policy {
    region = var.aws_region
  }
}

# --- Azure Endpoint (East US) ---
resource "aws_route53_record" "azure_frontend" {
  zone_id = aws_route53_zone.primary_domain.zone_id
  name    = "app.alti-analytics.com"
  type    = "A"
  ttl     = 60

  # Point to the Azure Front Door / Application Gateway IP
  records = [var.azure_app_gateway_ip]

  set_identifier = "azure-tertiary"
  
  latency_routing_policy {
    region = "us-east-1" # Azure East US maps roughly to AWS us-east-1
  }

  health_check_id = aws_route53_health_check.azure_health.id
}

# 3. Distributed Health Checks
resource "aws_route53_health_check" "gcp_health" {
  fqdn              = "gcp-origin.alti-analytics.com"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/api/health"
  failure_threshold = "3"
  request_interval  = "10"
}

resource "aws_route53_health_check" "azure_health" {
  fqdn              = "azure-origin.alti-analytics.com"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/api/health"
  failure_threshold = "3"
  request_interval  = "10"
}
