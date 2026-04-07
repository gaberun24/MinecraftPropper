#!/bin/bash
# Usage: world_switch.sh <new_world_name>
set -euo pipefail

MINECRAFT_DIR="${MCM_MINECRAFT_DIR:-/opt/minecraft}"
NEW_WORLD="${1:?Usage: world_switch.sh <new_world_name>}"
PROPERTIES="$MINECRAFT_DIR/server.properties"

CURRENT_WORLD=$(grep '^level-name=' "$PROPERTIES" | cut -d= -f2)

if [ "$CURRENT_WORLD" = "$NEW_WORLD" ]; then
    echo "World '$NEW_WORLD' is already active"
    exit 0
fi

if [ ! -d "$MINECRAFT_DIR/$NEW_WORLD" ]; then
    echo "ERROR: World directory '$NEW_WORLD' not found" >&2
    exit 1
fi

# Stop server if running
WAS_RUNNING=false
if systemctl is-active --quiet minecraft 2>/dev/null; then
    WAS_RUNNING=true
    systemctl stop minecraft
    sleep 5
fi

# Update server.properties
sed -i "s/^level-name=.*/level-name=$NEW_WORLD/" "$PROPERTIES"

# Start server if it was running
if $WAS_RUNNING; then
    systemctl start minecraft
fi

echo "Switched to world: $NEW_WORLD"
