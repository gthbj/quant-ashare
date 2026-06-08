#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-data-aquarium}"
REGION="${REGION:-asia-east2}"
SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-${REGION}}"
TIME_ZONE="${TIME_ZONE:-Asia/Shanghai}"
CALLER_SERVICE_ACCOUNT="${CALLER_SERVICE_ACCOUNT:-ashare-scheduler-invoker@${PROJECT_ID}.iam.gserviceaccount.com}"
JOB_GROUP="${JOB_GROUP:-all}"
ENABLE_JOBS="${ENABLE_JOBS:-true}"

ALERT_JOB_NAME="${ALERT_JOB_NAME:-ashare-pipeline-alert-checker}"
ALERT_WORKFLOW_NAME="${ALERT_WORKFLOW_NAME:-ashare_pipeline_alert_checker}"
ALERT_SCHEDULE="${ALERT_SCHEDULE:-0 * * * *}"
ALERT_LOOKBACK_MINUTES="${ALERT_LOOKBACK_MINUTES:-70}"

ODS_JOB_NAME="${ODS_JOB_NAME:-ashare-ods-ingestion-daily}"
ODS_WORKFLOW_NAME="${ODS_WORKFLOW_NAME:-ashare_ods_ingestion_daily}"
ODS_SCHEDULE="${ODS_SCHEDULE:-0 20 * * *}"
ODS_RUN_LABEL="${ODS_RUN_LABEL:-scheduled_daily_ingestion}"
ODS_PIPELINE_DRY_RUN="${ODS_PIPELINE_DRY_RUN:-false}"
ODS_SCHEDULED_RUN="${ODS_SCHEDULED_RUN:-true}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is required" >&2
  exit 1
fi

create_execution_body() {
  local argument_json="$1"
  ARGUMENT_JSON="${argument_json}" python3 - <<'PY'
import json
import os

print(json.dumps({"argument": os.environ["ARGUMENT_JSON"]}))
PY
}

upsert_scheduler_job() {
  local job_name="$1"
  local workflow_name="$2"
  local schedule="$3"
  local argument_json="$4"
  local body
  local target_url

  body="$(create_execution_body "${argument_json}")"
  target_url="https://workflowexecutions.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/workflows/${workflow_name}/executions"

  common_args=(
    --project="${PROJECT_ID}"
    --location="${SCHEDULER_LOCATION}"
    --schedule="${schedule}"
    --time-zone="${TIME_ZONE}"
    --uri="${target_url}"
    --http-method=POST
    --message-body="${body}"
    --oauth-service-account-email="${CALLER_SERVICE_ACCOUNT}"
  )

  if gcloud scheduler jobs describe "${job_name}" --project="${PROJECT_ID}" --location="${SCHEDULER_LOCATION}" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "${job_name}" \
      "${common_args[@]}" \
      --update-headers="Content-Type=application/json"
  else
    gcloud scheduler jobs create http "${job_name}" \
      "${common_args[@]}" \
      --headers="Content-Type=application/json"
  fi

  if [[ "${ENABLE_JOBS}" == "true" ]]; then
    gcloud scheduler jobs resume "${job_name}" \
      --project="${PROJECT_ID}" \
      --location="${SCHEDULER_LOCATION}" >/dev/null
  else
    gcloud scheduler jobs pause "${job_name}" \
      --project="${PROJECT_ID}" \
      --location="${SCHEDULER_LOCATION}" >/dev/null
  fi
}

deploy_alert_checker_job() {
  local argument_json
  argument_json="$(printf '{"project_id":"%s","lookback_minutes":%s,"write_log":true,"write_heartbeat":true}' "${PROJECT_ID}" "${ALERT_LOOKBACK_MINUTES}")"
  upsert_scheduler_job "${ALERT_JOB_NAME}" "${ALERT_WORKFLOW_NAME}" "${ALERT_SCHEDULE}" "${argument_json}"
}

deploy_ods_daily_job() {
  local argument_json
  argument_json="$(printf '{"pipeline_dry_run":%s,"scheduled_run":%s,"run_label":"%s"}' "${ODS_PIPELINE_DRY_RUN}" "${ODS_SCHEDULED_RUN}" "${ODS_RUN_LABEL}")"
  upsert_scheduler_job "${ODS_JOB_NAME}" "${ODS_WORKFLOW_NAME}" "${ODS_SCHEDULE}" "${argument_json}"
}

case "${JOB_GROUP}" in
  alert-checker)
    deploy_alert_checker_job
    ;;
  ods-daily)
    deploy_ods_daily_job
    ;;
  all)
    deploy_alert_checker_job
    deploy_ods_daily_job
    ;;
  *)
    echo "Unsupported JOB_GROUP=${JOB_GROUP}. Use alert-checker, ods-daily, or all." >&2
    exit 1
    ;;
esac

for job_name in "${ALERT_JOB_NAME}" "${ODS_JOB_NAME}"; do
  if gcloud scheduler jobs describe "${job_name}" --project="${PROJECT_ID}" --location="${SCHEDULER_LOCATION}" >/dev/null 2>&1; then
    gcloud scheduler jobs describe "${job_name}" \
      --project="${PROJECT_ID}" \
      --location="${SCHEDULER_LOCATION}" \
      --format='yaml(name,state,schedule,timeZone,httpTarget.oauthToken.serviceAccountEmail,httpTarget.uri,httpTarget.body)'
  fi
done
