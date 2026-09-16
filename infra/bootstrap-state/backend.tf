terraform {
  backend "gcs" {
    bucket = "gglobo-viu-terraform-state-prd"
    prefix = "infra/bootstrap-state/prod"
  }
}