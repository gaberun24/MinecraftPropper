#!/bin/bash
# Usage: restore_backup.sh <backup_file>
set -euo pipefail

MINECRAFT_DIR="${MCM_MINECRAFT_DIR:-/opt/minecraft}"
BACKUP_FILE="${1:?Usage: restore_backup.sh <backup_file>}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

# Stop server if running
WAS_RUNNING=false
if systemctl is-active --quiet minecraft 2>/dev/null; then
    WAS_RUNNING=true
    systemctl stop minecraft
    sleep 5
fi

# Restore
tar -xzf "$BACKUP_FILE" -C "$MINECRAFT_DIR"
chown -R minecraft:minecraft "$MINECRAFT_DIR"

# Restart if it was running
if $WAS_RUNNING; then
    systemctl start minecraft
fi

echo "Restored from: $BACKUP_FILE"
