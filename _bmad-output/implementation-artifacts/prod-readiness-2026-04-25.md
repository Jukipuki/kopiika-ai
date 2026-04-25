# Prod-readiness hardening — 2026-04-25

Status: ready-for-review (Phase A–E complete; review fixes applied; Phase F = first prod apply)

## Review fixes (post-initial-review, same day)

A self-review surfaced 14 findings; all resolved or tracked. Summary:

| ID | Finding | Resolution |
|---|---|---|
| H1 | ECR lifecycle `tagPatternList = ["sha-*", "beat-sha-*"]` matched zero of the actual pushed tags (`<sha>`, `worker-<sha>`, `beat-<sha>`) — repo would grow unbounded | Renamed pushed tags to `sha-<sha>`, `worker-sha-<sha>`, `beat-sha-<sha>` in `build-image.yml` and `deploy-backend.yml`; split lifecycle into 3 prefix rules (each keeps last 20) |
| H2 | `aws_iam_policy.ses_send` was orphan; would AccessDenied once SES enabled. Cognito-via-SES path needed an `aws_ses_identity_policy`, not an IAM policy | Added `aws_ses_identity_policy.cognito` granting `cognito-idp.amazonaws.com` SendEmail; attached `aws_iam_policy.ses_send` to App Runner instance role via new `aws_iam_role_policy_attachment.apprunner_ses` (count-gated on `has_sender`) |
| H3 | Deprecated `awslabs/amazon-app-runner-deploy@v1` action would AccessDenied (needs `apprunner:StartDeployment`/`TagResource` not in IAM) | Replaced with raw `aws apprunner update-service` + describe-service polling loop; reuses existing `apprunner:UpdateService`/`DescribeService` perms |
| H4 | `llm_api_keys` secret_version had no `lifecycle.ignore_changes`; operator-rotated keys would be wiped on next apply | Added the same `lifecycle { ignore_changes = [secret_string] }` guard as `chat_canaries`; cleaned dangling TD reference in chat_canaries comment |
| H5 | Standalone `aws_acm_certificate.api` was dead code — App Runner manages its own internal cert; the standalone would linger PENDING_VALIDATION forever | Deleted the resource and `api_acm_validation_records` output; updated `domain-setup.md` to reflect the single (App Runner-emitted) record set |
| M1 | `mfa_configuration = "OPTIONAL"` is opt-in, not enforced | Inline comment + TD-116 to flip to ON or post-confirmation Lambda once user base is real |
| M2 | VPC Flow Logs CloudWatch group was unencrypted (broke the Phase C per-service-CMK pattern) | Added `aws_kms_key.flow_logs` + alias + key policy granting `logs.<region>.amazonaws.com` Encrypt/Decrypt, scoped via `kms:EncryptionContext:aws:logs:arn`; log group now references the CMK |
| M3 | `ses_sender_email = ""` means Cognito uses AWS default sender (`no-reply@verificationemail.com`) — works but unbranded + sandbox-quota-shared | TD-117 with the SES domain-verification + sandbox-exit procedure |
| M4 | ECS `kms_key_arns` granted `kms:GenerateDataKey` on uploads CMK, but ECS only reads from S3 (verified: `processing_tasks.py:201` calls `get_object`, no `put_object` in `app/tasks/`) | Tightened ECS KMS policy to `Decrypt` + `DescribeKey` only — no `GenerateDataKey`; App Runner keeps full set (writes) |
| M5 | Story file-list omitted `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified pre-session) and `10-7-chat-ui.md` (untracked, unrelated) | Both are unrelated to this story and were excluded intentionally — clarifying here for reviewer transparency |
| M6 | "Plan: 157 to add" was unverified by `apply` against any account | `terraform validate` ✓ and `terraform plan` ✓ are the strongest checks possible without an apply target. Phase F is the first apply, against prod. No staging env to dry-run against (single-env decision); operator should review the apply log carefully and be ready to triage |
| L1 | Build workflow runs on push regardless of CI status | TD-119 noting branch protection is the actual gate; `workflow_run` chaining is belt-and-suspenders if protection ever loosens |
| L2 | Hardcoded `time_period_start = "2026-04-01_00:00"` in budgets | Inline comment clarifying this is creation-only and AWS Budgets does NOT retroactively pull spend from a past start date; safe to leave |
| L3 | Inspector v2 cost concern | Resolved by H1 fix (lifecycle now actually reaps; image count bounded at 60) |
| L4 | `random_password.redis_auth` doesn't actually rotate (no `keepers`) | TD-118 with the keepers pattern + manual taint procedure |

Resulting plan after round 1: **158 to add, 0 to change, 0 to destroy** (was 157; +2 from flow-logs KMS+alias, −1 from deleted ACM cert).

## Review fixes — round 2 (introduced by H3's CLI replacement)

The H3 fix (replacing `awslabs/amazon-app-runner-deploy@v1` with raw `aws apprunner` CLI) introduced its own bugs. Re-review caught five.

| ID | Finding | Resolution |
|---|---|---|
| R1 | `aws apprunner list-services` at the start of the deploy job — `apprunner:ListServices` was not in the OIDC role's IAM policy and AWS doesn't allow resource-level scoping on it (requires `*`). First deploy would AccessDenied at the very first AWS call. | Added a separate IAM statement granting `apprunner:ListServices` on `*`; tightened the existing scoped statement to also include `apprunner:ListOperations` (needed for R3's polling fix). The scoped statement's resource was also corrected to `service/${project_name}-*/*` (was missing the trailing `/*` for the App Runner service-instance UUID). |
| R2 | `update-service --source-configuration` JSON omitted `ImageConfiguration` (Port + RuntimeEnvironmentVariables). App Runner treats `SourceConfiguration.ImageRepository` as a full replacement → next deploy would silently reset port to 8080 (failing `/health`) and clear `ENVIRONMENT` + `AWS_SECRETS_PREFIX` env vars (FastAPI falls back to dev-pointed config or hard-fails on secrets prefix lookup). `lifecycle.ignore_changes` does NOT save you — it only protects `image_identifier`, not the nested config. | Inlined the full `ImageConfiguration` block into the workflow's update-service call: `Port = "8000"`, `RuntimeEnvironmentVariables = { ENVIRONMENT, AWS_SECRETS_PREFIX }` — values mirror [modules/app-runner/main.tf:170-176](../../infra/terraform/modules/app-runner/main.tf). Comment in the workflow file flags the mirror requirement so the values stay in sync if Terraform's are ever changed. |
| R3 | App Runner status polling used `describe-service.Status` which can briefly still report the previous deploy's `RUNNING` state for a few seconds after `update-service` returns — so the workflow could exit success without verifying the new deploy ever started. | Switched to `OperationId` tracking: capture `OperationId` from `update-service`'s response, poll `aws apprunner list-operations --query "OperationSummaryList[?Id=='$OP_ID'].Status"` until terminal. Treats `SUCCEEDED` as success, `FAILED`/`ROLLBACK_FAILED`/`ROLLBACK_SUCCEEDED` as failure (rollback success means our image was rejected). |
| M4-followup | The reviewer flagged that `module.ecs.kms_key_arns = [secrets, uploads]` looked unchanged from before — appearing as if M4 was claimed fixed but wasn't. | The list IS correct: ECS *does* need `kms:Decrypt` on the uploads CMK because `processing_tasks.py:201` does `s3.get_object` against KMS-encrypted objects. What was tightened in round 1 was the action set in the ECS module (Decrypt + DescribeKey only — no `GenerateDataKey`, since ECS doesn't write). Added a comment on the `kms_key_arns` list in [main.tf](../../infra/terraform/main.tf) explaining this distinction so a future reviewer doesn't have to re-derive it. |
| L-new | `data.aws_caller_identity.current` declared in `flow-logs.tf` while `data.aws_region.current` is in `main.tf` — same module, split-personality data sources. | Moved `data.aws_caller_identity.current` to `modules/networking/main.tf` next to `aws_region`. Comment in `flow-logs.tf` notes both data sources are module-scoped. |

Final plan: **158 to add, 0 to change, 0 to destroy** (R1-R3 are CLI/IAM-policy/comment changes — no resource churn).

---

## Story

As **the solo operator preparing for first prod traffic**,
I want **the Terraform audit's Critical and High findings closed before the first apply, plus a manual-release CI gate, plus a documented bootstrap procedure**,
so that **we ship to prod once with the right posture instead of patching a running system**.

## Background

Three artifacts kicked this off:

1. **Terraform audit** — [_bmad-output/planning-artifacts/terraform-audit-2026-04-25.md](../planning-artifacts/terraform-audit-2026-04-25.md). Six Critical and seven High findings.
2. **Operator decision** — single env named `prod`, archive `dev` / `staging` tfvars, single NAT (skip 2nd NAT in prod), Squarespace registrar (not Route 53), manual secrets bootstrap, half-day "do it right" approach.
3. **State of the world** — current AWS account: only a stale dev-tfvars Cognito user pool + S3 uploads bucket (test data, disposable). No real prod traffic. ECR image immutability and Redis AUTH (both `ForceNew`) are free because nothing is running.

## Phases

Each phase landed as ordered groups of changes; this story captures the whole thing as a single review surface.

### Phase A — Tear down + state-bucket protection

**Pre-flight:** verified `terraform.tfstate.backup` was never committed to git history (no leaked credentials). `kopiika-terraform-state` S3 bucket already exists in eu-central-1 with public-access-block; lacked versioning, lifecycle, bucket policy.

**Done:**

- Versioning enabled on state bucket (before destroy, so destroy is reversible via prior version restore).
- `terraform destroy` against the dev tfvars — 10 resources removed (Cognito user pool + clients + S3 uploads + 7 supporting configs).
- Stale local `terraform.tfstate` (0 B) and `terraform.tfstate.backup` (9 KB) removed; remote state in S3 is the only source of truth.

### Phase B — State-bucket hardening + tfvars consolidation

**Done:**

- Lifecycle policy on `kopiika-terraform-state`: noncurrent versions expire at 365d, incomplete multipart aborts at 7d.
- Bucket policy: deny non-TLS access, deny unencrypted PUT.
- `infra/terraform/environments/{dev,staging}` moved to `infra/terraform/tfvars.archive/`. `environments/` now contains only `prod`.
- `backend.tf` comment cleaned up (was misleadingly suggesting the backend was disabled — it's been wired since 2026-04-11).
- New runbook: [docs/runbooks/state-bucket.md](../../docs/runbooks/state-bucket.md) — how the bucket was bootstrapped, recovery procedures, the deferred KMS-CMK migration (TD-111).

### Phase C — Security hardening (155 of 157 net-new resources in the plan)

The biggest phase. All Critical + High audit findings closed in a single PR-shaped diff because nothing is running, so `ForceNew` migrations are free.

#### Per-service KMS CMKs (5 new keys)

Per-service, not shared, so blast radius and key-policy review surfaces stay scoped:

| CMK | Wraps |
|---|---|
| `kopiika-prod-rds` | RDS storage + Performance Insights |
| `kopiika-prod-redis` | ElastiCache at-rest |
| `kopiika-prod-secrets` | All 7 Secrets Manager entries |
| `kopiika-prod-s3-uploads` | S3 uploads bucket (default + bucket-key-enabled) |
| `kopiika-prod-ecr` | ECR repository |
| `kopiika-prod-cloudtrail` | CloudTrail S3 sink |

All have `enable_key_rotation = true` and 30d deletion windows.

#### ECR ([infra/terraform/main.tf](../../infra/terraform/main.tf))

- `image_tag_mutability = "IMMUTABLE"` (was MUTABLE — supply-chain hardening)
- Encryption switched from AES256 to KMS via `aws_kms_key.ecr`
- Lifecycle policy: untagged images expire at 7d; only the last 20 sha-tagged or beat-sha-tagged images retained
- `:latest` and `:beat-latest` tag references removed everywhere — see "Image-tag parameterization" below

#### RDS ([modules/rds/main.tf](../../infra/terraform/modules/rds/main.tf))

- `deletion_protection = true` (prod-gated)
- `kms_key_id = aws_kms_key.rds.arn` — replaces the AWS-managed `aws/rds`. Old Story 5.1 AC #1 `check` block updated to assert against the new CMK.
- `performance_insights_enabled` + 7d retention (free tier on db.t4g class)
- `copy_tags_to_snapshot = true`

Cross-region automated backup replication deferred to TD-112 (multi-region scope creep).

#### Redis ([modules/elasticache/main.tf](../../infra/terraform/modules/elasticache/main.tf))

- 64-char `auth_token` from `random_password.redis_auth` (base62 to avoid AUTH-special-char escaping issues)
- Per-service CMK on at-rest encryption
- `connection_url` output now embeds the auth token: `rediss://:<token>@host:6379`
- `auth_token_update_strategy = "ROTATE"` for safe future rotations

#### Secrets Manager ([modules/secrets/main.tf](../../infra/terraform/modules/secrets/main.tf))

- Per-env CMK applied to all 7 secrets (database, redis, cognito, s3, ses, llm-api-keys, chat-canaries)
- `kms_key_arn` exported so consumers (App Runner, ECS) can grant `kms:Decrypt` on it

#### S3 uploads ([modules/s3/main.tf](../../infra/terraform/modules/s3/main.tf))

- Per-service CMK; bucket-default encryption flipped from `AES256` to `aws:kms`
- Bucket policy: `DenyNonAES256Encryption` replaced with `DenyNonKMSEncryption` (`StringNotEqualsIfExists` so unmarked PUTs still go through and bucket-default encrypts)
- New `aws_s3_bucket.access_logs` (separate access-log destination, AES256-encrypted because the S3 log-delivery group can't write KMS without per-key carve-outs); `aws_s3_bucket_logging` on the uploads bucket
- Real lifecycle: STANDARD_IA at 30d, GLACIER_IR at 90d, noncurrent versions expire at 90d
- Backend code update: [backend/app/services/upload_service.py](../../backend/app/services/upload_service.py) sends `aws:kms` instead of `AES256`

#### Networking ([modules/networking/](../../infra/terraform/modules/networking/))

- New file `flow-logs.tf`: VPC Flow Logs to a CloudWatch log group, retention 90d in prod
- RDS + Redis security groups lost their `0.0.0.0/0` egress (default-deny — neither initiates outbound)

#### Cognito ([modules/cognito/main.tf](../../infra/terraform/modules/cognito/main.tf))

- `mfa_configuration = "OPTIONAL"` + `software_token_mfa_configuration { enabled = true }`
- Password minimum length 8 → 14

#### App Runner ([modules/app-runner/](../../infra/terraform/modules/app-runner/))

- New `waf.tf`: WAFv2 web ACL with `AWSManagedRulesCommonRuleSet` + `AWSManagedRulesKnownBadInputsRuleSet` + per-IP rate limit (2000 requests/5 min)
- `apprunner_kms` IAM policy granting `kms:Decrypt`/`GenerateDataKey`/`DescribeKey` on the secrets + S3 CMKs
- New `var.image_tag` (default `bootstrap`) — replaces hardcoded `:latest`
- `lifecycle.ignore_changes = [source_configuration[0].image_repository[0].image_identifier]` so CI deploys aren't reverted by the next `terraform apply`

#### ECS ([modules/ecs/](../../infra/terraform/modules/ecs/))

- `ecs_task_kms` IAM policy mirroring the App Runner one
- New `var.image_tag` (default `bootstrap`); worker uses `:${image_tag}`, beat uses `:beat-${image_tag}`
- `lifecycle.ignore_changes = [task_definition]` on both worker + beat services

#### IAM tightening ([modules/ecs/github-oidc.tf](../../infra/terraform/modules/ecs/github-oidc.tf))

- `github_bedrock_ci` `sub` claim locked to `repo:${var.github_repo}:environment:bedrock-ci` (was `pull_request` — any PR could assume the role and burn Bedrock budget). The CI matrix workflow now sets `environment: bedrock-ci` on the bedrock job; that GitHub Environment is configured with required reviewers as defense-in-depth on top of the AWS Budgets cap.
- `github_actions` ECS deploy actions scoped to `arn:aws:ecs:*:*:service/${project_name}-*/*` instead of `*` (`RegisterTaskDefinition` stays `*` because IAM doesn't support resource-level scoping on it)
- Dead `data "aws_iam_openid_connect_provider"` removed (failed to plan after destroy)

#### SES ([modules/ses/main.tf](../../infra/terraform/modules/ses/main.tf))

- Wildcard `ses:FromAddress = "*"` policy fail-closed: when `var.sender_email == ""`, the policy doesn't get created at all (`count = local.has_sender ? 1 : 0`).

#### Variable defaults

- `agentcore_runtime_arn` default `arn:aws:bedrock-agentcore:eu-central-1:*:runtime/*` → `""`. The existing regex gate in [modules/app-runner/main.tf:64](../../infra/terraform/modules/app-runner/main.tf#L64) treats both as "no policy" but the empty default removes the wildcard footgun.

#### NEW module: `security-baseline` ([modules/security-baseline/](../../infra/terraform/modules/security-baseline/))

A self-contained account-wide security baseline. Composed of:

- **CloudTrail** (`cloudtrail.tf`) — multi-region, log-file validation, dedicated KMS-encrypted S3 sink with deny-delete bucket policy, CloudWatch log group fed at 90d retention. Ten resources.
- **GuardDuty** (`guardduty.tf`) — detector with S3-data-events on, fifteen-minute publishing.
- **Security Hub** (`securityhub.tf`) — subscribed to AWS Foundational Security Best Practices + CIS AWS Foundations Benchmark v1.4.
- **Inspector v2** (`inspector.tf`) — enabled for ECR.
- **CIS alarm pack** (`alarms.tf`) — SNS topic + 7 high-signal CloudWatch alarms via metric filters on the CloudTrail log group: unauthorized API calls (3.1), root-account use (3.3), IAM policy changes (3.4), CloudTrail-config changes (3.5), console-auth failures (3.6), KMS key disable/delete (3.7), S3 bucket-policy changes (3.8). The 5 network-change alarms (3.10–3.14) are skipped intentionally — see TD-114.
- **AWS Budgets** (`budgets.tf`) — total monthly + Bedrock-specific. Both fire at 80% actual + 100% forecast. Bedrock cap is defense-in-depth against the `github_bedrock_ci` role being abused.

Wired into [main.tf](../../infra/terraform/main.tf) at the bottom alongside the other modules.

#### Tech debt opened

- **TD-111** — Migrate state bucket to KMS CMK (current SSE-S3)
- **TD-112** — RDS cross-region automated backup replication
- **TD-113** — Secrets Manager rotation Lambda for DB password
- **TD-114** — Network-change CIS alarms (3.10–3.14) intentionally skipped
- **TD-115** — Phase D CI rewrite tracker (now resolved by Phase D below)

### Phase D — CI rewrite

Goal: merge to `main` should not auto-deploy. Releases must be a deliberate, reviewable click.

#### NEW: [.github/workflows/build-image.yml](../../.github/workflows/build-image.yml)

Triggered by `push: backend/**` to main. Builds and pushes three images per commit:

- `kopiika-backend:<sha>` (API, from `backend/Dockerfile`)
- `kopiika-backend:worker-<sha>` (worker, from `backend/Dockerfile.worker`)
- `kopiika-backend:beat-<sha>` (beat, from `backend/Dockerfile.beat`)

No `:latest` (incompatible with IMMUTABLE ECR). Job summary lists the tags so the operator knows what's available to release.

#### REWRITE: [.github/workflows/deploy-backend.yml](../../.github/workflows/deploy-backend.yml)

`workflow_dispatch` only — no more push-on-main trigger. Inputs:

- `image_sha` — commit sha to deploy. Validated against ECR before any deploy step runs.
- `run_migrations` — boolean, default true.

Steps: configure AWS OIDC → ECR login → verify all 3 image tags exist → optional alembic → App Runner deploy → ECS worker render+deploy → ECS beat render+deploy. Each AWS call waits for stability before the next one runs.

`environment: production` is unchanged from the prior workflow — required-reviewer approval is configured on that GitHub Environment and gates the workflow.

#### PATCH: [.github/workflows/ci-backend-provider-matrix.yml](../../.github/workflows/ci-backend-provider-matrix.yml)

Added `environment: bedrock-ci` to the provider-matrix job. Required to match the new `github_bedrock_ci` OIDC trust policy `sub` claim. The `bedrock-ci` GitHub Environment must be configured in repo settings with required reviewers — that's the defense-in-depth gate.

#### NEW runbooks

- [docs/runbooks/release.md](../../docs/runbooks/release.md) — day-to-day release flow, first-deploy bootstrap (push `:bootstrap` and `:beat-bootstrap` images by hand), break-glass laptop deploy if Actions is down, rollback procedure.
- [docs/runbooks/terraform.md](../../docs/runbooks/terraform.md) — local Terraform workflow + safety rules ("never destroy", "never state rm to fix drift", "never apply without -out").
- [docs/runbooks/state-bucket.md](../../docs/runbooks/state-bucket.md) — covered above.

### Phase E — Domain + secrets bootstrap

#### Custom domain ([modules/app-runner/domain.tf](../../infra/terraform/modules/app-runner/domain.tf))

- `aws_acm_certificate.api` (DNS-validated, eu-central-1 — App Runner uses regional certs)
- `aws_apprunner_custom_domain_association.api` for `api.kopiika.coach`
- Outputs (`api_acm_validation_records`, `api_app_runner_dns_records`) surface the DNS records to paste into Squarespace's DNS panel — Squarespace doesn't expose an API.

`api_custom_domain = "api.kopiika.coach"` set in `prod.tfvars`.

#### NEW runbooks

- [docs/runbooks/domain-setup.md](../../docs/runbooks/domain-setup.md) — Squarespace DNS click-by-click, ACM validation timing, verification commands, renewal note.
- [docs/runbooks/secrets-bootstrap.md](../../docs/runbooks/secrets-bootstrap.md) — which secrets need manual values (LLM API keys, chat canaries, optional SES), exact `aws secretsmanager put-secret-value` commands, what to do when a secret is missing.

## Plan output

`terraform plan -var-file=environments/prod/terraform.tfvars`:

```
Plan: 157 to add, 0 to change, 0 to destroy.
```

One warning: the `check.rds_uses_customer_managed_kms` block in the RDS module evaluates at apply time (KMS ARNs aren't known at plan); not blocking.

## What's NOT in this story

Listed so a reviewer doesn't think they were forgotten:

- **Macie** for S3 PII detection — too expensive for a solo project ($1+/GB scanned). Skip until needed.
- **Second NAT in az[1]** for AZ-failover HA — operator decision, $32/mo not justified at solo scale.
- **VPC interface endpoints gated to prod-only** — single-env (always prod) collapses this to "always on". No change needed; the audit's cost-saving recommendation is mooted by the env consolidation.
- **Dev / staging environments** — archived to `tfvars.archive/`. Recreate as ephemeral test environments only when needed.
- **CI-driven `terraform plan/apply`** — local-only is right at solo scale. See [docs/runbooks/terraform.md](../../docs/runbooks/terraform.md).

## Phase F — first prod apply (next, requires operator approval)

Sequence:

1. **Build + push bootstrap images** by hand per [release.md](../../docs/runbooks/release.md) → `:bootstrap` and `:beat-bootstrap`. Without these, App Runner / ECS task-defs reference tags that don't exist.
2. **`terraform apply`** locally with `-var-file=environments/prod/terraform.tfvars` and a saved plan. 157 resources land.
3. **Bootstrap manual secrets** per [secrets-bootstrap.md](../../docs/runbooks/secrets-bootstrap.md): LLM API keys, chat canaries.
4. **Configure GitHub Environments** in repo settings → Environments:
   - `production` — required reviewer = ohumennyi (already exists, verify)
   - `bedrock-ci` — new; required reviewer = ohumennyi
5. **Set GitHub repo vars/secrets**:
   - `vars.AWS_IAM_ROLE_ARN` = output of `terraform output github_actions_role_arn`
   - `vars.PROJECT_NAME` = `kopiika`
   - `vars.ENVIRONMENT` = `prod`
   - `vars.APPRUNNER_ECR_ROLE_ARN` = output of `terraform output app_runner_ecr_role_arn`
   - `secrets.AWS_ROLE_TO_ASSUME` (for the bedrock-ci provider matrix) = output of `terraform output github_bedrock_ci_role_arn`
6. **Confirm SNS subscription** — AWS sends a confirmation email to `ogumennyj@gmail.com` for the security-alarms topic; click the link to confirm.
7. **Paste DNS records into Squarespace** per [domain-setup.md](../../docs/runbooks/domain-setup.md). Wait for ACM ISSUED + App Runner ACTIVE.
8. **Smoke test** — `curl https://api.kopiika.coach/health` returns 200; tail App Runner + ECS logs for clean startup.
9. **Trigger Deploy Backend** workflow with the real first commit's sha to replace the bootstrap images.

## Files changed

```
backend/app/services/upload_service.py                         # AES256 → aws:kms

infra/terraform/backend.tf                                     # cleanup misleading comment
infra/terraform/main.tf                                        # ECR KMS+IMMUTABLE+lifecycle, plumb kms+image_tag+domain, security_baseline module
infra/terraform/outputs.tf                                     # domain DNS records
infra/terraform/variables.tf                                   # security baseline + image_tag + custom_domain vars; agentcore default ""

infra/terraform/environments/prod/terraform.tfvars             # security_alarm_email, budgets, image_tag, api_custom_domain

infra/terraform/modules/app-runner/domain.tf                   # NEW
infra/terraform/modules/app-runner/main.tf                     # KMS perms, image_tag, lifecycle.ignore_changes, agentcore default
infra/terraform/modules/app-runner/outputs.tf                  # custom_domain + DNS records
infra/terraform/modules/app-runner/variables.tf                # kms_key_arns, image_tag, custom_domain, agentcore default
infra/terraform/modules/app-runner/waf.tf                      # NEW

infra/terraform/modules/cognito/main.tf                        # MFA + 14-char password

infra/terraform/modules/ecs/github-oidc.tf                     # bedrock-ci environment, ECS scoping
infra/terraform/modules/ecs/main.tf                            # KMS perms, image_tag, lifecycle.ignore_changes
infra/terraform/modules/ecs/variables.tf                       # kms_key_arns, image_tag

infra/terraform/modules/elasticache/main.tf                    # auth_token, KMS CMK
infra/terraform/modules/elasticache/outputs.tf                 # connection_url with auth, auth_token

infra/terraform/modules/networking/flow-logs.tf                # NEW
infra/terraform/modules/networking/main.tf                     # drop wide egress on RDS/Redis SGs

infra/terraform/modules/rds/main.tf                            # deletion_protection, KMS CMK, PI, check block

infra/terraform/modules/s3/main.tf                             # KMS CMK, access logs bucket, deny-non-KMS, lifecycle
infra/terraform/modules/s3/outputs.tf                          # kms_key_arn

infra/terraform/modules/secrets/main.tf                        # KMS CMK on all 7 secrets
infra/terraform/modules/secrets/outputs.tf                     # kms_key_arn

infra/terraform/modules/security-baseline/alarms.tf            # NEW
infra/terraform/modules/security-baseline/budgets.tf           # NEW
infra/terraform/modules/security-baseline/cloudtrail.tf        # NEW
infra/terraform/modules/security-baseline/guardduty.tf         # NEW
infra/terraform/modules/security-baseline/inspector.tf         # NEW
infra/terraform/modules/security-baseline/main.tf              # NEW
infra/terraform/modules/security-baseline/outputs.tf           # NEW
infra/terraform/modules/security-baseline/securityhub.tf       # NEW
infra/terraform/modules/security-baseline/variables.tf         # NEW

infra/terraform/modules/ses/main.tf                            # fail-closed when sender_email empty
infra/terraform/modules/ses/outputs.tf                         # nullable when policy not created

infra/terraform/tfvars.archive/dev/terraform.tfvars            # MOVED from environments/dev
infra/terraform/tfvars.archive/staging/terraform.tfvars        # MOVED from environments/staging

.github/workflows/build-image.yml                              # NEW
.github/workflows/ci-backend-provider-matrix.yml               # bedrock-ci environment
.github/workflows/deploy-backend.yml                           # rewrite as workflow_dispatch only

docs/runbooks/domain-setup.md                                  # NEW
docs/runbooks/release.md                                       # NEW
docs/runbooks/secrets-bootstrap.md                             # NEW
docs/runbooks/state-bucket.md                                  # NEW
docs/runbooks/terraform.md                                     # NEW

docs/tech-debt.md                                              # TD-111 .. TD-115
```
