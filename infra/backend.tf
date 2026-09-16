terraform {
  backend "gcs" {
    bucket = "gglobo-viu-terraform-state-prd"
    prefix = "infra/sla-orcamento/prod"
  }
}