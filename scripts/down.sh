#!/bin/bash

echo "🛑 Stopping DevOps Agent..."
docker compose --profile released --profile workspace down --volumes --remove-orphans
echo "✅ Stopped"
