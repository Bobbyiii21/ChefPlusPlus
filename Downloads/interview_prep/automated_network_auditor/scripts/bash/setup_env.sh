#!/usr/bin/env bash
# =============================================================================
# setup_env.sh — Bootstrap dev/CI environment
# =============================================================================
# Creates a virtualenv, installs deps, and validates tool availability.
# Safe to run multiple times (idempotent).
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RESET='\033[0m'
info()    { echo -e "${CYAN}[setup]${RESET} $*"; }
success() { echo -e "${GREEN}[done]${RESET}  $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"

# ── Python version check ──────────────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python || die "Python 3 not found.")
PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Using Python $PY_VER at $PYTHON"

# ── Virtual environment ───────────────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating virtual environment at $VENV_DIR …"
    "$PYTHON" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
info "Virtual environment active."

# ── Install dependencies ──────────────────────────────────────────────────────
info "Installing dependencies …"
pip install --quiet --upgrade pip
pip install --quiet -r "$PROJECT_ROOT/requirements.txt"
success "Dependencies installed."

# ── Verify key tools ─────────────────────────────────────────────────────────
for tool in python pytest black flake8 mypy; do
    if command -v "$tool" &>/dev/null; then
        info "$tool: $(${tool} --version 2>&1 | head -1)"
    else
        echo "WARNING: $tool not found in PATH."
    fi
done

# ── Verify shellcheck (optional) ─────────────────────────────────────────────
if command -v shellcheck &>/dev/null; then
    info "shellcheck: $(shellcheck --version | head -2 | tail -1)"
else
    echo "NOTE: shellcheck not installed — Bash linting will be skipped in CI."
fi

success "Environment setup complete. Activate with: source $VENV_DIR/bin/activate"
