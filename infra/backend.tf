terraform {
  backend "s3" {
    bucket  = "api-jmv-tf-state-dev-jorge"
    key     = "infra/terraform.tfstate"
    region  = "us-east-1"
    encrypt = true
  }
}
