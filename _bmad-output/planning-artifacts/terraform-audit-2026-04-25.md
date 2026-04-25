# Terraform audit — `infra/terraform/`

**Date:** 2026-04-25
**Auditor role:** Senior AWS solutions architect / Terraform reviewer
**Scope:** `infra/terraform/` (root + 10 modules + 3 env tfvars)
**Framework basis:** AWS Well-Architected (Security + Cost), CIS AWS Foundations Benchmark, FinOps best practices
**Prompt source:** [docs/prompts/terraform-audit-prompt.md](../../docs/prompts/terraform-audit-prompt.md)

---

## Executive summary

The configuration shows clear evidence of intentional engineering — single NAT for cost, gp3 across the board, scoped IAM, S3 deny-non-AES256 + deny-insecure-transport policies, a Bedrock Guardrail with regex'd UA-locale PII, and per-env gating of expensive features. That said, for a *regulated production environment* there are six **Critical** gaps that I'd treat as blockers: (1) no CloudTrail, (2) no VPC Flow Logs, (3) no `deletion_protection` on the prod RDS, (4) no Cognito MFA, (5) ECR is `MUTABLE` + App Runner consumes `:latest` (no digest pin), and (6) the `github_bedrock_ci` OIDC role accepts *any* PR subject in the repo, which is an unauthenticated invoke surface for Bedrock costs. On the cost side, the highest-impact wins are an S3 lifecycle policy (versioning is on, no IA/Glacier transitions, no noncurrent expiration) and an ECR lifecycle policy — both are unbounded today.

---

## Security findings

