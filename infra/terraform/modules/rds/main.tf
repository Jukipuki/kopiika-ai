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

# Story 5.1 AC #1: pin the RDS KMS key to the AWS-managed alias so the
# compliance documentation in architecture.md is code-verifiable, not just
# "whatever AWS defaults to today". `alias/aws/rds` is the default when
# storage_encrypted = true, so this is a no-op in plan output — but it
# makes the claim explicit and protected against future AWS default drift.
data "aws_kms_alias" "rds" {
  name = "alias/aws/rds"
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
  storage_type      = "gp3"

  backup_retention_period = var.backup_retention_period
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  multi_az            = var.environment == "prod"
  publicly_accessible = false
  skip_final_snapshot = var.environment == "dev"

  final_snapshot_identifier = var.environment != "dev" ? "${local.name_prefix}-final-snapshot" : null

  tags = {
    Name = "${local.name_prefix}-rds"
  }
}

# Story 5.1 AC #1: post-apply assertion that the RDS instance is encrypted
# with the AWS-managed `aws/rds` key. Uses a Terraform `check` block (TF 1.5+)
# so the compliance claim in architecture.md is code-verifiable without
# needing to set `kms_key_id` on the resource directly (which would be
# ForceNew on an existing instance and trigger a destructive replacement).
check "rds_uses_aws_managed_kms" {
  assert {
    condition     = aws_db_instance.main.kms_key_id == data.aws_kms_alias.rds.target_key_arn
    error_message = "RDS instance ${aws_db_instance.main.identifier} is not encrypted with the aws/rds managed KMS key. AC #1 requires AWS-managed key."
  }
}
