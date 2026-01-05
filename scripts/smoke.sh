#!/bin/bash
set -e

# Talos DevOps Agent Smoke Test
# Usage: ./scripts/smoke.sh

echo "🧪 Running Smoke Tests..."

# 1. API Health
HEALTH=$(curl -s http://localhost:8200/health)
if [[ $HEALTH == *"talos-aiops"* ]]; then
    echo "✅ /health: OK ($HEALTH)"
else
    echo "❌ /health: FAIL"
    exit 1
fi

# 2. Network Isolation Verification
# Agent Container (on agent-net) should NOT reach Cloud net directly
echo "🔒 Verifying Network Isolation..."
ISOLATION_TEST=$(docker exec talos-aiops-api curl -s -o /dev/null -w "%{http_code}" http://talos-aiops-cloud:4566 --connect-timeout 2 || echo "BLOCKED")

if [ "$ISOLATION_TEST" == "BLOCKED" ] || [ "$ISOLATION_TEST" == "000" ]; then
    echo "✅ Isolation Confirmed: Agent cannot reach Cloud (Result: $ISOLATION_TEST)"
else
    echo "❌ Security FAIL: Agent reached Cloud directly (Code: $ISOLATION_TEST)"
    exit 1
fi

echo "✨ All Systems Go"
exit 0