| Severity | Resource | Issue | Remediation |
|---|---|---|---|
| **Critical** | (missing) | **No CloudTrail** anywhere in the config. Regulated industries require an org/account trail with log-file validation and a dedicated S3 bucket. | Add `aws_cloudtrail` with `enable_log_file_validation = true`, multi-region, KMS-encrypted, S3 destination with deny-delete bucket policy. See snippet below. |
| **Critical** | (missing) | **No VPC Flow Logs** on `aws_vpc.main` ([modules/networking/main.tf:6](../../infra/terraform/modules/networking/main.tf#L6)). Network exfil & lateral-movement signal is invisible. | Add `aws_flow_log` to CloudWatch or S3, traffic_type `ALL`. Snippet below. |
| **Critical** | `aws_db_instance.main` ([modules/rds/main.tf:43](../../infra/terraform/modules/rds/main.tf#L43)) | **No `deletion_protection`** — a `terraform destroy` or accidental `taint` will obliterate the prod DB. `skip_final_snapshot = true` in dev makes the blast radius worse. | Set `deletion_protection = var.environment == "prod"`. In-place update, no recreation. |
| **Critical** | `aws_cognito_user_pool.main` ([modules/cognito/main.tf:6](../../infra/terraform/modules/cognito/main.tf#L6)) | **MFA not configured** — `mfa_configuration` defaults to `OFF`. For a regulated app gating customer financial data, this is a policy violation. | `mfa_configuration = "OPTIONAL"` (or `"ON"`) + `software_token_mfa_configuration { enabled = true }`. In-place update. |
| **Critical** | `aws_ecr_repository.backend` ([main.tf:86](../../infra/terraform/main.tf#L86)) + `aws_apprunner_service.api` ([modules/app-runner/main.tf:142](../../infra/terraform/modules/app-runner/main.tf#L142)) + ECS task-defs ([modules/ecs/main.tf:133](../../infra/terraform/modules/ecs/main.tf#L133), [modules/ecs/main.tf:231](../../infra/terraform/modules/ecs/main.tf#L231)) | `image_tag_mutability = "MUTABLE"` AND consumers reference `:latest` / `:beat-latest`. An attacker (or rogue CI run) overwriting `:latest` silently swaps prod runtime. Defeats the whole point of immutable artifacts. | Set `image_tag_mutability = "IMMUTABLE"`, deploy by `:sha-<git-sha>` tags only, and reference by digest (`@sha256:...`) where possible. Note: the deploy workflow already pins `:beat-${sha}` per the comment at modules/ecs/main.tf:228 — the `:beat-latest` *bootstrap tag* is the gap. |
| **Critical** | `aws_iam_role.github_bedrock_ci` ([modules/ecs/github-oidc.tf:175](../../infra/terraform/modules/ecs/github-oidc.tf#L175)) | Trust policy accepts `repo:${var.github_repo}:pull_request` — **any PR** (including from forks under some GitHub configurations, and from any contributor) can assume this role and run `bedrock:InvokeModel`. The comment acknowledges the risk and says "harden via env protection rule"; that hardening isn't in the Terraform. Cost-attack surface + data-exfil-via-prompt surface. | Either tighten the `sub` to `repo:${var.github_repo}:pull_request:base:main` style (still loose), or scope to `:environment:bedrock-ci` and gate the GitHub Environment with required reviewers. Add a `BedrockMaxTokens` SCP / per-day budget alarm as defense-in-depth. |
| **High** | `aws_db_instance.main` ([modules/rds/main.tf:43](../../infra/terraform/modules/rds/main.tf#L43)) | RDS uses the **AWS-managed `alias/aws/rds` key** (the `check` block at line 84 *enforces* this). For regulated data paths the audit checklist treats this as Medium; I'd elevate to High because (a) you cannot disable the key, (b) you cannot grant cross-account access to it, and (c) you lose the "key destruction = key revocation" property required by some retention regimes. | Provision a per-service CMK and set `kms_key_id` on a future RDS replacement. Note: this is **ForceNew** — schedule a snapshot+restore migration; do not flip in place. The existing `check` block must be inverted at the same time. |
| **High** | `aws_elasticache_replication_group.main` ([modules/elasticache/main.tf:14](../../infra/terraform/modules/elasticache/main.tf#L14)) | TLS in transit + at-rest encryption are on, but **no `auth_token`** (Redis AUTH) and no RBAC users. Anyone with network reach to port 6379 + a TLS handshake can issue commands. SG scoping helps but is not defense-in-depth. | Add `auth_token = random_password.redis.result` (32+ chars) + store in Secrets Manager. Or migrate to Redis user-group RBAC (`aws_elasticache_user` / `aws_elasticache_user_group`). Toggling `auth_token` forces replacement → ephemeral data loss is acceptable per the inline comment. |
| **High** | All `aws_secretsmanager_secret.*` ([modules/secrets/main.tf](../../infra/terraform/modules/secrets/main.tf)) | No `kms_key_id` set → defaults to `aws/secretsmanager` AWS-managed key. Same reasoning as RDS finding above; secret material is the most sensitive surface in the account. | Provision a per-env CMK and set `kms_key_id` on each `aws_secretsmanager_secret`. In-place change for the secret resource; **does not** re-encrypt existing versions — operators must rotate to bind to the new key. |
| **High** | `aws_s3_bucket.uploads` ([modules/s3/main.tf:5](../../infra/terraform/modules/s3/main.tf#L5)) | **No server access logging** and no S3 data-events trail. For a customer-data bucket in a regulated env, you cannot answer "who downloaded object X". | Add `aws_s3_bucket_logging` pointing at a separate access-log bucket, AND register the bucket as a CloudTrail data-event source. |
| **High** | (missing) | **No CloudWatch alarms for root account usage, unauthorized API calls, IAM policy changes**, etc. — the CIS AWS Foundations §3.x set. | Provision the standard CIS alarm pack (root-account-use, console-failures, IAM-policy-changes, S3-bucket-policy-changes, unauthorized-API-calls). Drop them in a new `modules/security-baseline/`. |
| **High** | `aws_apprunner_service.api` ([modules/app-runner/main.tf:127](../../infra/terraform/modules/app-runner/main.tf#L127)) | App Runner public endpoint has **no WAF**. Public surface in a regulated app warrants at minimum AWS-managed `CommonRuleSet` + rate limiting. App Runner WAF support is GA. | Add `aws_wafv2_web_acl_association` against the App Runner service ARN with `AWSManagedRulesCommonRuleSet` + `AWSManagedRulesKnownBadInputsRuleSet` + a rate-limit rule. |
| **Medium** | `aws_ecr_repository.backend` ([main.tf:95](../../infra/terraform/main.tf#L95)) | `encryption_type = "AES256"` (S3-managed). Audit checklist's KMS-CMK rule applies to ECR too. | `encryption_type = "KMS"` + `kms_key = aws_kms_key.ecr.arn`. **ForceNew** — destroys repo. Migrate via push to a new repo. |
| **Medium** | `aws_cognito_user_pool.main` ([modules/cognito/main.tf:16](../../infra/terraform/modules/cognito/main.tf#L16)) | `password_policy.minimum_length = 8`. CIS / NIST 800-63B current guidance is 12–14 chars min when MFA absent (and MFA is absent — see Critical above). | Bump to `minimum_length = 14`. In-place update. |
| **Medium** | `random_password.rds_master` ([modules/rds/main.tf:29](../../infra/terraform/modules/rds/main.tf#L29)) | `special = false` reduces character set to 62. 32-char base62 is still ~190 bits of entropy so practically fine, but RDS supports specials and the constraint reads as "we hit a special-char escaping bug once" rather than a security choice. | If specials caused a connection-string parsing bug, fix the parser (URL-encode); don't weaken the password. Otherwise leave a comment explaining the constraint. |
| **Medium** | `aws_secretsmanager_secret.*` ([modules/secrets/main.tf](../../infra/terraform/modules/secrets/main.tf)) | **No rotation** configured for any secret — including the RDS password. Regulated environments typically require ≤90-day rotation on DB credentials. | Add `aws_secretsmanager_secret_rotation` for `database` (and `redis` if you adopt AUTH) with the AWS-published Lambda rotation template. |
| **Medium** | `var.agentcore_runtime_arn` ([variables.tf:147](../../infra/terraform/variables.tf#L147)) | Default is wildcard `arn:aws:bedrock-agentcore:eu-central-1:*:runtime/*` — works because the App Runner module gates on a regex (modules/app-runner/main.tf:64) so the wildcard skips. But the wildcard sitting in defaults is a footgun: a future copy-paste into a non-gated context will silently grant bedrock-agentcore over any account. | Default to `""` (empty string) and update the regex gate to `length(var.agentcore_runtime_arn) > 0 && can(regex(...))`. |
| **Medium** | `aws_iam_role.github_actions` ([modules/ecs/github-oidc.tf:99-109](../../infra/terraform/modules/ecs/github-oidc.tf#L99)) | `ECSDeploy` statement uses `resources = ["*"]` for `RegisterTaskDefinition`/`UpdateService` — least-privilege violation. | Scope to `arn:aws:ecs:*:*:service/${var.project_name}-*/*` and `arn:aws:ecs:*:*:task-definition/${var.project_name}-*:*`. |
| **Medium** | `aws_iam_policy.ses_send` ([modules/ses/main.tf:13](../../infra/terraform/modules/ses/main.tf#L13)) | When `var.sender_email == ""` the policy condition becomes `ses:FromAddress = "*"` — i.e. any from address. The condition only constrains when the sender is set. | Either fail closed when `sender_email == ""` (count=0 the policy) or replace `"*"` with a region-scoped resource ARN. The policy is currently constructed but only attached when consumers reference its ARN, but it still exists in the account. |
| **Medium** | All security groups ([modules/networking/main.tf:137-142](../../infra/terraform/modules/networking/main.tf#L137) etc.) | Egress is `0.0.0.0/0` on all SGs (RDS, Redis, App Runner, ECS). For RDS/Redis the egress allows arbitrary outbound — should be unnecessary. | Remove the egress block on `rds` and `redis` SGs, or scope to VPC CIDR. App Runner & ECS legitimately need internet egress (Bedrock, ECR via NAT for non-VPC-endpoint services). |
| **Low** | `aws_ecr_repository.backend` ([main.tf:91](../../infra/terraform/main.tf#L91)) | `scan_on_push = true` enables only basic scanning. Enhanced scanning (Inspector v2) catches OS+lang vulns continuously. | Enable Inspector v2 for ECR at the account level (one-time `aws_inspector2_enabler` resource). |
| **Low** | `aws_iam_openid_connect_provider.github` ([modules/ecs/github-oidc.tf:9](../../infra/terraform/modules/ecs/github-oidc.tf#L9)) | `thumbprint_list` is hardcoded. AWS now ignores GitHub's OIDC thumbprint (since 2023), so this is decorative — but stale thumbprints suggest the doc/runbook may also be stale. | Leave the thumbprints (AWS still requires the field for backwards compat) but add a comment that they are no longer the trust mechanism. |
| **Low** | (missing) | **No GuardDuty / Security Hub / Macie / Inspector v2** at the account level. The audit checklist doesn't mandate these but for "regulated industry" they're table stakes. | Add a `modules/security-baseline/` enabling GuardDuty + Security Hub (with CIS + AWS Foundational Security Best Practices) + Inspector v2 + Macie. Account-global, ~$30–60/mo combined. |

---

## Cost findings

| Impact | Resource | Issue | Estimated savings / recommendation |
|---|---|---|---|
| **High** | `aws_s3_bucket.uploads` ([modules/s3/main.tf:136](../../infra/terraform/modules/s3/main.tf#L136)) | Versioning is **enabled** but lifecycle has only `abort-incomplete-multipart`. **No noncurrent-version expiration, no IA/Glacier transition.** Storage cost grows monotonically forever. | Add transitions to `STANDARD_IA` at 30d, `GLACIER_IR` at 90d, expire noncurrent versions at 90d. Could be 50–80% of bucket storage cost depending on overwrite cadence. Snippet below. |
| **High** | `aws_ecr_repository.backend` ([main.tf:86](../../infra/terraform/main.tf#L86)) | **No `aws_ecr_lifecycle_policy`.** Every CI build pushes a new image; nothing reaps them. Each image is ~500MB–2GB → $0.10/GB-mo → unbounded. | Add lifecycle: keep last 10 tagged with `sha-*`, expire untagged after 7 days. Likely $5–30/mo today, more later. |
| **High** | VPC interface endpoints ([modules/networking/main.tf:250-292](../../infra/terraform/modules/networking/main.tf#L250)) | Three Interface endpoints (`secretsmanager`, `ecr.api`, `ecr.dkr`) × 2 AZs × `~$0.011/hr` = **~$48/mo per env** ≈ **$144/mo across dev+staging+prod**. In dev/staging this is wildly disproportionate to traffic; in prod it's defensible. | Gate interface endpoints to `var.environment == "prod"` (S3 gateway endpoint stays — it's free). Keep dev/staging on NAT for these calls. ~$96/mo savings. |
| **Medium** | `var.rds_backup_retention_period = 30` ([variables.tf:52](../../infra/terraform/variables.tf#L52)) | Dev tfvars also uses 30d retention. Backup storage > allocated storage is billed. For a 20GB dev DB with churn, ~$5–10/mo of backup storage. | Set dev to 7 days, staging to 14, prod stays at 30. In-place update. |
| **Medium** | `aws_ecs_service.worker` + `aws_ecs_service.beat` in dev ([modules/ecs/main.tf:175,284](../../infra/terraform/modules/ecs/main.tf#L175)) | dev runs 2 always-on Fargate tasks (worker + beat) at 0.5vCPU/1GB → ~$15/mo even when idle. | Either set `desired_count = 0` in dev tfvars and toggle when used, or use Fargate Spot (`capacity_provider_strategy`). Worker+beat both use the SAME `cpu`/`memory` — beat could be 256/512. |
| **Medium** | `aws_nat_gateway.main` ([modules/networking/main.tf:61](../../infra/terraform/modules/networking/main.tf#L61)) | **Single NAT in `az[0]` only**. Comment acknowledges the cost-vs-HA tradeoff. NAT is ~$32/mo per AZ + data; if `az[0]` fails, all private-subnet egress (Bedrock, ECR pulls if endpoint absent, SES, Cognito IDP) breaks across both AZs. | This is a defensible cost choice for dev/staging. For **prod**, add a second NAT in `az[1]` and a per-AZ private route table → ~$32/mo + reliability. Not a regression to ignore but worth flagging. |
| **Medium** | `aws_cloudwatch_log_group.worker` and `.beat` ([modules/ecs/main.tf:20,206](../../infra/terraform/modules/ecs/main.tf#L20)) | 30-day retention in dev. Plus the metric-filter log groups inherit the same retention. | Set 7d in dev, 14d in staging, 30d (or 90d for compliance) in prod. Drive from `var.environment`. |
| **Low** | `aws_apprunner_service.api` ([modules/app-runner/main.tf:127](../../infra/terraform/modules/app-runner/main.tf#L127)) | `min_instances = 1` in dev means a permanently warm instance even when nobody is using dev. App Runner provisioned-but-paused instance ≈ $0.007/vCPU-hr × 1vCPU + $0.0008/GB-hr × 2GB ≈ ~$7/mo dev only. | Either keep (developer experience) or drop to `min_instances = 0` and accept cold-start. Dev tfvars choice. |
| **Low** | `aws_db_instance.main` ([modules/rds/main.tf:43](../../infra/terraform/modules/rds/main.tf#L43)) | No `performance_insights_enabled` on prod. Cost-impact: nearly free for 7-day retention; cost flag is here because the audit checklist asks about it. | Add `performance_insights_enabled = var.environment == "prod"` + `performance_insights_retention_period = 7`. Free for 7d retention on db.t4g class. |
| **Low** | `aws_apprunner_auto_scaling_configuration_version.main` ([modules/app-runner/main.tf:180](../../infra/terraform/modules/app-runner/main.tf#L180)) | `max_concurrency = 25` is App Runner default. For an FastAPI/SSE workload (chat) this is low — you'll scale out before saturating CPU. | Tune to 50–100 for SSE-heavy paths; reduces instance count under load. Not a regression. |

---

## Quick wins (low-effort, high-impact — address first)

1. **Add `deletion_protection` to RDS** — one line in [modules/rds/main.tf:43](../../infra/terraform/modules/rds/main.tf#L43), in-place update, prevents catastrophic loss.
2. **Add ECR lifecycle policy** — ~10 lines, in-place, immediate cost ceiling.
3. **Add S3 lifecycle transitions + noncurrent expiration** to [modules/s3/main.tf:136](../../infra/terraform/modules/s3/main.tf#L136) — in-place, bounds storage growth.
4. **Set `image_tag_mutability = "IMMUTABLE"` on ECR** + drop `:beat-latest` bootstrap reference — supply-chain hardening, requires deploy-workflow tweak but no infra recreation.
5. **Gate VPC interface endpoints on `var.environment == "prod"`** — saves ~$96/mo and is a delete-only diff for dev/staging.
6. **Cognito MFA + 14-char password** — two arguments, in-place.
7. **Reduce dev RDS `backup_retention_period` to 7 days** — one line in dev tfvars.
8. **Tighten `github_bedrock_ci` trust policy** — restrict the PR `sub` claim to `:environment:bedrock-ci` and add a GitHub Environment with required reviewers.

---

## Terraform snippets (Critical/High security + High cost)

### Critical-1: CloudTrail with log-file validation

New file `modules/security-baseline/cloudtrail.tf`:

```hcl
resource "aws_kms_key" "cloudtrail" {
  description             = "${local.name_prefix} CloudTrail CMK"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.cloudtrail_kms.json
}

resource "aws_s3_bucket" "cloudtrail" {
  bucket        = "${local.name_prefix}-cloudtrail-logs"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "cloudtrail" {
  bucket                  = aws_s3_bucket.cloudtrail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudtrail" "main" {
  name                          = "${local.name_prefix}-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  is_multi_region_trail         = true
  include_global_service_events = true
  enable_log_file_validation    = true
  kms_key_id                    = aws_kms_key.cloudtrail.arn

  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["${module.s3.bucket_arn}/"]
    }
  }
}
```
*Plan side-effect: pure additions. No recreation.*

### Critical-2: VPC Flow Logs

Append to [modules/networking/main.tf](../../infra/terraform/modules/networking/main.tf):

```hcl
resource "aws_cloudwatch_log_group" "vpc_flow" {
  name              = "/vpc/${local.name_prefix}-flow"
  retention_in_days = var.environment == "prod" ? 90 : 14
}

resource "aws_iam_role" "vpc_flow" {
  name               = "${local.name_prefix}-vpc-flow"
  assume_role_policy = data.aws_iam_policy_document.vpc_flow_assume.json
}

data "aws_iam_policy_document" "vpc_flow_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["vpc-flow-logs.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "vpc_flow" {
  role   = aws_iam_role.vpc_flow.id
  policy = data.aws_iam_policy_document.vpc_flow_logs.json
}

data "aws_iam_policy_document" "vpc_flow_logs" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
    resources = ["${aws_cloudwatch_log_group.vpc_flow.arn}:*"]
  }
}

resource "aws_flow_log" "main" {
  iam_role_arn    = aws_iam_role.vpc_flow.arn
  log_destination = aws_cloudwatch_log_group.vpc_flow.arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.main.id
}
```
*Plan side-effect: pure additions.*

### Critical-3: RDS deletion protection

In [modules/rds/main.tf:43](../../infra/terraform/modules/rds/main.tf#L43):

```hcl
resource "aws_db_instance" "main" {
  # ... existing args ...
  deletion_protection = var.environment == "prod"
}
```
*Plan side-effect: in-place update, no downtime.*

### Critical-4: Cognito MFA + stronger password

In [modules/cognito/main.tf:6](../../infra/terraform/modules/cognito/main.tf#L6):

```hcl
resource "aws_cognito_user_pool" "main" {
  # ... existing ...

  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration {
    enabled = true
  }

  password_policy {
    minimum_length                   = 14   # was 8
    require_uppercase                = true
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }
}
```
*Plan side-effect: in-place update; existing users unaffected until next password reset.*

### Critical-5: ECR immutability

In [main.tf:86](../../infra/terraform/main.tf#L86):

```hcl
resource "aws_ecr_repository" "backend" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "IMMUTABLE"   # was MUTABLE
  force_delete         = var.environment == "dev"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr.arn
  }
}
```
*Plan side-effect: `image_tag_mutability` is in-place. `encryption_type` change is **ForceNew** — defer or do it via repo migration. Also requires deploy workflow to stop pushing `:latest`/`:beat-latest`.*

### Critical-6: Tighten GitHub Bedrock CI OIDC trust

In [modules/ecs/github-oidc.tf:166-170](../../infra/terraform/modules/ecs/github-oidc.tf#L166):

```hcl
condition {
  test     = "StringLike"
  variable = "token.actions.githubusercontent.com:sub"
  values   = ["repo:${var.github_repo}:environment:bedrock-ci"]
}
```
And in `.github/workflows/ci-backend-provider-matrix.yml`, set `environment: bedrock-ci` on the job — gate that GitHub Environment with required reviewers and branch restrictions.
*Plan side-effect: in-place IAM update.*

### High: ElastiCache AUTH token

In [modules/elasticache/main.tf:14](../../infra/terraform/modules/elasticache/main.tf#L14):

```hcl
resource "random_password" "redis_auth" {
  length  = 64
  special = false   # Redis AUTH disallows some specials
}

resource "aws_elasticache_replication_group" "main" {
  # ... existing ...
  auth_token                 = random_password.redis_auth.result
  transit_encryption_enabled = true
}
```
And surface `auth_token` to the consumer via a new Secrets Manager entry consumed by `redis_connection_url`.
*Plan side-effect: enabling `auth_token` on an existing replication group **forces replacement** → ephemeral data loss. Already accepted per the existing comment at modules/elasticache/main.tf:21 for the encryption flip.*

### High: S3 lifecycle (cost High)

Replace [modules/s3/main.tf:136-149](../../infra/terraform/modules/s3/main.tf#L136):

```hcl
resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "transition-current-versions"
    status = "Enabled"
    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
  }

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}
```
*Plan side-effect: in-place update; objects already past the cutoffs transition on the next lifecycle run.*

### High: ECR lifecycle (cost High)

Append to [main.tf](../../infra/terraform/main.tf) after the `aws_ecr_repository.backend` block:

```hcl
resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images older than 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep last 10 sha-tagged images"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["sha-*", "beat-*"]
          countType      = "imageCountMoreThan"
          countNumber    = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}
```
*Plan side-effect: pure addition; first run reaps existing stale images.*

### High: Gate VPC interface endpoints on prod (cost High)

In [modules/networking/main.tf:249-292](../../infra/terraform/modules/networking/main.tf#L249), add `count = var.environment == "prod" ? 1 : 0` to `aws_vpc_endpoint.secretsmanager`, `ecr_api`, `ecr_dkr`, and `aws_security_group.vpc_endpoints`. Update references with `[0]` indexing.
*Plan side-effect: **destroy** of the three interface endpoints in dev/staging. No data path impact — traffic falls back to NAT egress (which already works for everything else).*

---

## Cross-cutting notes

- **Provider version**: pinned at `~> 5.0`. The S3 `aws_s3_bucket_lifecycle_configuration` shape and the Bedrock Guardrail resource both require provider 5.x; the snippets above assume that. If you bump to 6.x the `filter {}` empty-block syntax may need a `prefix = ""` form.
- **Default tags coverage**: `providers.tf` correctly applies `Project / Environment / ManagedBy / feature / epic / env` via `default_tags`. Module-level `tags = { Name = ... }` blocks merge cleanly. The Bedrock Guardrail module re-declares `feature = "chat"` and `epic = "10"` to override the default `ai`/`9` — that's intentional and documented.
- **Backend not yet migrated to S3**: [backend.tf](../../infra/terraform/backend.tf) is fully commented out; state lives locally. For a regulated production env this is itself a finding (state contains plaintext secret values), but it's flagged in the file's comment as "uncomment after bootstrap" — so I treat it as a known follow-up rather than a finding here.
- **`terraform.tfstate` and `terraform.tfstate.backup` are present in the repo directory.** The current `terraform.tfstate` is 0 bytes, but `terraform.tfstate.backup` is 9 KB. **If that backup contains real prod state with the random RDS password, it should be purged from git history.** Check `git log -- infra/terraform/terraform.tfstate*` before assuming it's safe.
