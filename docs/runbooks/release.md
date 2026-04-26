# Release runbook — backend

## Day-to-day flow

Releases are manual. Merging to `main` does **not** auto-deploy.

1. **PR opened** — `ci-backend.yml` runs lint + tests on every PR. Merge gate requires green.
2. **PR merged** — `build-image.yml` builds and pushes three immutable images to ECR:
   - `kopiika-backend:<sha>` (API + worker code)
   - `kopiika-backend:worker-<sha>` (Celery worker, optimized image)
   - `kopiika-backend:beat-<sha>` (Celery beat)
3. **Decide to release** — go to Actions → **Deploy Backend** → *Run workflow*. Input:
   - `image_sha` — the commit sha you want to release. Verify the build summary on the corresponding `Build Backend Images` run says all 3 tags are present.
4. **Approve** — GitHub `production` environment requires you to click *Approve and run*.
5. **Watch** — workflow runs App Runner deploy (entrypoint.sh inside the API container runs `alembic upgrade head` automatically before uvicorn starts), then ECS worker + beat deploys (each waits for stability). Migrations are NOT run from CI — RDS is in private subnets and unreachable from GitHub runners.
6. **Smoke-test** — hit `/health` on App Runner; tail `/ecs/kopiika-prod-{worker,beat}` log groups for clean startup.

## First-deploy bootstrap

Terraform's App Runner + ECS task definitions reference `:bootstrap` / `:beat-bootstrap` tags that don't exist yet. App Runner needs the image at create time (CREATE_FAILED otherwise). Chicken-and-egg: ECR repo doesn't exist until terraform creates it. Resolution: targeted apply for ECR first, push images, then full apply.

```bash
export AWS_PROFILE=personal
export AWS_REGION=eu-central-1
export ECR_REPO=kopiika-backend
export ACCT=573562677570
export REGISTRY=$ACCT.dkr.ecr.$AWS_REGION.amazonaws.com

cd infra/terraform

# Step 1: Create ECR repo + its KMS key + lifecycle (only).
# Targeted apply leaves App Runner / ECS / etc. unprovisioned for now.
terraform apply -var-file=environments/prod/terraform.tfvars \
  -target=aws_kms_key.ecr \
  -target=aws_kms_alias.ecr \
  -target=aws_ecr_repository.backend \
  -target=aws_ecr_lifecycle_policy.backend

# Step 2: Push bootstrap images.
cd ../../backend

aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin $REGISTRY

# CRITICAL: --platform linux/amd64 is required when building from Apple
# Silicon (M-series) laptops. App Runner + ECS Fargate run x86-64; an
# ARM64 build will pull cleanly and then fail at container start with
# "exec format error" + container exit code 255. The flag is harmless on
# x86 hosts.

# Read the repo-root VERSION (must be done from repo root, not backend/).
APP_VERSION=$(cat ../VERSION)

# API + worker bootstrap from the API Dockerfile (worker has its own
# Dockerfile but the bootstrap image just needs to start; CI deploys
# replace it with the worker-specific image immediately).
docker build --platform linux/amd64 --build-arg APP_VERSION="$APP_VERSION" \
  -t $REGISTRY/$ECR_REPO:bootstrap -f Dockerfile .
docker push $REGISTRY/$ECR_REPO:bootstrap

# Beat has its own Dockerfile (different ENTRYPOINT).
docker build --platform linux/amd64 --build-arg APP_VERSION="$APP_VERSION" \
  -t $REGISTRY/$ECR_REPO:beat-bootstrap -f Dockerfile.beat .
docker push $REGISTRY/$ECR_REPO:beat-bootstrap

# Step 3: Full apply — everything else, App Runner picks up :bootstrap.
cd ../infra/terraform
terraform apply -var-file=environments/prod/terraform.tfvars
```

After the first apply, every subsequent release goes through the standard `build-image.yml` → `deploy-backend.yml` flow above. The `:bootstrap` and `:beat-bootstrap` tags can be left in ECR — they'll age out via the lifecycle policy if untagged or via prefix-rule retention if a future build accidentally tags them again.

