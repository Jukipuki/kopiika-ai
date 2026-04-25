output "endpoint" {
  value = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "connection_url" {
  # Celery + redis-py require ssl_cert_reqs as a URL parameter on rediss://
  # connections (raises ValueError otherwise: "A rediss:// URL must have
  # parameter ssl_cert_reqs ..."). CERT_REQUIRED validates the AWS-managed
  # ElastiCache certificate chain — the secure choice.
  value     = "rediss://:${random_password.redis_auth.result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}?ssl_cert_reqs=CERT_REQUIRED"
  sensitive = true
}

output "auth_token" {
  value     = random_password.redis_auth.result
  sensitive = true
}
