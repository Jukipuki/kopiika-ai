environment        = "prod"
aws_region         = "eu-central-1"
availability_zones = ["eu-central-1a", "eu-central-1b"]

# RDS
rds_instance_class      = "db.t4g.small"
rds_allocated_storage   = 100
rds_backup_retention_period = 30

# ElastiCache
elasticache_node_type = "cache.t4g.micro"

# App Runner
app_runner_cpu           = "1024"
app_runner_memory        = "2048"
app_runner_min_instances = 1
app_runner_max_instances = 4

# ECS
ecs_cpu           = 512
ecs_memory        = 1024
ecs_desired_count = 1

# Cognito
cognito_access_token_validity  = 15
cognito_refresh_token_validity = 30

# SES
ses_sender_email = ""

# Observability (Story 11.9)
enable_observability_alarms = true
observability_sns_topic_arn = ""
