terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

variable "project_id" {
  type    = string
  default = "gglobo-viu-dados-hdg-prd"
}

variable "dataset_id" {
  type    = string
  default = "viu_agenciamento"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "bucket_name" {
  type        = string
  description = "Nome globalmente único, definido pela equipe GCP."
}

variable "github_repository" {
  type    = string
  default = "CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO"
}

variable "github_repository_id" {
  type        = string
  description = "ID numérico imutável do repositório GitHub (API repos/owner/repo)."
}

variable "github_owner_id" {
  type        = string
  description = "ID numérico imutável do proprietário GitHub."
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "secretmanager.googleapis.com",
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com"
  ])

  service            = each.key
  disable_on_destroy = false
}

resource "google_storage_bucket" "state" {
  name                        = var.bucket_name
  location                    = var.region
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

  depends_on = [google_project_service.apis]

  # No TTL on generations: checkpoints are the only durable source history.
}

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "viu-pipelines"
  format        = "DOCKER"

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "runtime" {
  account_id   = "pipeline-orcamento"
  display_name = "Monday SLA: runtime"

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "scheduler" {
  account_id   = "scheduler-sla-orcamento"
  display_name = "Monday SLA: scheduler"

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "deployer" {
  account_id   = "deploy-sla-orcamento"
  display_name = "Monday SLA: GitHub deployment"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "bq_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_bigquery_dataset_iam_member" "writer" {
  dataset_id = var.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket_iam_member" "state_writer" {
  bucket = google_storage_bucket.state.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_custom_role" "bucket_metadata" {
  role_id     = "slaStateBucketMetadata"
  title       = "SLA: read load-source bucket metadata"
  permissions = ["storage.buckets.get"]

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "state_metadata" {
  bucket = google_storage_bucket.state.name
  role   = google_project_iam_custom_role.bucket_metadata.name
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret" "monday" {
  secret_id = "monday-api-token"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }

  # O valor do token será adicionado pelo console.
}

resource "google_secret_manager_secret_iam_member" "token_reader" {
  secret_id = google_secret_manager_secret.monday.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "deploy_run" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deploy_services" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "deploy_act_as" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_artifact_registry_repository_iam_member" "deploy_push" {
  location   = var.region
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "sla-orcamento-github"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"

  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
  }

  attribute_condition = "assertion.repository_id == '${var.github_repository_id}' && assertion.repository_owner_id == '${var.github_owner_id}' && assertion.ref == 'refs/heads/main' && assertion.repository == '${var.github_repository}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_deploy" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${var.github_repository_id}"
}

output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_service_account" {
  value = google_service_account.deployer.email
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

output "bucket_name" {
  value = google_storage_bucket.state.name
}