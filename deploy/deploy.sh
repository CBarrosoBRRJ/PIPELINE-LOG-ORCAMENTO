#!/usr/bin/env bash
# Run from repository root, in Cloud Shell or GitHub Actions; never executes a load.
set -euo pipefail
: "${IMAGE:?Set the built image URL}"
: "${GCS_BUCKET:?Set the provisioned private bucket name}"
PROJECT_ID="gglobo-viu-dados-hdg-prd"
REGION="${REGION:-us-central1}"
SECRET_VERSION="${SECRET_VERSION:-1}"
[[ "$GCS_BUCKET" =~ ^[a-z0-9][a-z0-9._-]+[a-z0-9]$ ]] || { echo 'Invalid bucket name' >&2; exit 1; }
config_file="$(mktemp)"
trap 'rm -f -- "$config_file"' EXIT
sed "s/__SET_AT_DEPLOY__/${GCS_BUCKET}/g" deploy/gcp.env.yaml > "$config_file"
gcloud run jobs deploy pipeline-orcamento \
  --project "$PROJECT_ID" --region "$REGION" --image "$IMAGE" \
  --service-account "pipeline-orcamento@${PROJECT_ID}.iam.gserviceaccount.com" \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 3600s \
  --cpu 1 --memory 2Gi --args daily \
  --env-vars-file "$config_file" \
  --set-secrets "MONDAY_API_TOKEN=monday-api-token:${SECRET_VERSION}"
