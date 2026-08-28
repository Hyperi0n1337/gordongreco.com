output "kms_key_arn" {value = aws_kms_key.portal.arn}
output "bucket_names" {value = {for key, bucket in aws_s3_bucket.private : key => bucket.id}}
