#!/usr/bin/env bash
set -euo pipefail
umask 077

export RESTIC_REPOSITORY="/mnt/d/backups/restic/xaausd-paction-data"
export RESTIC_PASSWORD_FILE="/home/brais/.config/restic/dlf-data.pass"

DATA_DIR="/mnt/c/Code/XAAUSD-PAction-projectFolder/data"
LOG_DIR="/mnt/c/Code/XAAUSD-PAction-projectFolder/logs/restic"
mkdir -p "$LOG_DIR"
exec >>"$LOG_DIR/backup.log" 2>&1

echo "=== $(date -Is) backup start ==="
restic backup "$DATA_DIR" \
  --host xaausd-paction-wsl \
  --tag xaausd-paction-data \
  --tag auto \
  --exclude-caches
echo "=== $(date -Is) backup done ==="
