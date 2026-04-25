locals {
  bucket_name        = "${var.project_name}-uploads-${var.environment}"
  access_logs_bucket = "${var.project_name}-access-logs-${var.environment}"
  name_prefix        = "${var.project_name}-${var.environment}"
}

# Per-service KMS CMK for S3 uploads.
resource "aws_kms_key" "uploads" {
  description             = "${local.name_prefix} S3 uploads encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${local.name_prefix}-s3-uploads"
  }
}

resource "aws_kms_alias" "uploads" {
  name          = "alias/${local.name_prefix}-s3-uploads"
  target_key_id = aws_kms_key.uploads.key_id
}

resource "aws_s3_bucket" "uploads" {
  bucket = local.bucket_name

  tags = {
    Name = local.bucket_name
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.uploads.arn
    }
    bucket_key_enabled = true
  }
}

# --- Access log bucket ---
# Dedicated sink for S3 server access logs on the uploads bucket. Required by
# the audit's "who downloaded object X" requirement. Owns its own lifecycle
# (90d expiration) — access logs are noisy and only useful for forensic queries.
resource "aws_s3_bucket" "access_logs" {
  bucket = local.access_logs_bucket

  tags = {
    Name = local.access_logs_bucket
  }
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 server access logging delivery uses the log-delivery group, which AWS
# does not allow to write KMS-encrypted objects without a per-key policy
# carve-out. SSE-S3 (AES256) is the AWS-supported encryption for access-log
# destinations and is acceptable here: the logs themselves contain only
# request metadata (no object payloads). See
# https://docs.aws.amazon.com/AmazonS3/latest/userguide/enable-server-access-logging.html
resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "expire-access-logs"
    status = "Enabled"
    filter {}

    expiration {
      days = 90
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_logging" "uploads" {
  bucket        = aws_s3_bucket.uploads.id
  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "uploads/"
}

data "aws_iam_policy_document" "uploads_deny_unencrypted" {
  # Successor to Story 5.1 AC #2's deny-non-AES256 policy. With the bucket
  # default flipped to aws:kms (per-service CMK), we deny explicit non-KMS
  # PUTs. The deny-missing-header rule is no longer required: bucket-default
  # encryption transparently encrypts unmarked PUTs with the same CMK. The
  # backend uploader (backend/app/services/upload_service.py — see TD-XXX)
  # must send ServerSideEncryption="aws:kms" or omit the header entirely.
  statement {
    sid    = "DenyNonKMSEncryption"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]

    condition {
      test     = "StringNotEqualsIfExists"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }
  }

  # Deny unencrypted transport at all times.
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.uploads.arn,
      "${aws_s3_bucket.uploads.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  policy = data.aws_iam_policy_document.uploads_deny_unencrypted.json

  # Ensure the public-access block is applied before this policy. AWS's
  # "is this policy public?" heuristic only flags Allow+wildcard statements,
  # so our Deny+"*" policy is accepted — but an explicit dependency documents
  # the ordering and avoids any race on first apply.
  depends_on = [aws_s3_bucket_public_access_block.uploads]
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = length(var.cors_allowed_origins) > 0 ? var.cors_allowed_origins : ["https://${var.project_name}.vercel.app"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}

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
