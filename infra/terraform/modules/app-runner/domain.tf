# Custom domain for the App Runner public endpoint.
# DNS is hosted at Squarespace (not Route 53) for cost reasons — domain
# registration there is ~$10/yr vs Route 53's ~$70/yr. The trade-off is
# manual: App Runner emits a set of validation CNAMEs that need to be
# pasted into Squarespace's DNS panel.
#
# App Runner manages its own ACM certificate internally — no separate
# `aws_acm_certificate` resource is needed (and adding one would just
# linger in PENDING_VALIDATION forever, since App Runner is the only
# service that knows the validation records it's actually using).
#
# Set var.custom_domain to enable. Empty default = no domain (the App
# Runner default `*.<region>.awsapprunner.com` URL keeps working).

resource "aws_apprunner_custom_domain_association" "api" {
  count = var.custom_domain != "" ? 1 : 0

  domain_name = var.custom_domain
  service_arn = aws_apprunner_service.api.arn

  enable_www_subdomain = false
}
