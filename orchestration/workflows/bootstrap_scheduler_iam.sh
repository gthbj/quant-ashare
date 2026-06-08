#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-data-aquarium}"
REGION="${REGION:-asia-east2}"
LOCK_BUCKET="${LOCK_BUCKET:-ashare-artifacts}"
PIPELINE_CONTROL_SERVICE="${PIPELINE_CONTROL_SERVICE:-ashare-pipeline-control}"
SCHEDULER_CALLER_SERVICE_ACCOUNT="${SCHEDULER_CALLER_SERVICE_ACCOUNT:-ashare-scheduler-invoker@${PROJECT_ID}.iam.gserviceaccount.com}"
WORKFLOW_RUNTIME_SERVICE_ACCOUNT="${WORKFLOW_RUNTIME_SERVICE_ACCOUNT:-ashare-workflows-runtime@${PROJECT_ID}.iam.gserviceaccount.com}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is required" >&2
  exit 1
fi

ensure_service_account() {
  local email="$1"
  local display_name="$2"
  if ! gcloud iam service-accounts describe "${email}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${email%@*}" \
      --project="${PROJECT_ID}" \
      --display-name="${display_name}" >/dev/null
  fi
}

ensure_project_role() {
  local member="$1"
  local role="$2"
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="${member}" \
    --role="${role}" >/dev/null
}

ensure_bucket_role() {
  local member="$1"
  local role="$2"
  gcloud storage buckets add-iam-policy-binding "gs://${LOCK_BUCKET}" \
    --member="${member}" \
    --role="${role}" >/dev/null
}

ensure_run_service_role() {
  local member="$1"
  local role="$2"
  gcloud run services add-iam-policy-binding "${PIPELINE_CONTROL_SERVICE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --member="${member}" \
    --role="${role}" >/dev/null
}

ensure_service_account "${SCHEDULER_CALLER_SERVICE_ACCOUNT}" "Ashare Scheduler Invoker"

ensure_project_role "serviceAccount:${SCHEDULER_CALLER_SERVICE_ACCOUNT}" "roles/workflows.invoker"

ensure_project_role "serviceAccount:${WORKFLOW_RUNTIME_SERVICE_ACCOUNT}" "roles/bigquery.dataEditor"
ensure_project_role "serviceAccount:${WORKFLOW_RUNTIME_SERVICE_ACCOUNT}" "roles/bigquery.jobUser"
ensure_project_role "serviceAccount:${WORKFLOW_RUNTIME_SERVICE_ACCOUNT}" "roles/logging.logWriter"
ensure_project_role "serviceAccount:${WORKFLOW_RUNTIME_SERVICE_ACCOUNT}" "roles/run.developer"
ensure_project_role "serviceAccount:${WORKFLOW_RUNTIME_SERVICE_ACCOUNT}" "roles/workflows.invoker"

ensure_bucket_role "serviceAccount:${WORKFLOW_RUNTIME_SERVICE_ACCOUNT}" "roles/storage.objectAdmin"
ensure_run_service_role "serviceAccount:${WORKFLOW_RUNTIME_SERVICE_ACCOUNT}" "roles/run.invoker"

printf 'scheduler_caller=%s\n' "${SCHEDULER_CALLER_SERVICE_ACCOUNT}"
printf 'workflow_runtime=%s\n' "${WORKFLOW_RUNTIME_SERVICE_ACCOUNT}"
printf 'lock_bucket=%s\n' "${LOCK_BUCKET}"
printf 'pipeline_control_service=%s\n' "${PIPELINE_CONTROL_SERVICE}"
