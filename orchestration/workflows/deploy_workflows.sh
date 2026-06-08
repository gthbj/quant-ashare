#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${REGION:-asia-east2}"
WORKFLOW_SERVICE_ACCOUNT="${WORKFLOW_SERVICE_ACCOUNT:-ashare-workflows-runtime@${PROJECT_ID}.iam.gserviceaccount.com}"
PIPELINE_CONTROL_URL="${PIPELINE_CONTROL_URL:-}"
WORKFLOW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is required" >&2
  exit 1
fi

if [[ -z "${PIPELINE_CONTROL_URL}" ]]; then
  echo "PIPELINE_CONTROL_URL is required" >&2
  exit 1
fi

PIPELINE_CONTROL_URL="${PIPELINE_CONTROL_URL%/}"

deploy_workflow() {
  local workflow_name="$1"
  local source_file="$2"
  local rendered
  rendered="$(mktemp)"
  sed "s|__PIPELINE_CONTROL_URL__|${PIPELINE_CONTROL_URL}|g" "${source_file}" > "${rendered}"
  gcloud workflows deploy "${workflow_name}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --service-account="${WORKFLOW_SERVICE_ACCOUNT}" \
    --source="${rendered}"
  rm -f "${rendered}"
}

deploy_workflow "ashare_warehouse_window_refresh" "${WORKFLOW_DIR}/ashare_warehouse_window_refresh.yaml"
deploy_workflow "ashare_ods_ingestion_daily" "${WORKFLOW_DIR}/ashare_ods_ingestion_daily.yaml"
