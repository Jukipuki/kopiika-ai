# Inspector v2: continuous vulnerability scanning of ECR container images
# (Lambda is also supported; not used here). Replaces the basic ECR
# scan-on-push with full Common Vulnerabilities and Exposures (CVE) coverage.

resource "aws_inspector2_enabler" "ecr" {
  account_ids    = [data.aws_caller_identity.current.account_id]
  resource_types = ["ECR"]
}
