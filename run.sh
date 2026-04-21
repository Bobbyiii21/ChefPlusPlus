#!/usr/bin/env bash
# Build and run ChefPlusPlus in Docker.
# Vertex features (e.g. Generate description) need GCP env vars inside the container.
# Put GOOGLE_CLOUD_PROJECT (and related keys from .env.example) in repo-root .env, or pass -e manually.
# Vertex needs credentials inside the container. This script mounts your host
# Application Default Credentials if you ran: gcloud auth application-default login
# (file: ~/.config/gcloud/application_default_credentials.json).
# Alternatively mount a service account JSON and set GOOGLE_APPLICATION_CREDENTIALS yourself.
set -euo pipefail
cd "$(dirname "$0")"

docker build --no-cache -t chefplusplus .

ENV_ARGS=()
if [[ -f .env ]]; then
  ENV_ARGS+=(--env-file .env)
fi

# Host ADC from `gcloud auth application-default login` — not visible in Docker unless mounted.
ADC_HOST="${HOME}/.config/gcloud/application_default_credentials.json"
CRED_ARGS=()
if [[ -f "${ADC_HOST}" ]]; then
  CRED_ARGS+=(
    -v "${ADC_HOST}:/run/gcp/application_default_credentials.json:ro"
    -e GOOGLE_APPLICATION_CREDENTIALS=/run/gcp/application_default_credentials.json
  )
else
  echo "Note: No host ADC at ${ADC_HOST} — Vertex calls may fail until you run:" >&2
  echo "  gcloud auth application-default login" >&2
  echo "  or mount a service account key (see comments in run.sh)." >&2
fi

docker run --rm -p 8000:8000 \
  "${ENV_ARGS[@]}" \
  "${CRED_ARGS[@]}" \
  -e DJANGO_SUPERUSER_EMAIL='admin@hyperlapse.one' \
  -e DJANGO_SUPERUSER_PASSWORD='BigChef' \
  chefplusplus
