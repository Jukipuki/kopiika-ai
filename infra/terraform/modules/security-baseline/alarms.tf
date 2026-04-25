# SNS topic + CloudWatch metric filters/alarms for the high-signal subset of
# CIS AWS Foundations Benchmark §3.x. The full set is 14 alarms; this picks
# the 7 most useful for a single-developer regulated workload and skips the
# noisy network-change alarms (NACL/route-table/SG/VPC). Re-add later if
# audit pressure requires it.

resource "aws_sns_topic" "security_alarms" {
  name = "${local.name_prefix}-security-alarms"

  tags = {
    Name = "${local.name_prefix}-security-alarms"
  }
}

resource "aws_sns_topic_subscription" "security_alarms_email" {
  count = var.alarm_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.security_alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

locals {
  metric_namespace = "${local.name_prefix}/Security"

  # CIS §3 alarm definitions: each entry produces a metric filter on the
  # CloudTrail log group + an alarm that fires when the metric goes >= 1
  # over a single 5-minute period.
  cis_alarms = {
    "unauthorized-api-calls" = {
      pattern     = "{ ($.errorCode = \"*UnauthorizedOperation\") || ($.errorCode = \"AccessDenied*\") }"
      description = "CIS 3.1 — unauthorized API calls"
    }
    "root-account-use" = {
      pattern     = "{ $.userIdentity.type = \"Root\" && $.userIdentity.invokedBy NOT EXISTS && $.eventType != \"AwsServiceEvent\" }"
      description = "CIS 3.3 — root account use"
    }
    "iam-policy-changes" = {
      pattern     = "{ ($.eventName=DeleteGroupPolicy) || ($.eventName=DeleteRolePolicy) || ($.eventName=DeleteUserPolicy) || ($.eventName=PutGroupPolicy) || ($.eventName=PutRolePolicy) || ($.eventName=PutUserPolicy) || ($.eventName=CreatePolicy) || ($.eventName=DeletePolicy) || ($.eventName=CreatePolicyVersion) || ($.eventName=DeletePolicyVersion) || ($.eventName=AttachRolePolicy) || ($.eventName=DetachRolePolicy) || ($.eventName=AttachUserPolicy) || ($.eventName=DetachUserPolicy) || ($.eventName=AttachGroupPolicy) || ($.eventName=DetachGroupPolicy) }"
      description = "CIS 3.4 — IAM policy changes"
    }
    "cloudtrail-config-changes" = {
      pattern     = "{ ($.eventName = CreateTrail) || ($.eventName = UpdateTrail) || ($.eventName = DeleteTrail) || ($.eventName = StartLogging) || ($.eventName = StopLogging) }"
      description = "CIS 3.5 — CloudTrail configuration changes"
    }
    "console-auth-failures" = {
      pattern     = "{ ($.eventName = ConsoleLogin) && ($.errorMessage = \"Failed authentication\") }"
      description = "CIS 3.6 — console authentication failures"
    }
    "kms-key-disable" = {
      pattern     = "{ ($.eventSource = kms.amazonaws.com) && (($.eventName = DisableKey) || ($.eventName = ScheduleKeyDeletion)) }"
      description = "CIS 3.7 — disabling/scheduling deletion of customer-managed KMS keys"
    }
    "s3-bucket-policy-changes" = {
      pattern     = "{ ($.eventSource = s3.amazonaws.com) && (($.eventName = PutBucketAcl) || ($.eventName = PutBucketPolicy) || ($.eventName = PutBucketCors) || ($.eventName = PutBucketLifecycle) || ($.eventName = PutBucketReplication) || ($.eventName = DeleteBucketPolicy) || ($.eventName = DeleteBucketCors) || ($.eventName = DeleteBucketLifecycle) || ($.eventName = DeleteBucketReplication)) }"
      description = "CIS 3.8 — S3 bucket policy / ACL changes"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "cis" {
  for_each = local.cis_alarms

  name           = "${local.name_prefix}-${each.key}"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = each.value.pattern

  metric_transformation {
    name      = each.key
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "cis" {
  for_each = local.cis_alarms

  alarm_name          = "${local.name_prefix}-${each.key}"
  alarm_description   = each.value.description
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = each.key
  namespace           = local.metric_namespace
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.security_alarms.arn]
  ok_actions    = [aws_sns_topic.security_alarms.arn]

  tags = {
    Name = "${local.name_prefix}-${each.key}"
  }
}
