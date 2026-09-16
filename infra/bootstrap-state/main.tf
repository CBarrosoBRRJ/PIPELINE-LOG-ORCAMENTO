terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.50.0"
    }
  }
}

provider "google" {
  project = "gglobo-viu-dados-hdg-prd"
  region  = "us-central1"
}

resource "google_storage_bucket" "terraform_state" {
  name          = "gglobo-viu-terraform-state-prd"
  project = "gglobo-viu-dados-hdg-prd"
  location      = "us-central1"
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  soft_delete_policy {
    retention_duration_seconds = 604800
  }

  lifecycle {
    prevent_destroy = true
  }
}

data "google_iam_policy" "terraform_state_admins" {
  binding {
    role = "roles/storage.admin"
    members = [
      "group:GCP-Administrators-gglobo-viu-dados-hdg-prd@g.globo",
    ]
  }
}

resource "google_storage_bucket_iam_policy" "terraform_state_access" {
  bucket      = google_storage_bucket.terraform_state.name
  policy_data = data.google_iam_policy.terraform_state_admins.policy_data
}