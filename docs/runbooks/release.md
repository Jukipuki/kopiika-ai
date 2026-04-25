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

# API + worker bootstrap from the API Dockerfile (worker has its own
# Dockerfile but the bootstrap image just needs to start; CI deploys
# replace it with the worker-specific image immediately).
docker build --platform linux/amd64 -t $REGISTRY/$ECR_REPO:bootstrap -f Dockerfile .
docker push $REGISTRY/$ECR_REPO:bootstrap

# Beat has its own Dockerfile (different ENTRYPOINT).
docker build --platform linux/amd64 -t $REGISTRY/$ECR_REPO:beat-bootstrap -f Dockerfile.beat .
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
docker build -t $REGISTRY/$REPO:$SHA -f backend/Dockerfile backend/
docker push $REGISTRY/$REPO:$SHA
docker build -t $REGISTRY/$REPO:worker-$SHA -f backend/Dockerfile.worker backend/
docker push $REGISTRY/$REPO:worker-$SHA
docker build -t $REGISTRY/$REPO:beat-$SHA -f backend/Dockerfile.beat backend/
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
- WAF blocks: CloudWatch metrics → namespace `AWS/WAFV2` → `kopiika-prod-api-waf`
