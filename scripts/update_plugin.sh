#!/bin/bash
# Usage: update_plugin.sh <plugin_name> <jar_url> <sha256> <filename>
set -euo pipefail

MINECRAFT_DIR="${MCM_MINECRAFT_DIR:-/opt/minecraft}"
PLUGIN_NAME="$1"
JAR_URL="$2"
EXPECTED_SHA="$3"
FILENAME="$4"

PLUGIN_DIR="$MINECRAFT_DIR/plugins"
JAR_PATH="$PLUGIN_DIR/$FILENAME"

# Backup old jar
if [ -f "$JAR_PATH" ]; then
    mv "$JAR_PATH" "${JAR_PATH}.bak"
fi

# Download
echo "Downloading $PLUGIN_NAME..."
curl -fSL -o "$JAR_PATH" "$JAR_URL"

# Verify
ACTUAL_SHA=$(sha256sum "$JAR_PATH" | cut -d' ' -f1)
if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
    mv "${JAR_PATH}.bak" "$JAR_PATH" 2>/dev/null || true
    echo "ERROR: SHA256 mismatch for $PLUGIN_NAME" >&2
    exit 1
fi

rm -f "${JAR_PATH}.bak"
echo "$PLUGIN_NAME updated: $FILENAME"
