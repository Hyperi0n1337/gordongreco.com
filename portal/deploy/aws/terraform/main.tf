provider "aws" { region = var.region }

data "aws_caller_identity" "current" {}

resource "aws_kms_key" "portal" {
  description             = "Gordon Greco portal object and TOTP envelope encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}
resource "aws_kms_alias" "portal" {
  name          = "alias/${var.name_prefix}"
  target_key_id = aws_kms_key.portal.key_id
}

locals { buckets = toset(["${var.name_prefix}-quarantine", "${var.name_prefix}-clean"]) }
resource "aws_s3_bucket" "private" {
  for_each = local.buckets
  bucket   = each.value
}
resource "aws_s3_bucket_public_access_block" "private" {
  for_each                = aws_s3_bucket.private
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "private" {
  for_each = aws_s3_bucket.private
  bucket   = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.portal.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}
resource "aws_s3_bucket_versioning" "private" {
  for_each = aws_s3_bucket.private
  bucket   = each.value.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_lifecycle_configuration" "quarantine" {
  bucket = aws_s3_bucket.private["${var.name_prefix}-quarantine"].id
  rule {
    id     = "quarantine-expiry"
    status = "Enabled"
    filter { prefix = "quarantine/" }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
    expiration { days = 7 }
  }
}
