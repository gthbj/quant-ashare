#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-data-aquarium}"
REGION="${REGION:-asia-east2}"
SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-${REGION}}"
PIPELINE_CONTROL_URL="${PIPELINE_CONTROL_URL:-}"
JOB_NAME="${JOB_NAME:-ashare-pipeline-alert-checker}"
SCHEDULE="${SCHEDULE:-0 * * * *}"
TIME_ZONE="${TIME_ZONE:-Asia/Shanghai}"
OIDC_SERVICE_ACCOUNT="${OIDC_SERVICE_ACCOUNT:-ashare-workflows-runtime@${PROJECT_ID}.iam.gserviceaccount.com}"
LOOKBACK_MINUTES="${LOOKBACK_MINUTES:-70}"

if [[ -z "${PIPELINE_CONTROL_URL}" ]]; then
  echo "PIPELINE_CONTROL_URL is required" >&2
  exit 1
fi

PIPELINE_CONTROL_URL="${PIPELINE_CONTROL_URL%/}"
TARGET_URL="${PIPELINE_CONTROL_URL}/v1/tasks/alert-check"
BODY=$(printf '{"project_id":"%s","lookback_minutes":%s,"write_log":true,"write_heartbeat":true}' "${PROJECT_ID}" "${LOOKBACK_MINUTES}")

COMMON_ARGS=(
  --project="${PROJECT_ID}"
  --location="${SCHEDULER_LOCATION}"
  --schedule="${SCHEDULE}"
  --time-zone="${TIME_ZONE}"
  --uri="${TARGET_URL}"
  --http-method=POST
  --headers="Content-Type=application/json"
  --message-body="${BODY}"
  --oidc-service-account-email="${OIDC_SERVICE_ACCOUNT}"
  --oidc-token-audience="${PIPELINE_CONTROL_URL}"
)

if gcloud scheduler jobs describe "${JOB_NAME}" --project="${PROJECT_ID}" --location="${SCHEDULER_LOCATION}" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "${JOB_NAME}" "${COMMON_ARGS[@]}"
else
  gcloud scheduler jobs create http "${JOB_NAME}" "${COMMON_ARGS[@]}"
fi

gcloud scheduler jobs describe "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --location="${SCHEDULER_LOCATION}" \
  --format='yaml(name,state,schedule,timeZone,httpTarget.uri,httpTarget.oidcToken.serviceAccountEmail)'
