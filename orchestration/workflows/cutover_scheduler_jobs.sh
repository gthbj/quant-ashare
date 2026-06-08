#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-data-aquarium}"
REGION="${REGION:-asia-east2}"
COMPOSER_ENVIRONMENT="${COMPOSER_ENVIRONMENT:-ashare-composer}"
SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-${REGION}}"
RESUME_SCHEDULER_JOBS="${RESUME_SCHEDULER_JOBS:-false}"
WORKFLOW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

composer_exists() {
  gcloud composer environments describe "${COMPOSER_ENVIRONMENT}" \
    --project="${PROJECT_ID}" \
    --location "${REGION}" >/dev/null 2>&1
}

pause_dag() {
  local dag_id="$1"
  if ! composer_exists; then
    echo "Composer environment ${COMPOSER_ENVIRONMENT} not found; skipping pause for DAG ${dag_id}."
    return 0
  fi
  gcloud composer environments run "${COMPOSER_ENVIRONMENT}" \
    --project="${PROJECT_ID}" \
    --location "${REGION}" \
    dags pause -- "${dag_id}" >/dev/null
}

"${WORKFLOW_DIR}/bootstrap_scheduler_iam.sh"
ENABLE_JOBS=false "${WORKFLOW_DIR}/deploy_scheduler_jobs.sh"

pause_dag "ashare_daily_pipeline_v0"
pause_dag "ashare_ods_ingestion_daily"
pause_dag "ashare_warehouse_window_refresh"
pause_dag "ashare_pipeline_alert_checker"
pause_dag "ashare_warehouse_full_rebuild"

if [[ "${RESUME_SCHEDULER_JOBS}" == "true" ]]; then
  ENABLE_JOBS=true "${WORKFLOW_DIR}/deploy_scheduler_jobs.sh"
else
  echo "Scheduler jobs remain PAUSED."
  echo "Run a manual validation fire, then rerun with RESUME_SCHEDULER_JOBS=true to enable production schedules."
fi

gcloud scheduler jobs describe ashare-ods-ingestion-daily \
  --project="${PROJECT_ID}" \
  --location="${SCHEDULER_LOCATION}" \
  --format='yaml(name,state,schedule,httpTarget.oauthToken.serviceAccountEmail,httpTarget.uri)'

gcloud scheduler jobs describe ashare-pipeline-alert-checker \
  --project="${PROJECT_ID}" \
  --location="${SCHEDULER_LOCATION}" \
  --format='yaml(name,state,schedule,httpTarget.oauthToken.serviceAccountEmail,httpTarget.uri)'
