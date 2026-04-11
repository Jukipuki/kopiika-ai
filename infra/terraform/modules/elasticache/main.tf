locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-subnet"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${local.name_prefix}-redis-subnet"
  }
}

resource "aws_elasticache_replication_group" "main" {
  # Story 5.1 AC #4: converted from aws_elasticache_cluster to
  # aws_elasticache_replication_group so that at_rest_encryption_enabled
  # can be set (the cluster resource does not support that argument).
  # Still a single-node topology (num_cache_clusters = 1) — no replica,
  # no failover — matching the prior aws_elasticache_cluster footprint.
  # Enabling at-rest encryption on an existing cluster forces a replacement.
  # Safe here because Redis holds only ephemeral state (Celery broker,
  # SSE progress, short-lived job hashes). Operators: review plan output.
  replication_group_id = "${local.name_prefix}-redis"
  description          = "${local.name_prefix} Redis (Celery broker, SSE, job status)"

  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.node_type
  num_cache_clusters   = 1
  port                 = 6379
  parameter_group_name = "default.redis7"

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [var.redis_security_group_id]

  transit_encryption_enabled = true
  at_rest_encryption_enabled = true

  automatic_failover_enabled = false
  multi_az_enabled           = false

  snapshot_retention_limit = var.environment == "prod" ? 7 : 0

  # Dev only: apply parameter changes immediately rather than in the
  # maintenance window. Staging and prod respect the maintenance window.
  apply_immediately = var.environment == "dev"

  tags = {
    Name = "${local.name_prefix}-redis"
  }
}
