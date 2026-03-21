# Uncomment after creating the S3 state bucket (see infra/README.md bootstrap steps)
# and configuring valid AWS credentials.
#
# terraform {
#   backend "s3" {
#     bucket       = "kopiika-terraform-state"
#     key          = "terraform.tfstate"
#     region       = "eu-central-1"
#     use_lockfile = true
#     encrypt      = true
#   }
# }
