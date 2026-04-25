# Terraform state bucket — `kopiika-terraform-state`

The S3 bucket holding Terraform state. **Not managed by Terraform** to avoid the chicken-and-egg problem (the TF that manages the state bucket needs its own state somewhere). Configured once via AWS CLI; documented here so the configuration is reviewable.

## Configuration

- **Bucket:** `kopiika-terraform-state`
- **Region:** `eu-central-1`
- **Account:** `573562677570`
- **State key:** `terraform.tfstate`
- **Locking:** S3 native (`use_lockfile = true` in [backend.tf](../../infra/terraform/backend.tf)) — no DynamoDB needed (Terraform 1.10+).
- **Encryption:** SSE-S3 (AES256). KMS CMK migration deferred — would require re-encrypting all state versions.
- **Versioning:** Enabled.
- **Lifecycle:** Noncurrent versions expire at 365d, incomplete multipart uploads abort at 7d.
- **Public access block:** All four blocks on.
- **Bucket policy:** Denies non-TLS access and unencrypted PUTs.

## Bootstrap commands (already applied)

If the bucket ever needs to be recreated, run these in order:

```bash
export AWS_PROFILE=personal
export REGION=eu-central-1
export BUCKET=kopiika-terraform-state

aws s3api create-bucket --bucket $BUCKET --region $REGION \
  --create-bucket-configuration LocationConstraint=$REGION

aws s3api put-public-access-block --bucket $BUCKET --region $REGION \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws s3api put-bucket-encryption --bucket $BUCKET --region $REGION \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-bucket-versioning --bucket $BUCKET --region $REGION \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-lifecycle-configuration --bucket $BUCKET --region $REGION \
  --lifecycle-configuration '{
    "Rules":[{
      "ID":"expire-noncurrent-state-versions",
      "Status":"Enabled",
      "Filter":{},
      "NoncurrentVersionExpiration":{"NoncurrentDays":365},
      "AbortIncompleteMultipartUpload":{"DaysAfterInitiation":7}
    }]
  }'

# Bucket policy (deny non-TLS + deny unencrypted PUT) — see /tmp/state-bucket-policy.json
# or reconstruct from this runbook.
```

## Recovery scenarios

### Accidental state corruption / deletion

Versioning is on. Restore the previous version of `terraform.tfstate`:

```bash
aws s3api list-object-versions --bucket $BUCKET --prefix terraform.tfstate --region $REGION
aws s3api copy-object --bucket $BUCKET --region $REGION \
  --copy-source "$BUCKET/terraform.tfstate?versionId=<VERSION_ID>" \
  --key terraform.tfstate
```

### Lock stuck

S3 native locking writes a `.tflock` object. If a CI run dies mid-apply, the lock can stick:

```bash
aws s3 ls s3://$BUCKET/ --region $REGION | grep tflock
aws s3 rm s3://$BUCKET/terraform.tfstate.tflock --region $REGION
```

Only do this if you're certain no other apply is running.

## Open follow-ups

- Migrate to per-bucket KMS CMK (TD-NNN). Defer until first incident; current SSE-S3 is acceptable for a solo project with no state-export risk.
