output "endpoint" {
  value = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "connection_url" {
  value     = "rediss://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}"
  sensitive = true
}
