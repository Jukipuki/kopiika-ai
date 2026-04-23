terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "kopiika"
      Environment = var.environment
      ManagedBy   = "terraform"

      # Story 9.7 — cost-allocation tags (activated via
      # infra/terraform/cost-allocation-tags.tf). The lowercase `env` coexists
      # with `Environment` so AWS cost exploration matches architecture.md's
      # naming convention without breaking the existing `Environment` reports.
      # Per-resource `tags` merges override these defaults (e.g. chat resources
      # flip feature="chat" and epic="10" when Story 10.4a lands).
      feature = "ai"
      epic    = "9"
      env     = var.environment
    }
  }
}
