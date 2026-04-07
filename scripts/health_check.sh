#!/bin/bash
# Usage: health_check.sh [timeout_seconds] [port]
set -euo pipefail

TIMEOUT="${1:-90}"
PORT="${2:-25565}"

for i in $(seq 1 "$TIMEOUT"); do
    if nc -z localhost "$PORT" 2>/dev/null; then
        echo "OK: Server responding on port $PORT after ${i}s"
        exit 0
    fi
    sleep 1
done

echo "FAIL: Server not responding on port $PORT after ${TIMEOUT}s" >&2
exit 1
