#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-data-aquarium}"
REGION="${REGION:-asia-east2}"
SERVICE_NAME="${SERVICE_NAME:-ashare-pipeline-control}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-ashare-workflows-runtime@${PROJECT_ID}.iam.gserviceaccount.com}"
LOCK_BUCKET="${LOCK_BUCKET:-ashare-artifacts}"
LOCK_PREFIX="${LOCK_PREFIX:-locks/pipeline/orchestration}"
IMAGE_URI="${IMAGE_URI:-${REGION}-docker.pkg.dev/${PROJECT_ID}/ashare/pipeline-control:latest}"

gcloud builds submit . \
  --project="${PROJECT_ID}" \
  --config=orchestration/workflows/cloudbuild.pipeline_control.yaml \
  --substitutions=_IMAGE_URI="${IMAGE_URI}"

gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --service-account="${SERVICE_ACCOUNT}" \
  --no-allow-unauthenticated \
  --cpu=1 \
  --memory=512Mi \
  --timeout=3600 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},REGION=${REGION},BQ_LOCATION=${REGION},LOCK_BUCKET=${LOCK_BUCKET},LOCK_PREFIX=${LOCK_PREFIX}"

gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(status.url)'

