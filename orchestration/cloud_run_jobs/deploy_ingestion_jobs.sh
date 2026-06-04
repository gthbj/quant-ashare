#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-data-aquarium}"
REGION="${REGION:-asia-east2}"
IMAGE_URI="${IMAGE_URI:-asia-east2-docker.pkg.dev/${PROJECT_ID}/ashare/ingestion:latest}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-sa-ashare-ingestion@${PROJECT_ID}.iam.gserviceaccount.com}"
TUSHARE_SECRET="${TUSHARE_SECRET:-tushare-token}"
INGESTION_MANIFEST="${INGESTION_MANIFEST:-configs/ingestion/ods_current_scope_v0.yml}"
TUSHARE_HTTP_URL="${TUSHARE_HTTP_URL:-https://api.tushare.pro}"
TUSHARE_ROW_LIMIT="${TUSHARE_ROW_LIMIT:-5000}"
TUSHARE_THROTTLE_SECONDS="${TUSHARE_THROTTLE_SECONDS:-0.3}"
MAX_RETRIES="${MAX_RETRIES:-0}"
VPC_NETWORK="${VPC_NETWORK:-default}"
VPC_SUBNET="${VPC_SUBNET:-default}"
VPC_EGRESS="${VPC_EGRESS:-all-traffic}"
DRY_RUN_ARGS="${DRY_RUN_ARGS:---dry-run}"

deploy_job() {
  local job_name="$1"
  local endpoint_group="$2"
  local args="--endpoint-group,${endpoint_group}"

  if [[ -n "${DRY_RUN_ARGS}" ]]; then
    args="${args},${DRY_RUN_ARGS}"
  fi

  gcloud run jobs deploy "${job_name}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --image="${IMAGE_URI}" \
    --service-account="${SERVICE_ACCOUNT}" \
    --max-retries="${MAX_RETRIES}" \
    --network="${VPC_NETWORK}" \
    --subnet="${VPC_SUBNET}" \
    --vpc-egress="${VPC_EGRESS}" \
    --set-env-vars="INGESTION_MANIFEST=${INGESTION_MANIFEST},TUSHARE_HTTP_URL=${TUSHARE_HTTP_URL},TUSHARE_ROW_LIMIT=${TUSHARE_ROW_LIMIT},TUSHARE_THROTTLE_SECONDS=${TUSHARE_THROTTLE_SECONDS}" \
    --set-secrets="TUSHARE_TOKEN=${TUSHARE_SECRET}:latest" \
    --args="${args}"
}

deploy_job ashare-ingest-market-eod market_eod
deploy_job ashare-ingest-index-eod index_eod
deploy_job ashare-ingest-dim-snapshot dim_snapshot
deploy_job ashare-ingest-finance-recent finance_recent
deploy_job ashare-ingest-current-scope current_scope
