#!/bin/bash
set -e

echo "🚀 Starting DevOps Agent API..."
echo "Mode: $EXAMPLES_MODE"

if [ "$EXAMPLES_MODE" == "workspace" ]; then
    echo "📂 Workspace Mode: Installing Contracts and SDK..."

    # 1. Install Contracts (Dependency for SDK)
    if [ -d "/mnt/workspace/talos-contracts-py" ]; then
        echo "    Installing local talos-contracts-py..."
        cp -r /mnt/workspace/talos-contracts-py /tmp/talos-contracts-py
        pip install --no-build-isolation /tmp/talos-contracts-py
    fi

    # 2. Install SDK
    if [ ! -d "/mnt/workspace/talos-sdk-py" ]; then
        echo "❌ SDK not found at /mnt/workspace/talos-sdk-py"
        exit 1
    fi
    # Copy to tmp to allow building wheel (requires write access for egg-info)
    # This respects Read-Only mount but sacrifices live-reloading (requires restart)
    echo "    Copying SDK to writable /tmp/talos-sdk-py..."
    cp -r /mnt/workspace/talos-sdk-py /tmp/talos-sdk-py
    pip install --no-build-isolation /tmp/talos-sdk-py
else
    echo "📦 Released Mode: Installing SDK from PyPI..."
    # Attempt install, fail if not found (expected until published)
    pip install talos-sdk-py>=0.1.0 || {
        echo "⚠️  Warning: Failed to install talos-sdk-py from PyPI."
        echo "    (This is expected if the package is not yet published)"
        echo "    Continuing without it may cause runtime errors."
    }
fi

# Run Application
exec python src/main.py
