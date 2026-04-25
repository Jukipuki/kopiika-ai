# Domain setup — `kopiika.coach` on Squarespace

DNS is hosted at Squarespace (registrar + DNS), App Runner serves the API at `api.kopiika.coach`. ACM (eu-central-1) issues the TLS cert via DNS validation — those validation CNAMEs need to be pasted into Squarespace's DNS panel.

This is a one-time setup per environment. Once the validation CNAMEs are in place, ACM auto-renews the cert without further intervention.

## Why not Route 53

Squarespace registration is ~$10/yr; Route 53 + registration is ~$70/yr. For a solo project the $60/yr difference exceeds the value of full DNS-as-code, and renewal works fine via the DNS panel.

## Procedure

### 1. Register `kopiika.coach` at Squarespace

If not already registered, register at squarespace.com → Domains. Choose default DNS hosting (Squarespace's own).

### 2. Apply Terraform with the domain set

In `environments/prod/terraform.tfvars`, `api_custom_domain = "api.kopiika.coach"` is already set. Run `terraform apply` — this creates:

- `aws_apprunner_custom_domain_association.api` — App Runner provisions an internal ACM cert and emits the validation records via output. The association stays in `pending_certificate_dns_validation` until the records below are pasted into Squarespace.

There is **no separate `aws_acm_certificate` resource** — App Runner manages the cert internally; provisioning a standalone ACM cert was tried and removed (would have lingered PENDING_VALIDATION forever, since App Runner is the only service that knows the validation records it's actually using).

### 3. Read the DNS records to paste

```bash
cd infra/terraform
terraform output -json api_app_runner_dns_records
```

You'll see one record set with two parts:

- **`dns_target`**: the CNAME target your custom domain points at (e.g. `xxx.awsapprunner.com`).
- **`certificate_records`**: 1-3 validation CNAMEs App Runner needs to issue + renew its internal ACM cert.

### 4. Add records in Squarespace

Squarespace → Domains → `kopiika.coach` → DNS Settings → Custom Records.

For each entry in **`certificate_records`**:

- **Host**: the leading `_xxx` part of `name`. Squarespace appends `.kopiika.coach` automatically — strip the trailing `.` and the `.kopiika.coach` suffix before pasting.
- **Type**: `CNAME`
- **Data** (or "Points to"): the full `value` field, including its trailing `.`. Squarespace accepts the dot fine.
- **Priority/TTL**: leave defaults.

For **`dns_target`**:

- **Host**: `api`
- **Type**: `CNAME`
- **Data**: the `dns_target` value (e.g. `xxx.awsapprunner.com`).

Save. Squarespace propagates DNS in 1-15 minutes.

### 5. Verify

```bash
# Should resolve to the App Runner CNAME chain.
dig api.kopiika.coach CNAME

# App Runner status should be "active" (not pending_certificate_dns_validation).
aws apprunner describe-custom-domains \
  --service-arn $(aws apprunner list-services \
    --query "ServiceSummaryList[?ServiceName=='kopiika-prod-api'].ServiceArn" \
    --output text) \
  --region eu-central-1
```

ACM validation typically takes 5-30 minutes after the CNAME is propagating. App Runner custom domain activation takes another 5-15 minutes after that.

### 6. Smoke test

```bash
curl https://api.kopiika.coach/health
```

Should return 200 and the App Runner default health response.

## Renewal

ACM auto-renews 60 days before expiry as long as the validation CNAME stays in Squarespace DNS. Don't delete those records.

## Removing the domain

To revert to the default `*.awsapprunner.com` URL: set `api_custom_domain = ""` and `terraform apply`. Then delete the records in Squarespace. The ACM cert is destroyed by Terraform but Squarespace records are not — they're harmless leftovers but worth removing.
