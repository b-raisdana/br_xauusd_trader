#!/usr/bin/env bash
set -euo pipefail
umask 077

export RESTIC_REPOSITORY="/mnt/d/backups/restic/xaausd-paction-data"
export RESTIC_PASSWORD_FILE="/home/brais/.config/restic/dlf-data.pass"

LOG_DIR="/mnt/c/Code/XAAUSD-PAction-projectFolder/logs/restic"
mkdir -p "$LOG_DIR"
exec >>"$LOG_DIR/forget.log" 2>&1

echo "=== $(date -Is) forget+prune start ==="
restic forget --tag xaausd-paction-data --keep-within 14d --prune
restic check --read-data-subset=5%
echo "=== $(date -Is) forget+prune done ==="
