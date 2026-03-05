# AWS Elastic Kubernetes Service (EKS) - Node Fleet
# Stretches the Alti.Analytics Swarm into Amazon Web Services for Active-Active survivability.

provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key
}

# 1. IAM Role for EKS Cluster
resource "aws_iam_role" "alti_eks_cluster_role" {
  name = "alti-eks-cluster-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "alti_eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.alti_eks_cluster_role.name
}

# 2. VPC for EKS (Simplified Abstraction)
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "alti-aws-vpc-${var.environment}"
  cidr = "10.1.0.0/16" 

  azs             = ["${var.aws_region}a", "${var.aws_region}b"]
  private_subnets = ["10.1.1.0/24", "10.1.2.0/24"]
  public_subnets  = ["10.1.101.0/24", "10.1.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true
}

# 3. EKS Cluster Definition
resource "aws_eks_cluster" "primary" {
  name     = "alti-analytics-${var.environment}-eks"
  role_arn = aws_iam_role.alti_eks_cluster_role.arn

  vpc_config {
    subnet_ids = module.vpc.private_subnets
  }

  depends_on = [
    aws_iam_role_policy_attachment.alti_eks_cluster_policy
  ]
}

# 4. Swarm Node Group (Equivalent to GKE App Pool)
resource "aws_eks_node_group" "swarm_nodes" {
  cluster_name    = aws_eks_cluster.primary.name
  node_group_name = "alti-swarm-nodes"
  node_role_arn   = aws_iam_role.alti_eks_worker_role.arn
  subnet_ids      = module.vpc.private_subnets

  scaling_config {
    desired_size = 2
    max_size     = 10
    min_size     = 1
  }

  instance_types = ["m5.2xlarge"] # Equivalent to 8 vCPU

  # taint {
  #   key    = "confidential-enclave"
  #   value  = "true"
  #   effect = "NO_SCHEDULE"
  # } # Optional: Apply Nitro Enclaves if AMD SEV is unavailable

  depends_on = [
    aws_iam_role_policy_attachment.alti_eks_worker_policy,
    aws_iam_role_policy_attachment.alti_eks_cni_policy,
    aws_iam_role_policy_attachment.alti_ecr_read_only
  ]
}

# 5. Worker IAM Role Data (Abridged)
resource "aws_iam_role" "alti_eks_worker_role" {
  name = "alti-eks-worker-role-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "alti_eks_worker_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.alti_eks_worker_role.name
}
resource "aws_iam_role_policy_attachment" "alti_eks_cni_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.alti_eks_worker_role.name
}
resource "aws_iam_role_policy_attachment" "alti_ecr_read_only" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.alti_eks_worker_role.name
}
