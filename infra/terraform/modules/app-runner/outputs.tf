output "service_url" {
  value = aws_apprunner_service.api.service_url
}

output "service_arn" {
  value = aws_apprunner_service.api.arn
}

output "custom_domain" {
  description = "Configured custom domain (if any). Empty when var.custom_domain is unset."
  value       = var.custom_domain
}

# Single set of DNS records for Squarespace, all emitted by App Runner:
#   - dns_target: the CNAME the operator points var.custom_domain at
#   - certificate_records: validation CNAMEs App Runner needs to issue/renew
#     its internal ACM cert.
# All paste into Squarespace's DNS panel after first apply. See
# docs/runbooks/domain-setup.md.
output "app_runner_dns_records" {
  description = "App Runner-issued DNS targets for the custom domain (the CNAME you point your domain at, plus its own validation records)."
  value = var.custom_domain != "" ? {
    dns_target          = aws_apprunner_custom_domain_association.api[0].dns_target
    certificate_records = aws_apprunner_custom_domain_association.api[0].certificate_validation_records
  } : null
}
