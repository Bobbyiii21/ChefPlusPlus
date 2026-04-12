#!/usr/bin/env bash
# =============================================================================
# bulk_deploy.sh — Deploy automation scripts to multiple Unix hosts in parallel
# =============================================================================
# Usage:
#   ./scripts/bash/bulk_deploy.sh -i <inventory_csv> [-w <workers>] [-d]
#
# Inventory CSV format (no header):
#   hostname,username,port,device_type[,ssh_key]
#
# Example:
#   10.0.1.10,sysadmin,22,linux,/home/ops/.ssh/id_rsa
#   10.0.1.11,sysadmin,22,linux
#
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }

# ── Defaults ─────────────────────────────────────────────────────────────────
INVENTORY_CSV=""
MAX_WORKERS=5
DRY_RUN=false

while getopts "i:w:d" opt; do
    case "$opt" in
        i) INVENTORY_CSV="$OPTARG" ;;
        w) MAX_WORKERS="$OPTARG"   ;;
        d) DRY_RUN=true            ;;
        *) die "Usage: $0 -i <inventory_csv> [-w workers] [-d]" ;;
    esac
done

[[ -z "$INVENTORY_CSV" ]] && die "Inventory CSV (-i) is required."
[[ -f "$INVENTORY_CSV" ]] || die "Inventory file not found: $INVENTORY_CSV"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMISSION="$SCRIPT_DIR/commission_device.sh"
[[ -x "$COMMISSION" ]] || die "commission_device.sh not executable at $COMMISSION"

LOG_DIR="/tmp/bulk_deploy_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

# ── Worker function ───────────────────────────────────────────────────────────
deploy_host() {
    local line="$1"
    # Parse CSV fields
    IFS=',' read -r HOST USER PORT DEVICE_TYPE KEY_FILE <<< "$line"
    KEY_FILE="${KEY_FILE:-}"

    local log_file="$LOG_DIR/${HOST}.log"
    local args=(-h "$HOST" -u "${USER:-sysadmin}" -t "${DEVICE_TYPE:-linux}" -p "${PORT:-22}")
    [[ -n "$KEY_FILE" ]] && args+=(-k "$KEY_FILE")
    [[ "$DRY_RUN" == true ]] && args+=(-d)

    info "Deploying → $HOST (${DEVICE_TYPE}) …"
    if bash "$COMMISSION" "${args[@]}" > "$log_file" 2>&1; then
        success "$HOST — completed."
    else
        error "$HOST — FAILED. See $log_file"
        return 1
    fi
}

export -f deploy_host
export LOG_DIR DRY_RUN COMMISSION

# ── Dispatch ─────────────────────────────────────────────────────────────────
info "Bulk deploy starting — workers=$MAX_WORKERS, dry_run=$DRY_RUN"
info "Log directory: $LOG_DIR"

TOTAL=0; PASSED=0; FAILED=0
declare -a PIDS=()
declare -A PID_HOST

while IFS= read -r line || [[ -n "$line" ]]; do
    # Skip blank lines and comments
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    HOST=$(echo "$line" | cut -d',' -f1)

    deploy_host "$line" &
    pid=$!
    PIDS+=("$pid")
    PID_HOST["$pid"]="$HOST"
    TOTAL=$((TOTAL + 1))

    # Throttle to MAX_WORKERS parallel jobs
    while [[ $(jobs -rp | wc -l) -ge $MAX_WORKERS ]]; do
        sleep 0.5
    done
done < "$INVENTORY_CSV"

# ── Collect results ───────────────────────────────────────────────────────────
for pid in "${PIDS[@]}"; do
    host="${PID_HOST[$pid]}"
    if wait "$pid"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
        warn "$host failed — check $LOG_DIR/${host}.log"
    fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo "  Bulk Deploy Summary"
echo "────────────────────────────────────────"
printf "  Total:  %d\n" "$TOTAL"
printf "  Passed: %d\n" "$PASSED"
printf "  Failed: %d\n" "$FAILED"
echo "  Logs:   $LOG_DIR"
echo "════════════════════════════════════════"

[[ $FAILED -gt 0 ]] && exit 1 || exit 0
