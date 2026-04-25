# GuardDuty: continuous threat detection across CloudTrail, VPC Flow Logs,
# DNS logs, and S3 data events. Account-global, ~$5-15/mo for a small footprint.

resource "aws_guardduty_detector" "main" {
  enable                       = true
  finding_publishing_frequency = "FIFTEEN_MINUTES"

  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = false
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = false
        }
      }
    }
  }

  tags = {
    Name = "${local.name_prefix}-guardduty"
  }
}
