#!/usr/bin/env bash
# Deploy Pincite to Google Cloud Run.
#
#   gcloud auth login && gcloud config set project YOUR_PROJECT_ID
#   ./deploy/cloudrun.sh
#
# Secrets go to Secret Manager, never into the image or the command line history.
set -euo pipefail

PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-east1}"
SERVICE="${SERVICE:-pincite}"
[[ -n "$PROJECT" ]] || { echo "Set a project: gcloud config set project YOUR_PROJECT_ID"; exit 1; }

echo "Deploying $SERVICE to $PROJECT ($REGION)"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com --project "$PROJECT"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Newer projects build source deploys as the default compute account, which needs this role.
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member "serviceAccount:${RUNTIME_SA}" --role roles/run.builder --condition None >/dev/null \
  || echo "Couldn't grant roles/run.builder (you may need Owner on the project). Continuing."

ensure_secret() {
  local name="$1" prompt="$2" value
  if gcloud secrets describe "$name" --project "$PROJECT" >/dev/null 2>&1; then
    echo "Secret $name already exists; keeping it."
  else
    read -rsp "$prompt: " value; echo
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --project "$PROJECT"
  fi
  gcloud secrets add-iam-policy-binding "$name" --project "$PROJECT" \
    --member "serviceAccount:${RUNTIME_SA}" --role roles/secretmanager.secretAccessor >/dev/null
}

ensure_secret pincite-openai-key "OpenAI API key"
ensure_secret pincite-access-code "Access code people will type to open the workspace"

# max-instances=1: case data lives in one SQLite file per instance (see docs/decisions/0004).
gcloud run deploy "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --source . \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 1 \
  --timeout 300 \
  --set-secrets "OPENAI_API_KEY=pincite-openai-key:latest,ACCESS_CODE=pincite-access-code:latest"

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')"
echo
echo "Pincite is live at $URL"
curl -fsS "$URL/api/health" && echo
