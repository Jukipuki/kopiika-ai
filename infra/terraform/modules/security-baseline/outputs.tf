output "cloudtrail_log_group_arn" {
  description = "CloudWatch log group receiving the CloudTrail stream. Other modules that want to add metric filters can target this group."
  value       = aws_cloudwatch_log_group.cloudtrail.arn
}

output "security_alarms_topic_arn" {
  description = "SNS topic receiving CIS alarm notifications. Wire CloudWatch alarms in other modules to this topic for a single notification surface."
  value       = aws_sns_topic.security_alarms.arn
}
