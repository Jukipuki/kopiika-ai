locals {
  name_prefix = "${var.project_name}-${var.environment}"
  use_ses     = var.ses_sender_arn != ""
}

resource "aws_cognito_user_pool" "main" {
  name = "${local.name_prefix}-user-pool"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  username_configuration {
    case_sensitive = false
  }

  password_policy {
    minimum_length                   = 14
    require_uppercase                = true
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  # OPTIONAL = users may enroll TOTP but most won't. Regulated workload
  # arguably wants MFA "ON", but pre-launch user base is one operator with
  # an authenticator already wired out of band. Revisit when there are real
  # customers — see TD-116 for the path to enforced MFA.
  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration {
    enabled = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  dynamic "email_configuration" {
    for_each = local.use_ses ? [1] : []
    content {
      email_sending_account = "DEVELOPER"
      source_arn            = var.ses_sender_arn
    }
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  tags = {
    Name = "${local.name_prefix}-user-pool"
  }
}

# Frontend app client (public, no secret, SRP auth for browser + public Cognito API calls)
resource "aws_cognito_user_pool_client" "frontend" {
  name         = "${local.name_prefix}-frontend-client"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  access_token_validity  = var.access_token_validity
  refresh_token_validity = var.refresh_token_validity
  id_token_validity      = var.access_token_validity

  token_validity_units {
    access_token  = "minutes"
    refresh_token = "days"
    id_token      = "minutes"
  }

  prevent_user_existence_errors = "ENABLED"
}

# Backend app client (confidential, with secret, for admin API calls)
resource "aws_cognito_user_pool_client" "backend" {
  name         = "${local.name_prefix}-backend-client"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = true

  explicit_auth_flows = [
    "ALLOW_ADMIN_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  access_token_validity  = var.access_token_validity
  refresh_token_validity = var.refresh_token_validity
  id_token_validity      = var.access_token_validity

  token_validity_units {
    access_token  = "minutes"
    refresh_token = "days"
    id_token      = "minutes"
  }

  prevent_user_existence_errors = "ENABLED"
}
