# JobApply infrastructure.
#
# The security posture is expressed here rather than left to a runbook: the data
# stores are private, the object bucket blocks public access entirely, and secrets
# come from Secrets Manager rather than from task definitions.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name = "${var.project}-${var.environment}"
}

# --------------------------------------------------------------------- network
module "network" {
  source = "./modules/network"

  name     = local.name
  vpc_cidr = var.vpc_cidr
}

# -------------------------------------------------------------------- datastores
module "database" {
  source = "./modules/database"

  name               = local.name
  subnet_ids         = module.network.private_subnet_ids
  security_group_ids = [module.network.database_security_group_id]
  instance_class     = var.database_instance_class

  # Never publicly reachable, encrypted at rest, backups retained.
  publicly_accessible     = false
  storage_encrypted       = true
  backup_retention_period = 14
  deletion_protection     = var.environment == "production"
}

module "cache" {
  source = "./modules/cache"

  name               = local.name
  subnet_ids         = module.network.private_subnet_ids
  security_group_ids = [module.network.cache_security_group_id]
  node_type          = var.redis_node_type
  transit_encryption = true
}

# ------------------------------------------------------------------------ storage
module "documents" {
  source = "./modules/storage"

  name = "${local.name}-documents"

  # Resumes and screenshots. Private, versioned, encrypted; the API issues
  # short-lived presigned URLs after checking the requester owns the object.
  block_public_access = true
  versioning          = true
  sse_algorithm       = "AES256"
  lifecycle_days      = 365
}

# ------------------------------------------------------------------------ secrets
module "secrets" {
  source = "./modules/secrets"

  name = local.name

  # Values are set out of band; Terraform creates the entries, not their contents.
  secret_names = [
    "SECRET_KEY",
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "STRIPE_SECRET_KEY",
    "GOOGLE_CLIENT_SECRET",
  ]
}

# ------------------------------------------------------------------------ compute
module "services" {
  source = "./modules/services"

  name               = local.name
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  public_subnet_ids  = module.network.public_subnet_ids
  secret_arns        = module.secrets.arns
  bucket_name        = module.documents.bucket_name
  domain_name        = var.domain_name

  services = {
    api = {
      image_key     = "api"
      desired_count = var.api_desired_count
      cpu           = 512
      memory        = 1024
      port          = 8000
      public        = true
      health_path   = "/health"
    }
    worker = {
      image_key     = "worker"
      desired_count = var.worker_desired_count
      cpu           = 512
      memory        = 1024
      public        = false
    }
    automation = {
      # Chromium needs materially more memory than the other services, which is
      # exactly why it is its own task definition.
      image_key     = "automation"
      desired_count = var.automation_desired_count
      cpu           = 1024
      memory        = 3072
      public        = false
    }
    beat = {
      image_key     = "worker"
      desired_count = 1
      cpu           = 256
      memory        = 512
      public        = false
      command       = ["celery", "-A", "jobapply_workers.beat", "beat", "--loglevel=INFO"]
    }
  }
}
