output "endpoint" {
  value = aws_db_instance.main.endpoint
}

output "connection_string" {
  value     = "postgresql://${aws_db_instance.main.username}:${random_password.rds_master.result}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}"
  sensitive = true
}

output "db_name" {
  value = aws_db_instance.main.db_name
}