## Break-glass: deploy without GitHub Actions

If GitHub Actions is down and you need to ship a fix:

```bash
SHA=<commit-sha>          # commit you want to release
export AWS_PROFILE=personal
export AWS_REGION=eu-central-1
export REPO=kopiika-backend
export REGISTRY=573562677570.dkr.ecr.eu-central-1.amazonaws.com

# Build + push from the laptop (skip if image already exists).
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin $REGISTRY
APP_VERSION=$(cat VERSION)
docker build --build-arg APP_VERSION="$APP_VERSION" -t $REGISTRY/$REPO:$SHA -f backend/Dockerfile backend/
docker push $REGISTRY/$REPO:$SHA
docker build --build-arg APP_VERSION="$APP_VERSION" -t $REGISTRY/$REPO:worker-$SHA -f backend/Dockerfile.worker backend/
docker push $REGISTRY/$REPO:worker-$SHA
docker build --build-arg APP_VERSION="$APP_VERSION" -t $REGISTRY/$REPO:beat-$SHA -f backend/Dockerfile.beat backend/
docker push $REGISTRY/$REPO:beat-$SHA

# Migrations run automatically inside the App Runner container's entrypoint.sh.
# Don't run them from your laptop unless you have a VPN/bastion to RDS — the
# DB is in private subnets and your machine can't reach it.

# App Runner.
aws apprunner update-service \
  --service-arn $(aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='kopiika-prod-api'].ServiceArn" --output text) \
  --source-configuration "ImageRepository={ImageIdentifier=$REGISTRY/$REPO:$SHA,ImageRepositoryType=ECR}"

# ECS worker + beat.
for kind in worker beat; do
  TASK_FAMILY=kopiika-prod-$kind
  CURRENT=$(aws ecs describe-task-definition --task-definition $TASK_FAMILY \
    --query 'taskDefinition' --output json)
  NEW=$(echo "$CURRENT" | jq --arg img "$REGISTRY/$REPO:$kind-$SHA" '
    .containerDefinitions[0].image = $img
    | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)
  ')
  REVISION=$(aws ecs register-task-definition --cli-input-json "$NEW" \
    --query 'taskDefinition.taskDefinitionArn' --output text)
  aws ecs update-service --cluster kopiika-prod-cluster --service $TASK_FAMILY \
    --task-definition $REVISION
done
```

## Rollback

Identify the last-known-good sha, then run **Deploy Backend** with that sha. Same flow as a forward release — ECR is immutable so the prior image is still there (subject to the lifecycle policy: last 20 sha-tagged images retained).

## Where to look when things break

- App Runner service health: `aws apprunner describe-service --service-arn ...`
- App Runner logs: CloudWatch → log group `/aws/apprunner/kopiika-prod-api/*`
- ECS service events: `aws ecs describe-services --cluster kopiika-prod-cluster --services kopiika-prod-{worker,beat}` → tail `events`
- ECS task logs: CloudWatch → `/ecs/kopiika-prod-{worker,beat}`
- WAF blocks: CloudWatch metrics → namespace `AWS/WAFV2` → `kopiika-prod-api-waf`. For sampled blocked requests, use `aws wafv2 get-sampled-requests --rule-metric-name kopiika-prod-waf-common ...`

## One-shot ops via ECS run-task

Some operations need to run **inside the VPC** (RDS in private subnets) but aren't part of the normal request path. Pattern: spawn a one-off Fargate task using the worker's task-def (which has the right env vars + IAM + network), override the command to whatever you need, task exits when done.

The two parameters that change per AWS account / re-apply: subnet IDs and the ECS SG. Pull them once and reuse.

```bash
export AWS_PROFILE=personal
export AWS_REGION=eu-central-1

# One-time: capture network config (or pin in shell rc)
PRIVATE_SUBNETS=$(aws ec2 describe-subnets --region $AWS_REGION \
  --filters "Name=tag:Name,Values=kopiika-prod-private-*" \
  --query 'Subnets[*].SubnetId' --output text | tr '\t' ',')
ECS_SG=$(aws ec2 describe-security-groups --region $AWS_REGION \
  --filters "Name=group-name,Values=kopiika-prod-sg-ecs-*" \
  --query 'SecurityGroups[0].GroupId' --output text)
NETWORK="awsvpcConfiguration={subnets=[$PRIVATE_SUBNETS],securityGroups=[$ECS_SG],assignPublicIp=DISABLED}"
```

