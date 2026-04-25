# Secrets bootstrap — post-apply manual steps

Most secrets are populated by Terraform from resource outputs (RDS connection string, Cognito IDs, S3 bucket name). A few hold operator-supplied values that Terraform deliberately seeds with placeholders — you populate them after the first `terraform apply`.

The placeholders use a `lifecycle.ignore_changes = [secret_string]` pattern, so subsequent `terraform apply` runs won't overwrite operator-rotated values. See [modules/secrets/main.tf](../../infra/terraform/modules/secrets/main.tf).

All secrets are encrypted with the per-env CMK `alias/kopiika-prod-secrets`.

## Secrets that need manual values

### `kopiika/prod/llm-api-keys`

**What:** Provider API keys for LLM clients used by the cross-provider matrix and any non-Bedrock code paths.

**Why manual:** API keys come from Anthropic / OpenAI / etc., not from AWS. They never live in Terraform state (the secret is seeded with `{}`).

**Set values:**

```bash
export AWS_PROFILE=personal
export AWS_REGION=eu-central-1

aws secretsmanager put-secret-value \
  --region $AWS_REGION \
  --secret-id kopiika/prod/llm-api-keys \
  --secret-string '{
    "ANTHROPIC_API_KEY": "sk-ant-...",
    "OPENAI_API_KEY": "sk-..."
  }'
```

**Verify:**

```bash
aws secretsmanager get-secret-value --region $AWS_REGION \
  --secret-id kopiika/prod/llm-api-keys --query SecretString --output text \
  | jq 'keys'
```

### `kopiika/prod/chat-canaries`

**What:** Three random tokens used by the chat prompt-leak detector (Story 10.4b). The model never sees these directly; the detector scans for them in outputs to flag prompt extraction attempts.

**Why manual:** Real canaries must never live in Terraform state plaintext. The terraform-seeded values are `REPLACE_ME_VIA_ROTATION_RUNBOOK_*` placeholders satisfying the 24-char minimum so the secret resource creates cleanly.

**Generate + set values:**

```bash
A=$(openssl rand -hex 16)
B=$(openssl rand -hex 16)
C=$(openssl rand -hex 16)

aws secretsmanager put-secret-value \
  --region $AWS_REGION \
  --secret-id kopiika/prod/chat-canaries \
  --secret-string "$(jq -n --arg a "$A" --arg b "$B" --arg c "$C" \
    '{canary_a: $a, canary_b: $b, canary_c: $c}')"
```

**Verify the loader picks them up:** restart the App Runner service or wait for the next pod cycle. Hit the `/admin/canary-status` endpoint (or whatever the loader exposes) to confirm the values are non-placeholder.

### `kopiika/prod/ses` (optional)

**What:** SES sender configuration. Currently `ses_sender_email = ""` in `prod.tfvars`, which means SES is effectively disabled and Cognito uses its default email service. If/when you verify a real sender domain in SES:

1. Verify the domain in SES (`aws ses verify-domain-identity`) and complete DKIM setup at your DNS registrar.
2. Set `ses_sender_email = "noreply@kopiika.coach"` in `prod.tfvars`.
3. `terraform apply` — this updates the secret, attaches the SES policy, and re-wires Cognito's `email_configuration` to use SES (`use_ses = true` local in [modules/cognito/main.tf](../../infra/terraform/modules/cognito/main.tf)).

## Secrets populated by Terraform (no manual steps)

These are listed for completeness — verify after first apply:

- `kopiika/prod/database` — full connection string (includes Story 5.1 CMK-encrypted password)
- `kopiika/prod/redis` — `rediss://:<auth_token>@<host>:6379` (Phase C added the auth token)
- `kopiika/prod/cognito` — user pool + client IDs + backend client secret
- `kopiika/prod/s3` — bucket name + region

```bash
# Spot-check that Terraform actually wrote sensible values:
for secret in database redis cognito s3; do
  echo "--- $secret ---"
  aws secretsmanager get-secret-value --region $AWS_REGION \
    --secret-id "kopiika/prod/$secret" --query SecretString --output text \
    | jq 'keys'
done
```

## Rotation

For now, all secrets are rotated manually. See [TD-113](../tech-debt.md) for the planned Secrets Manager rotation Lambda for the DB password.

For LLM API keys: rotate at the provider, then `aws secretsmanager put-secret-value` with the new key. App Runner / Celery workers pick up the change on next secret read (typically next request, since the cache is short). For zero-downtime rotation, deploy a new image (release runbook) so workers explicitly restart.

## What if I forget a secret?

The app fails to start. App Runner / ECS task logs will say "secret X not found" or "no API key for provider Y". Set the secret per the steps above and trigger a redeploy.
