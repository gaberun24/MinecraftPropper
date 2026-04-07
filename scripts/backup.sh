#!/bin/bash
# Usage: backup.sh <type> [world_name]
# Types: daily, monthly, update, world
set -euo pipefail

MINECRAFT_DIR="${MCM_MINECRAFT_DIR:-/opt/minecraft}"
BACKUP_DIR="${MCM_BACKUP_DIR:-/var/backups/minecraft}"
STDIN_PIPE="${MCM_STDIN_PIPE:-/run/minecraft.stdin}"
TYPE="${1:?Usage: backup.sh <type> [world_name]}"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)

case "$TYPE" in
    daily)   DEST_DIR="$BACKUP_DIR/daily" ;;
    monthly) DEST_DIR="$BACKUP_DIR/monthly" ;;
    update)  DEST_DIR="$BACKUP_DIR/update" ;;
    world)
        WORLD="${2:?World name required for world backup}"
        DEST_DIR="$BACKUP_DIR/worlds/$WORLD/snapshots"
        ;;
    *)       echo "Unknown type: $TYPE" >&2; exit 1 ;;
esac

mkdir -p "$DEST_DIR"
BACKUP_FILE="$DEST_DIR/${TYPE}_${TIMESTAMP}.tar.gz"

# Check if server is running
SERVER_RUNNING=false
if systemctl is-active --quiet minecraft 2>/dev/null; then
    SERVER_RUNNING=true
fi

# Safe save flow
if $SERVER_RUNNING; then
    echo "save-off" > "$STDIN_PIPE"
    echo "save-all flush" > "$STDIN_PIPE"

    LOG="$MINECRAFT_DIR/logs/latest.log"
    LINES_BEFORE=$(wc -l < "$LOG" 2>/dev/null || echo 0)

    for i in $(seq 1 30); do
        if tail -n +"$LINES_BEFORE" "$LOG" 2>/dev/null | grep -q "Saved the game"; then
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "save-on" > "$STDIN_PIPE"
            echo "ERROR: Timed out waiting for save" >&2
            exit 2
        fi
        sleep 1
    done
fi

# Create backup
if [ "$TYPE" = "world" ]; then
    cd "$MINECRAFT_DIR"
    DIRS="$WORLD/"
    [ -d "${WORLD}_nether" ] && DIRS="$DIRS ${WORLD}_nether/"
    [ -d "${WORLD}_the_end" ] && DIRS="$DIRS ${WORLD}_the_end/"
    tar -czf "$BACKUP_FILE" $DIRS
else
    tar -czf "$BACKUP_FILE" -C "$MINECRAFT_DIR" \
        --exclude='logs' --exclude='cache' --exclude='*.log' .
fi

# Re-enable saving
if $SERVER_RUNNING; then
    echo "save-on" > "$STDIN_PIPE"
fi

echo "$BACKUP_FILE"
