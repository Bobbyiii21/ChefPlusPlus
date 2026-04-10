#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Error: .env not found at ${ENV_FILE}" >&2
  exit 1
fi

# Load .env (skip blank lines and comments)
set -a
while IFS='=' read -r key value || [[ -n "$key" ]]; do
  [[ -z "$key" || "$key" =~ ^# ]] && continue
  export "${key}=${value}"
done < "${ENV_FILE}"
set +a

PROJECT="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT in .env}"
REGION="${VERTEX_AI_LOCATION:-us-central1}"
REPO="chefplusplus"
IMAGE="chefplusplus"
SERVICE="chefplusplus"
TAG="${1:-latest}"

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${IMAGE}:${TAG}"

# ── 1. Auth ──────────────────────────────────────────────────────
echo "==> Authenticating Docker with Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ── 2. Build & Push ──────────────────────────────────────────────
echo "==> Building image (linux/amd64) and pushing..."
docker buildx build \
  --platform=linux/amd64 \
  -t "${REGISTRY}" \
  --push \
  .

# ── 3. Deploy to Cloud Run ───────────────────────────────────────
echo "==> Deploying to Cloud Run..."

ENV_VARS="DJANGO_DEBUG=false"
ENV_VARS+=",DJANGO_ALLOWED_HOSTS=.run.app"
ENV_VARS+=",DJANGO_CSRF_TRUSTED_ORIGINS=https://*.run.app"
ENV_VARS+=",DJANGO_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"

# Map superuser credentials to the names the management command expects
ENV_VARS+=",DJANGO_SUPERUSER_EMAIL=${SUPERUSER_EMAIL:-}"
ENV_VARS+=",DJANGO_SUPERUSER_PASSWORD=${SUPERUSER_PASSWORD:-}"

# Forward every key from .env (except secrets/comments/superuser keys already mapped)
while IFS='=' read -r key value || [[ -n "$key" ]]; do
  [[ -z "$key" || "$key" =~ ^# || "$key" == "key" ]] && continue
  [[ "$key" == "SUPERUSER_EMAIL" || "$key" == "SUPERUSER_PASSWORD" ]] && continue
  ENV_VARS+=",${key}=${value}"
done < "${ENV_FILE}"

gcloud run deploy "${SERVICE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --image="${REGISTRY}" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8000 \
  --cpu=1 \
  --memory=512Mi \
  --min-instances=0 \
  --max-instances=2 \
  --cpu-boost \
  --set-env-vars="${ENV_VARS}" \
  --quiet

# ── 4. Print the public URL ──────────────────────────────────────
URL=$(gcloud run services describe "${SERVICE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --format="value(status.url)")

echo ""
echo "==> Deployed! Public URL: ${URL}"
