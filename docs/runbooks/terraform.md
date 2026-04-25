# Terraform — local workflow

Terraform runs **locally**, not in CI. For a single-developer regulated project, the value of CI-driven plan/apply (team coordination, plan-as-PR-comment) is low and the cost (provisioning a broad-permission CI role + reviewing the role's policy + state-bucket policy carve-outs) is high. Local-only is cleaner.

`tfsec.yml` still runs static security analysis on every PR touching `infra/**`.

## Prerequisites

- AWS CLI configured with `AWS_PROFILE=personal` (account `573562677570`)
- Terraform `>= 1.10` (S3 native locking requires 1.10+)
- Read-write access to S3 bucket `kopiika-terraform-state` (eu-central-1)

## Standard flow

```bash
cd infra/terraform

export AWS_PROFILE=personal

# Initialize (only needed after backend.tf or provider changes).
terraform init

# Plan against prod tfvars. Always read the diff before applying.
terraform plan -var-file=environments/prod/terraform.tfvars -out=/tmp/tfplan

# If the plan looks right, apply the saved plan.
terraform apply /tmp/tfplan

# Verify state matches.
terraform state list
```

The state bucket is hardened (versioning + lifecycle + deny-non-TLS + deny-non-encrypted PUT). See [state-bucket.md](state-bucket.md).

## Common operations

### View what's deployed

```bash
terraform state list
terraform state show <resource_address>
```

### Target a single module / resource

```bash
terraform plan -var-file=environments/prod/terraform.tfvars \
  -target=module.s3 -out=/tmp/tfplan
```

Use sparingly — targeted applies create state drift over time.

### Refresh state without applying

```bash
terraform refresh -var-file=environments/prod/terraform.tfvars
```

### Recover from a stuck S3 lock

S3 native locking writes a `.tflock` object. If a `terraform apply` dies mid-run, the lock can stick:

```bash
aws s3 rm s3://kopiika-terraform-state/terraform.tfstate.tflock --region eu-central-1
```

Only do this if you're certain no other apply is running.

## What NOT to do

- **Never `terraform destroy` against prod.** RDS has `deletion_protection = true` so it would fail anyway, but other resources (S3 access logs, CloudTrail logs, Cognito user pool) would be lost.
- **Never `terraform state rm` to "fix" drift.** If a resource is in state but doesn't exist in AWS, fix the AWS side or use `terraform import` — never silently remove from state. Same goes for `taint`.
- **Never apply without a saved plan.** Always `-out=/tmp/tfplan` then apply the file. Otherwise the plan you saw isn't necessarily the plan that runs.
- **Never commit `terraform.tfstate*` files.** State lives in S3. The `infra/terraform/.gitignore` should already exclude these.

## When to escalate to Phase D-style CI

If the project ever grows to >1 developer or a deploy needs to happen during off-hours via Slack approval, add `terraform-plan.yml` (PR-time) and `terraform-apply.yml` (manual workflow_dispatch with required reviewers). Until then, local is right.
