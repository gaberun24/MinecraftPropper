#!/bin/bash
# Usage: update_paper.sh <mc_version> <build_number> <jar_url> <sha256>
set -euo pipefail

MINECRAFT_DIR="${MCM_MINECRAFT_DIR:-/opt/minecraft}"
VERSIONS_DIR="${MCM_VERSIONS_DIR:-/opt/minecraft-versions}"
MC_VERSION="$1"
BUILD="$2"
JAR_URL="$3"
EXPECTED_SHA="$4"

JAR_NAME="paper-${MC_VERSION}-${BUILD}.jar"
JAR_PATH="$VERSIONS_DIR/$JAR_NAME"

mkdir -p "$VERSIONS_DIR"

# Download
echo "Downloading Paper $MC_VERSION build $BUILD..."
curl -fSL -o "$JAR_PATH" "$JAR_URL"

# Verify checksum
ACTUAL_SHA=$(sha256sum "$JAR_PATH" | cut -d' ' -f1)
if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
    rm -f "$JAR_PATH"
    echo "ERROR: SHA256 mismatch" >&2
    exit 1
fi

# Update symlink
ln -sf "$JAR_PATH" "$MINECRAFT_DIR/paper.jar"

echo "Paper updated to $MC_VERSION build $BUILD"
