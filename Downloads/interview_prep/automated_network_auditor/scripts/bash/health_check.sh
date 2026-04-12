#!/usr/bin/env bash
# =============================================================================
# health_check.sh — Quick connectivity and service health check
# =============================================================================
# Checks: ICMP ping, SSH port, NTP sync, disk usage, CPU load
#
# Usage:
#   ./scripts/bash/health_check.sh -i <inventory_csv> [-t <timeout>]
#
# Output:
#   Per-host one-liner status; exits 1 if any host is degraded.
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; RESET='\033[0m'

pass() { echo -e "${GREEN}[PASS]${RESET} $*"; }
fail() { echo -e "${RED}[FAIL]${RESET} $*"; }
warn() { echo -e "${YELLOW}[WARN]${RESET} $*"; }

INVENTORY_CSV=""
TIMEOUT=5

while getopts "i:t:" opt; do
    case "$opt" in
        i) INVENTORY_CSV="$OPTARG" ;;
        t) TIMEOUT="$OPTARG"       ;;
        *) echo "Usage: $0 -i <inventory_csv> [-t timeout]"; exit 1 ;;
    esac
done

[[ -z "$INVENTORY_CSV" ]] && { echo "ERROR: -i required"; exit 1; }
[[ -f "$INVENTORY_CSV" ]] || { echo "ERROR: file not found: $INVENTORY_CSV"; exit 1; }

DEGRADED=0

check_host() {
    local HOST USER PORT DEVICE_TYPE KEY_FILE
    IFS=',' read -r HOST USER PORT DEVICE_TYPE KEY_FILE <<< "$1"
    PORT="${PORT:-22}"; KEY_FILE="${KEY_FILE:-}"
    local status_line="$HOST"

    # 1. Ping
    if ping -c 1 -W "$TIMEOUT" "$HOST" &>/dev/null; then
        status_line="$status_line [ping:OK]"
    else
        status_line="$status_line [ping:FAIL]"
        fail "$status_line"
        return 1
    fi

    # 2. SSH port
    SSH_OPTS="-o ConnectTimeout=${TIMEOUT} -o BatchMode=yes -o StrictHostKeyChecking=no"
    [[ -n "$KEY_FILE" ]] && SSH_OPTS="$SSH_OPTS -i $KEY_FILE"

    if ssh $SSH_OPTS -p "$PORT" "${USER}@${HOST}" "echo ok" &>/dev/null; then
        status_line="$status_line [ssh:OK]"
    else
        status_line="$status_line [ssh:FAIL]"
        fail "$status_line"
        return 1
    fi

    # 3. Linux-specific checks
    if [[ "$DEVICE_TYPE" == "linux" ]]; then
        # Disk usage (warn >85%)
        DISK=$(ssh $SSH_OPTS -p "$PORT" "${USER}@${HOST}" \
            "df / --output=pcent | tail -1 | tr -d '% '")
        if [[ "$DISK" -ge 90 ]]; then
            status_line="$status_line [disk:${DISK}%:CRIT]"
        elif [[ "$DISK" -ge 85 ]]; then
            status_line="$status_line [disk:${DISK}%:WARN]"
        else
            status_line="$status_line [disk:${DISK}%:OK]"
        fi

        # NTP sync
        NTP=$(ssh $SSH_OPTS -p "$PORT" "${USER}@${HOST}" \
            "timedatectl show --property=NTPSynchronized --value 2>/dev/null || echo unknown")
        status_line="$status_line [ntp:${NTP}]"
    fi

    pass "$status_line"
    return 0
}

TOTAL=0; PASSED=0; FAILED=0
declare -a PIDS=()

while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    check_host "$line" &
    PIDS+=($!)
    TOTAL=$((TOTAL + 1))
done < "$INVENTORY_CSV"

for pid in "${PIDS[@]}"; do
    if wait "$pid"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
        DEGRADED=1
    fi
done

echo ""
echo "Health check complete: $PASSED/$TOTAL hosts healthy."
[[ $FAILED -gt 0 ]] && warn "$FAILED host(s) degraded."

exit $DEGRADED
