# Kopiika Infrastructure

AWS infrastructure provisioned with Terraform.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- AWS CLI configured with appropriate credentials
- S3 bucket `kopiika-terraform-state` for state management (uses native S3 lock file, no DynamoDB needed)

### State Backend Bootstrap

Before first use, create the state bucket and uncomment the backend config in `backend.tf`:

```bash
aws s3api create-bucket \
  --bucket kopiika-terraform-state \
  --region eu-central-1 \
  --create-bucket-configuration LocationConstraint=eu-central-1
```

Then uncomment the S3 backend block in `infra/terraform/backend.tf` and run `terraform init`.

## Directory Structure

```
infra/terraform/
├── main.tf              # Root module — wires all child modules
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── providers.tf         # AWS provider config
├── backend.tf           # S3 state backend
├── environments/
│   ├── dev/terraform.tfvars
│   ├── staging/terraform.tfvars
│   └── prod/terraform.tfvars
└── modules/
    ├── networking/      # VPC, subnets, security groups, NAT, endpoints
    ├── rds/             # PostgreSQL 16 + pgvector
    ├── elasticache/     # Redis 7
    ├── cognito/         # User pool + app clients
    ├── s3/              # Upload bucket
    ├── ses/             # Email service
    ├── secrets/         # Secrets Manager
    ├── app-runner/      # API service
    └── ecs/             # Celery worker cluster
```

## Usage

Use the `Makefile` in `infra/terraform/` — it always passes the per-env
`-var-file` so a forgotten flag can't silently evaluate count-gated
resources to their `false` defaults (the 2026-04-26 prod near-miss had a
plain `terraform plan` propose 9 destroys including the API custom domain
and IAM roles, all spurious — root cause was the missing `-var-file`).

`ENV` defaults to `prod` (the only currently-live env; dev/staging
tfvars are in `tfvars.archive/`). Override per-invocation if needed.

```bash
cd infra/terraform
make init                         # one-time
make plan                         # writes tfplan with -var-file pre-supplied
make apply                        # consumes tfplan if present
```

Other targets: `make fmt`, `make validate`, `make destroy` (refuses
ENV=prod), and `make tf CMD="state list"` for arbitrary subcommands.

### Direct terraform invocation (escape hatch)

If you need to run terraform directly, **always** pass the var-file:

```bash
terraform plan -var-file=environments/prod/terraform.tfvars
```

Skipping the flag will appear to work but will mark every count-gated
resource (`count = var.<flag> ? 1 : 0`) for destruction.

## Environments

| Environment | RDS Instance     | ElastiCache     | App Runner Scale | ECS Workers |
|-------------|------------------|-----------------|------------------|-------------|
| dev         | db.t4g.micro     | cache.t4g.micro | min 1, max 1     | 1           |
| staging     | db.t4g.small     | cache.t4g.micro | min 1, max 2     | 1           |
| prod        | db.t4g.small     | cache.t4g.micro | min 1, max 4     | 1           |

## Environment Variables

After provisioning, the following environment variables are needed by backend and frontend services. Values are stored in AWS Secrets Manager under the `kopiika/{env}/` path.

### Backend

| Variable               | Description                          | Source                    |
|------------------------|--------------------------------------|---------------------------|
| `DATABASE_URL`         | PostgreSQL connection string         | Secrets Manager           |
| `REDIS_URL`            | Redis connection URL                 | Secrets Manager           |
| `AWS_REGION`           | AWS region                           | terraform.tfvars          |
| `COGNITO_USER_POOL_ID` | Cognito user pool ID                 | Secrets Manager           |
| `COGNITO_APP_CLIENT_ID`| Cognito app client ID                | Secrets Manager           |
| `S3_BUCKET_NAME`       | S3 uploads bucket                    | Secrets Manager           |
| `SES_SENDER_EMAIL`     | Verified sender email                | Secrets Manager           |
| `AWS_SECRETS_PREFIX`   | Secrets path prefix (`kopiika/{env}`)| Environment config        |

### Frontend

| Variable                           | Description                 |
|------------------------------------|-----------------------------|
| `NEXT_PUBLIC_API_URL`              | Backend API URL             |
| `NEXT_PUBLIC_COGNITO_USER_POOL_ID` | Cognito user pool ID        |
| `NEXT_PUBLIC_COGNITO_CLIENT_ID`    | Cognito app client ID       |
| `NEXTAUTH_URL`                     | NextAuth base URL           |
| `NEXTAUTH_SECRET`                  | NextAuth secret key         |