### RAG corpus re-seed

Trigger after: changes under `backend/data/rag-corpus/`, embedding-model swap, `document_embeddings` schema migration. Idempotent (the seed script upserts via `ON CONFLICT DO UPDATE`).

```bash
TASK_ARN=$(aws ecs run-task --region $AWS_REGION \
  --cluster kopiika-prod-cluster --task-definition kopiika-prod-worker \
  --launch-type FARGATE \
  --network-configuration "$NETWORK" \
  --overrides '{"containerOverrides":[{"name":"worker","command":["python","-m","app.rag.seed"]}]}' \
  --query 'tasks[0].taskArn' --output text)
TASK_ID=${TASK_ARN##*/}
echo "Seed task: $TASK_ID"

# Wait for completion (~60-90s for ~50 markdown files)
aws ecs wait tasks-stopped --region $AWS_REGION \
  --cluster kopiika-prod-cluster --tasks "$TASK_ID"

# Verify exit code 0 and tail the final summary
aws ecs describe-tasks --region $AWS_REGION \
  --cluster kopiika-prod-cluster --tasks "$TASK_ID" \
  --query 'tasks[0].{ExitCode:containers[0].exitCode,StoppedReason:stoppedReason}'
aws logs tail /ecs/kopiika-prod-worker --region $AWS_REGION --since 5m \
  | grep -E "Seed complete|chunks for" | tail -10
```

Expected final log line: `Seed complete: <N> files processed, <M> total chunks upserted`.

### Interactive shell into a running worker (ECS Exec)

For ad-hoc DB queries, debugging session state, etc. The worker service has `enable_execute_command = true`; beat does not (single-purpose scheduler, no debug surface needed).

**One-time laptop setup:** install the AWS Session Manager plugin.

```bash
# macOS
brew install --cask session-manager-plugin

# Linux — see https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
```

**Connect:**

```bash
TASK_ID=$(AWS_PROFILE=personal aws ecs list-tasks --region eu-central-1 \
  --cluster kopiika-prod-cluster --service-name kopiika-prod-worker \
  --query 'taskArns[0]' --output text | awk -F/ '{print $NF}')

AWS_PROFILE=personal aws ecs execute-command --region eu-central-1 \
  --cluster kopiika-prod-cluster --task "$TASK_ID" \
  --container worker --interactive --command "/bin/bash"
```

Inside the container, all secret-injected env vars are present:

```bash
$ psql "$DATABASE_URL"
psql=> SELECT count(*) FROM users;
psql=> \dt
psql=> \q

$ python -c "from app.core.config import settings; print(settings.LLM_PROVIDER)"
```

**Audit:** every `execute-command` call records a CloudTrail event with the principal (assumed-role/your-user-session). The session itself is also logged via the SSM session log if you ever turn that on.

**Don't:**
- Don't `exit` and re-connect repeatedly — connections take ~5s to spin up. Stay in the shell.
- Don't run schema migrations from the shell — use the deploy workflow / run-task pattern so they're traceable.
- Don't run anything destructive (`DELETE FROM users` etc.) without an explicit go-ahead from yourself the next morning.

### Other run-task uses

Same pattern works for any one-shot DB-touching script. Replace the `command` array:

- `["alembic", "upgrade", "head"]` — manual migration outside the deploy flow
- `["python", "-m", "app.scripts.<script_name>"]` — any custom maintenance script
- `["psql", "$DATABASE_URL", "-c", "SELECT ..."]` — quick prod DB query without standing up a bastion (don't paste sensitive output anywhere)

The task definition's `secrets` field injects `DATABASE_URL`, `REDIS_URL`, etc. into the override-command's environment, so you can use them directly. KMS + Secrets Manager perms are already on the task role.
