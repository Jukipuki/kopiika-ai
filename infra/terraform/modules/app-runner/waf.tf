# WAFv2 web ACL fronting the App Runner public endpoint.
# Three rule groups: AWS-managed CommonRuleSet (OWASP-style), KnownBadInputs
# (well-known exploit signatures), and a per-IP rate limit.

resource "aws_wafv2_web_acl" "app_runner" {
  name        = "${local.name_prefix}-api-waf"
  description = "Public WAF for ${local.name_prefix} API"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"

        # CommonRuleSet's default body-size cap is 8 KB, which blocks any
        # file upload to /api/v1/uploads. Demote this single sub-rule to
        # COUNT — metrics + samples still recorded, but no block. The rest
        # of CommonRuleSet (XSS, SQLi, traversal, etc.) stays in BLOCK.
        # Upload-size discipline is enforced upstream (FastAPI multipart
        # limits) and downstream (S3 object size, KMS quotas).
        rule_action_override {
          name = "SizeRestrictions_BODY"
          action_to_use {
            count {}
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-waf-common"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-waf-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "RateLimitPerIP"
    priority = 3

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-waf-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name_prefix}-waf"
    sampled_requests_enabled   = true
  }

  tags = {
    Name = "${local.name_prefix}-api-waf"
  }
}

resource "aws_wafv2_web_acl_association" "app_runner" {
  resource_arn = aws_apprunner_service.api.arn
  web_acl_arn  = aws_wafv2_web_acl.app_runner.arn
}
