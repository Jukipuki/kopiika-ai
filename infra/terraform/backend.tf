# State bucket configuration: see docs/runbooks/state-bucket.md.
# Uses S3 native locking (Terraform 1.10+); no DynamoDB lock table required.
terraform {
  backend "s3" {
    bucket       = "kopiika-terraform-state"
    key          = "terraform.tfstate"
    region       = "eu-central-1"
    use_lockfile = true
    encrypt      = true
  }
}
