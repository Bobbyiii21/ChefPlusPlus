#!/usr/bin/env bash
# Export variables from `.env` for this process (and the dev server), then start Django.
# Your interactive shell is unchanged after exit; run `set -a && source .env && set +a` yourself
# if you need the same vars in the parent terminal.
#
# Usage:
#   ./run.sh
#   ./run.sh 0.0.0.0:8000
#
# Requires Python deps in PATH (activate a venv first, or rely on app/.venv below).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$REPO_ROOT/app"

if [[ ! -f "$APP_DIR/manage.py" ]]; then
  echo "run.sh: expected $APP_DIR/manage.py" >&2
  exit 1
fi

# Optional: use the venv the README creates under app/
if [[ -f "$APP_DIR/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$APP_DIR/.venv/bin/activate"
fi

# Export variables from .env (same files as Django's dotenv loader: root then app/).
set -a
if [[ -f "$REPO_ROOT/.env" ]]; then
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.env"
fi
if [[ -f "$APP_DIR/.env" ]]; then
  # shellcheck source=/dev/null
  source "$APP_DIR/.env"
fi
set +a

cd "$APP_DIR"
exec python manage.py runserver "$@"
