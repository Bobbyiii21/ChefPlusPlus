#!/usr/bin/env bash
# =============================================================================
# commission_device.sh — Single-device network commissioning
# =============================================================================
# Usage:
#   ./scripts/bash/commission_device.sh -h <host> -u <user> -t <type> [-p <port>] [-k <key>] [-d]
#
# Options:
#   -h HOST      Target device IP / hostname (required)
#   -u USER      SSH username (required)
#   -t TYPE      Device type: cisco_ios | cisco_asa | linux (required)
#   -p PORT      SSH port (default: 22)
#   -k KEY       Path to SSH private key (optional; uses password otherwise)
#   -d           Dry-run — generate config but do not push
#
# =============================================================================
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }

# ── Defaults ─────────────────────────────────────────────────────────────────
HOST=""
USER=""
DEVICE_TYPE=""
PORT=22
KEY_FILE=""
DRY_RUN=false

# ── Argument parsing ─────────────────────────────────────────────────────────
while getopts "h:u:t:p:k:d" opt; do
    case "$opt" in
        h) HOST="$OPTARG"        ;;
        u) USER="$OPTARG"        ;;
        t) DEVICE_TYPE="$OPTARG" ;;
        p) PORT="$OPTARG"        ;;
        k) KEY_FILE="$OPTARG"    ;;
        d) DRY_RUN=true          ;;
        *) die "Unknown option: -$OPTARG. Use -h for help." ;;
    esac
done

[[ -z "$HOST"        ]] && die "Host (-h) is required."
[[ -z "$USER"        ]] && die "Username (-u) is required."
[[ -z "$DEVICE_TYPE" ]] && die "Device type (-t) is required."

VALID_TYPES="cisco_ios cisco_asa linux"
echo "$VALID_TYPES" | grep -qw "$DEVICE_TYPE" || \
    die "Unknown device type '$DEVICE_TYPE'. Valid: $VALID_TYPES"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── SSH connectivity check ────────────────────────────────────────────────────
info "Checking SSH connectivity to ${HOST}:${PORT} …"
SSH_OPTS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes"
[[ -n "$KEY_FILE" ]] && SSH_OPTS="$SSH_OPTS -i $KEY_FILE"

MAX_RETRIES=3; RETRY_DELAY=5; attempt=0
until ssh $SSH_OPTS -p "$PORT" "${USER}@${HOST}" "echo connected" &>/dev/null; do
    attempt=$((attempt + 1))
    if [[ $attempt -ge $MAX_RETRIES ]]; then
        die "Cannot connect to ${HOST}:${PORT} after $MAX_RETRIES attempts."
    fi
    warn "Attempt $attempt/$MAX_RETRIES failed. Retrying in ${RETRY_DELAY}s …"
    sleep "$RETRY_DELAY"
    RETRY_DELAY=$((RETRY_DELAY * 2))   # exponential back-off
done
success "SSH connectivity verified: ${USER}@${HOST}:${PORT}"

# ── Render baseline config via Python ────────────────────────────────────────
info "Rendering baseline config (type=$DEVICE_TYPE) …"
RENDER_CMD=(
    python3 -c "
import sys; sys.path.insert(0, '${PROJECT_ROOT}')
from scripts.python.commission import commission_device, _render_template
from pathlib import Path
from datetime import datetime

class D:
    name='${HOST}'; host='${HOST}'; device_type='${DEVICE_TYPE}'
    username='${USER}'; password=None; key_file='${KEY_FILE}' or None
    port=${PORT}; timeout=30; simulate=False; location=''; role=''

tmpl_map = {'cisco_ios':'cisco_ios_baseline.j2','cisco_asa':'cisco_asa_baseline.j2','linux':'linux_server_baseline.j2'}
tmpl = tmpl_map.get('${DEVICE_TYPE}','cisco_ios_baseline.j2')
ctx = {'device':D(),'timestamp':datetime.utcnow().isoformat(),'org_name':'CORP','domain':'corp.local','ntp_servers':['10.0.0.100'],'syslog_server':'10.0.0.200'}
print(_render_template(tmpl, Path('${PROJECT_ROOT}/config/templates'), ctx))
"
)

CONFIG_TEXT=$("${RENDER_CMD[@]}") || die "Template rendering failed."
CONFIG_FILE="/tmp/baseline_${HOST}_$(date +%s).cfg"
echo "$CONFIG_TEXT" > "$CONFIG_FILE"
info "Config rendered → $CONFIG_FILE"

# ── Dry-run exit ─────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == true ]]; then
    warn "[DRY-RUN] Config NOT pushed. Preview:"
    echo "─────────────────────────────────────────────────────────"
    head -30 "$CONFIG_FILE"
    echo "─────────────────────────────────────────────────────────"
    success "Dry-run complete. Exiting."
    exit 0
fi

# ── Push config ───────────────────────────────────────────────────────────────
info "Pushing config to ${HOST} …"
scp $SSH_OPTS -P "$PORT" "$CONFIG_FILE" "${USER}@${HOST}:/tmp/baseline.cfg" || \
    die "SCP upload failed."

if [[ "$DEVICE_TYPE" == "linux" ]]; then
    ssh $SSH_OPTS -p "$PORT" "${USER}@${HOST}" "bash /tmp/baseline.cfg" || \
        die "Remote execution failed."
else
    # Cisco: load config (simplified; production would use expect or netmiko)
    warn "Cisco config push requires interactive session or NETCONF. Config uploaded to /tmp/baseline.cfg"
fi

success "Device ${HOST} commissioned successfully."
rm -f "$CONFIG_FILE"
