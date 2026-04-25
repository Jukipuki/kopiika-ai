output "endpoint" {
  value = aws_db_instance.main.endpoint
}

output "connection_string" {
  # Async driver suffix is required: app/core/database.py uses
  # SQLAlchemy create_async_engine, which raises
  # "asyncio extension requires an async driver" on bare postgresql://
  # (which SQLAlchemy defaults to psycopg2). Sync paths (alembic, Celery
  # workers) derive the psycopg2 form via SYNC_DATABASE_URL property in
  # app/core/config.py.
  value     = "postgresql+asyncpg://${aws_db_instance.main.username}:${random_password.rds_master.result}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}"
  sensitive = true
}

output "db_name" {
  value = aws_db_instance.main.db_name
}
