#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-data-aquarium}"
REGION="${REGION:-asia-east2}"
COMPOSER_ENVIRONMENT="${COMPOSER_ENVIRONMENT:-ashare-composer}"
SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-${REGION}}"
WORKFLOW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

pause_dag() {
  local dag_id="$1"
  gcloud composer environments run "${COMPOSER_ENVIRONMENT}" \
    --project="${PROJECT_ID}" \
    --location "${REGION}" \
    dags pause -- "${dag_id}" >/dev/null
}

"${WORKFLOW_DIR}/bootstrap_scheduler_iam.sh"
"${WORKFLOW_DIR}/deploy_scheduler_jobs.sh"

pause_dag "ashare_daily_pipeline_v0"
pause_dag "ashare_ods_ingestion_daily"
pause_dag "ashare_warehouse_window_refresh"
pause_dag "ashare_pipeline_alert_checker"
pause_dag "ashare_warehouse_full_rebuild"

gcloud scheduler jobs describe ashare-ods-ingestion-daily \
  --project="${PROJECT_ID}" \
  --location="${SCHEDULER_LOCATION}" \
  --format='yaml(name,state,schedule,httpTarget.oauthToken.serviceAccountEmail,httpTarget.uri)'

gcloud scheduler jobs describe ashare-pipeline-alert-checker \
  --project="${PROJECT_ID}" \
  --location="${SCHEDULER_LOCATION}" \
  --format='yaml(name,state,schedule,httpTarget.oauthToken.serviceAccountEmail,httpTarget.uri)'
