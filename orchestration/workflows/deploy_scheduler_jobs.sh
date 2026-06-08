#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-data-aquarium}"
REGION="${REGION:-asia-east2}"
SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-${REGION}}"
JOB_NAME="${JOB_NAME:-ashare-pipeline-alert-checker}"
WORKFLOW_NAME="${WORKFLOW_NAME:-ashare_pipeline_alert_checker}"
SCHEDULE="${SCHEDULE:-0 * * * *}"
TIME_ZONE="${TIME_ZONE:-Asia/Shanghai}"
CALLER_SERVICE_ACCOUNT="${CALLER_SERVICE_ACCOUNT:-ashare-workflows-runtime@${PROJECT_ID}.iam.gserviceaccount.com}"
LOOKBACK_MINUTES="${LOOKBACK_MINUTES:-70}"
TARGET_URL="https://workflowexecutions.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/workflows/${WORKFLOW_NAME}/executions"
ARGUMENT=$(printf '{"project_id":"%s","lookback_minutes":%s,"write_log":true,"write_heartbeat":true}' "${PROJECT_ID}" "${LOOKBACK_MINUTES}")
BODY="$(
  ARGUMENT="${ARGUMENT}" python3 - <<'PY'
import json
import os

print(json.dumps({"argument": os.environ["ARGUMENT"]}))
PY
)"

COMMON_ARGS=(
  --project="${PROJECT_ID}"
  --location="${SCHEDULER_LOCATION}"
  --schedule="${SCHEDULE}"
  --time-zone="${TIME_ZONE}"
  --uri="${TARGET_URL}"
  --http-method=POST
  --message-body="${BODY}"
  --oauth-service-account-email="${CALLER_SERVICE_ACCOUNT}"
)

if gcloud scheduler jobs describe "${JOB_NAME}" --project="${PROJECT_ID}" --location="${SCHEDULER_LOCATION}" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "${JOB_NAME}" \
    "${COMMON_ARGS[@]}" \
    --update-headers="Content-Type=application/json"
else
  gcloud scheduler jobs create http "${JOB_NAME}" \
    "${COMMON_ARGS[@]}" \
    --headers="Content-Type=application/json"
fi

gcloud scheduler jobs describe "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --location="${SCHEDULER_LOCATION}" \
  --format='yaml(name,state,schedule,timeZone,httpTarget.uri,httpTarget.oauthToken.serviceAccountEmail)'
