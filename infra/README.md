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

### Initialize (first time per environment)

```bash
cd infra/terraform
terraform init
```

### Plan Changes

```bash
terraform plan -var-file=environments/dev/terraform.tfvars
```

### Apply Changes

```bash
terraform apply -var-file=environments/dev/terraform.tfvars
```

### Destroy (dev only)

```bash
terraform destroy -var-file=environments/dev/terraform.tfvars
```

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
