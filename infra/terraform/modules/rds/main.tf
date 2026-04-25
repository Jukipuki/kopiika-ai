locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${local.name_prefix}-db-subnet"
  }
}

resource "aws_db_parameter_group" "postgres16" {
  name   = "${local.name_prefix}-postgres16-params"
  family = "postgres16"

  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }

  tags = {
    Name = "${local.name_prefix}-postgres16-params"
  }
}

resource "random_password" "rds_master" {
  length  = 32
  special = false
}

# Per-service KMS CMK for RDS.
# Hardened beyond the original Story 5.1 AC #1 (which pinned aws/rds, the AWS-
# managed key) — a customer-managed key gives us key-policy control, the ability
# to revoke by destroying the key, and audit visibility independent of AWS.
resource "aws_kms_key" "rds" {
  description             = "${local.name_prefix} RDS encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${local.name_prefix}-rds"
  }
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${local.name_prefix}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

resource "aws_db_instance" "main" {
  identifier = "${local.name_prefix}-rds"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.allocated_storage * 2

  db_name  = "kopiika_db"
  username = "kopiika_admin"
  password = random_password.rds_master.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_security_group_id]
  parameter_group_name   = aws_db_parameter_group.postgres16.name

  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn
  storage_type      = "gp3"

  backup_retention_period = var.backup_retention_period
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"
  copy_tags_to_snapshot   = true

  performance_insights_enabled          = var.environment == "prod"
  performance_insights_retention_period = var.environment == "prod" ? 7 : null
  performance_insights_kms_key_id       = var.environment == "prod" ? aws_kms_key.rds.arn : null

  deletion_protection = var.environment == "prod"
  multi_az            = var.environment == "prod"
  publicly_accessible = false
  skip_final_snapshot = var.environment == "dev"

  final_snapshot_identifier = var.environment != "dev" ? "${local.name_prefix}-final-snapshot" : null

  tags = {
    Name = "${local.name_prefix}-rds"
  }
}

# Post-apply assertion: RDS is encrypted with our CMK, not an AWS-managed key.
# Successor to the Story 5.1 AC #1 check (which pinned aws/rds).
check "rds_uses_customer_managed_kms" {
  assert {
    condition     = aws_db_instance.main.kms_key_id == aws_kms_key.rds.arn
    error_message = "RDS instance ${aws_db_instance.main.identifier} is not encrypted with the per-service CMK."
  }
}
