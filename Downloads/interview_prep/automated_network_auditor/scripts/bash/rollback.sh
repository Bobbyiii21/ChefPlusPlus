#!/usr/bin/env bash
# =============================================================================
# rollback.sh — Restore previous device configuration from backup
# =============================================================================
# Usage:
#   ./scripts/bash/rollback.sh -h <host> -u <user> -b <backup_file> [-p <port>] [-k <key>]
#
# Workflow:
#   1. Verify backup file exists and is non-empty
#   2. SSH to device and validate it is reachable
#   3. Upload backup config via SCP
#   4. Apply config (Linux: bash; Cisco: copy command)
#   5. Verify service is still reachable post-rollback
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }

HOST=""; USER=""; BACKUP_FILE=""; PORT=22; KEY_FILE=""; DEVICE_TYPE="linux"

while getopts "h:u:b:p:k:t:" opt; do
    case "$opt" in
        h) HOST="$OPTARG"        ;;
        u) USER="$OPTARG"        ;;
        b) BACKUP_FILE="$OPTARG" ;;
        p) PORT="$OPTARG"        ;;
        k) KEY_FILE="$OPTARG"    ;;
        t) DEVICE_TYPE="$OPTARG" ;;
        *) die "Usage: $0 -h host -u user -b backup_file [-p port] [-k key] [-t type]" ;;
    esac
done

[[ -z "$HOST"        ]] && die "-h host is required."
[[ -z "$USER"        ]] && die "-u user is required."
[[ -z "$BACKUP_FILE" ]] && die "-b backup_file is required."
[[ -f "$BACKUP_FILE" ]] || die "Backup file not found: $BACKUP_FILE"
[[ -s "$BACKUP_FILE" ]] || die "Backup file is empty: $BACKUP_FILE"

SSH_OPTS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes"
[[ -n "$KEY_FILE" ]] && SSH_OPTS="$SSH_OPTS -i $KEY_FILE"

# ── Step 1: connectivity check ─────────────────────────────────────────────
info "Verifying connectivity to ${HOST}:${PORT} …"
ssh $SSH_OPTS -p "$PORT" "${USER}@${HOST}" "echo connected" &>/dev/null || \
    die "Cannot reach ${HOST}:${PORT}"
success "Host is reachable."

# ── Step 2: snapshot current config before rollback ─────────────────────────
SNAPSHOT="/tmp/pre_rollback_snapshot_$(date +%s).cfg"
info "Snapshotting current config → $SNAPSHOT …"
if [[ "$DEVICE_TYPE" == "linux" ]]; then
    ssh $SSH_OPTS -p "$PORT" "${USER}@${HOST}" \
        "cat /etc/ssh/sshd_config /etc/issue.net /etc/chrony.conf 2>/dev/null || true" \
        > "$SNAPSHOT"
else
    warn "Cisco snapshot: upload only — interactive session required for show run."
fi
info "Snapshot saved: $SNAPSHOT"

# ── Step 3: upload backup ─────────────────────────────────────────────────────
info "Uploading backup to ${HOST}:/tmp/rollback.cfg …"
scp $SSH_OPTS -P "$PORT" "$BACKUP_FILE" "${USER}@${HOST}:/tmp/rollback.cfg" || \
    die "SCP upload failed."
success "Backup uploaded."

# ── Step 4: apply ─────────────────────────────────────────────────────────────
info "Applying rollback config on ${HOST} …"
if [[ "$DEVICE_TYPE" == "linux" ]]; then
    ssh $SSH_OPTS -p "$PORT" "${USER}@${HOST}" \
        "bash /tmp/rollback.cfg && rm /tmp/rollback.cfg" || \
        die "Remote rollback execution failed."
else
    warn "Cisco: config at /tmp/rollback.cfg — apply manually via: copy /tmp/rollback.cfg running-config"
fi

# ── Step 5: post-rollback verification ────────────────────────────────────────
info "Verifying host is still reachable post-rollback …"
sleep 3
ssh $SSH_OPTS -p "$PORT" "${USER}@${HOST}" "echo ok" &>/dev/null || \
    die "HOST IS UNREACHABLE AFTER ROLLBACK. Restore snapshot: $SNAPSHOT"

success "Rollback complete — ${HOST} is healthy."
