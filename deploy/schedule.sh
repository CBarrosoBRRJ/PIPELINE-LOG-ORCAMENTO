#!/usr/bin/env bash
# Only after initial load, reconciliation and a successful manual daily execution.
set -euo pipefail
PROJECT_ID="gglobo-viu-dados-hdg-prd"
REGION="${REGION:-us-central1}"
SCHEDULER_SA="scheduler-sla-orcamento@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud run jobs add-iam-policy-binding pipeline-orcamento \
  --project "$PROJECT_ID" --region "$REGION" \
  --member "serviceAccount:${SCHEDULER_SA}" --role roles/run.invoker
gcloud scheduler jobs create http pipeline-orcamento-diario \
  --project "$PROJECT_ID" --location "$REGION" \
  --schedule '0 6 * * *' --time-zone America/Sao_Paulo \
  --uri "https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/pipeline-orcamento:run" \
  --http-method POST --message-body '{}' \
  --oauth-service-account-email "$SCHEDULER_SA" --max-retry-attempts 0
