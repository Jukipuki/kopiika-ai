locals {
  bucket_name = "${var.project_name}-uploads-${var.environment}"
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
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

data "aws_iam_policy_document" "uploads_deny_unencrypted" {
  # Story 5.1 AC #2 (strict): deny any PutObject that is not explicitly tagged
  # as AES256 server-side-encrypted. Two statements are required to cover both
  # the "wrong algorithm" and "header missing" cases:
  #   1. DenyNonAES256Encryption — explicit header present but != AES256
  #   2. DenyMissingEncryptionHeader — header absent entirely (Null condition)
  # The backend caller (backend/app/services/upload_service.py) is updated in
  # the same story to send ServerSideEncryption="AES256" so this policy does
  # not break uploads. Bucket-default SSE-S3 remains configured as a
  # belt-and-suspenders fallback.
  statement {
    sid    = "DenyNonAES256Encryption"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]

    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["AES256"]
    }
  }

  statement {
    sid    = "DenyMissingEncryptionHeader"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]

    condition {
      test     = "Null"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["true"]
    }
  }

  # Belt-and-suspenders: also deny unencrypted transport.
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
}
