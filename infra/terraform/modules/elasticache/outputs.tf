output "endpoint" {
  value = aws_elasticache_cluster.main.cache_nodes[0].address
}

output "connection_url" {
  value     = "rediss://${aws_elasticache_cluster.main.cache_nodes[0].address}:${aws_elasticache_cluster.main.cache_nodes[0].port}"
  sensitive = true
}
