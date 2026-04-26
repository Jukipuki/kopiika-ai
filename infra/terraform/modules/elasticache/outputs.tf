output "endpoint" {
  value = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "connection_url" {
  # ssl_cert_reqs URL param is required by both clients but they disagree
  # on accepted values:
  #   - redis-py sync (Celery via kombu) — accepts both CERT_REQUIRED and
  #     `required`
  #   - redis-py asyncio (FastAPI sessions/SSE) — accepts ONLY lowercase
  #     `required` / `optional` / `none`. Anything else raises
  #     "Invalid SSL Certificate Requirements Flag" at connect time.
  # Use the lowercase form so both work. `required` validates the AWS-
  # managed ElastiCache certificate chain — the secure choice.
  value     = "rediss://:${random_password.redis_auth.result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}?ssl_cert_reqs=required"
  sensitive = true
}

output "auth_token" {
  value     = random_password.redis_auth.result
  sensitive = true
}
