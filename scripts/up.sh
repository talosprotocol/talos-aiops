#!/bin/bash
set -e

# Talos DevOps Agent Start Script
# Usage: ./scripts/up.sh [released|workspace]

MODE=${1:-released}
export EXAMPLES_MODE=$MODE

echo "🚀 Starting DevOps Agent in [$MODE] mode..."

# 1. Validation for Workspace Mode
if [ "$MODE" == "workspace" ]; then
    SDK_PATH="../talos-sdk-py"
    if [ ! -d "$SDK_PATH" ]; then
        echo "❌ Error: SDK path $SDK_PATH not found for workspace mode."
        exit 1
    fi
    # Resolve absolute path for Docker mount
    export TALOS_SDK_PATH=$(cd "$SDK_PATH" && pwd)
    echo "📂 Mounting SDK from: $TALOS_SDK_PATH"
fi

# 2. Network Cleanup
docker network rm agent-net cloud-net control-plane 2>/dev/null || true

# 3. Docker Compose Up
# Use the correct profile
docker compose --profile $MODE up -d --build --remove-orphans

# 4. Health Wait
echo "⏳ Waiting for API health..."
MAX_RETRIES=30
COUNT=0
URL="http://localhost:8200/health"

while [ $COUNT -lt $MAX_RETRIES ]; do
    if curl -s $URL > /dev/null; then
        echo "✅ DevOps Agent Operational at $URL"
        exit 0
    fi
    sleep 1
    COUNT=$((COUNT+1))
done

echo "❌ Timeout waiting for healthy signal"
exit 1
