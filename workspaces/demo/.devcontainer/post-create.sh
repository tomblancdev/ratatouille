#!/bin/bash
# 🐀 Ratatouille Workspace Setup
# Connects to existing infrastructure started via `make up`

set -e

echo "🐀 Setting up Ratatouille workspace..."
echo ""

# Check if services are running
echo "🔍 Checking services..."

check_service() {
    local name=$1
    local url=$2
    if curl -sf "$url" > /dev/null 2>&1; then
        echo "   ✅ $name is running"
        return 0
    else
        echo "   ❌ $name is NOT running at $url"
        return 1
    fi
}

SERVICES_OK=true
check_service "MinIO" "${MINIO_ENDPOINT}/minio/health/live" || SERVICES_OK=false
check_service "Nessie" "${NESSIE_URI}/config" || SERVICES_OK=false

if [ "$SERVICES_OK" = false ]; then
    echo ""
    echo "⚠️  Some services are not running!"
    echo ""
    echo "Please start the Ratatouille infrastructure first:"
    echo "  cd /path/to/ratatouille"
    echo "  make up"
    echo ""
    echo "Then rebuild this devcontainer."
    echo ""
fi

# Install ratatouille
echo ""
echo "📦 Installing ratatouille..."

if pip install "ratatouille @ git+https://github.com/ratatouille-data/ratatouille.git" 2>/dev/null; then
    echo "   ✅ Installed from git"
else
    echo "   ⚠️  Git install failed, trying local..."
    # Try to find local ratatouille repo
    if [ -d "/ratatouille/src/ratatouille" ]; then
        pip install -e "/ratatouille[dev]"
        echo "   ✅ Installed from local mount"
    else
        echo "   ⚠️  Could not install ratatouille"
        echo "   Install manually: pip install git+https://github.com/ratatouille-data/ratatouille.git"
    fi
fi

# Create workspace bucket if services are running
if [ "$SERVICES_OK" = true ]; then
    echo ""
    echo "🪣 Setting up workspace bucket..."
    python << 'EOF'
import os
import boto3
from botocore.client import Config

try:
    s3 = boto3.client("s3",
        endpoint_url=os.environ.get("MINIO_ENDPOINT"),
        aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY"),
        config=Config(signature_version="s3v4"))

    workspace = os.environ.get("RATATOUILLE_WORKSPACE", "demo")
    bucket = f"ratatouille-{workspace}"

    try:
        s3.head_bucket(Bucket=bucket)
        print(f"   ✅ Bucket '{bucket}' exists")
    except:
        s3.create_bucket(Bucket=bucket)
        print(f"   ✅ Created bucket '{bucket}'")
except Exception as e:
    print(f"   ⚠️  Bucket setup: {e}")
EOF
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐀 Workspace ready!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Quick start:"
echo "  from ratatouille import tools"
echo ""
echo "  tools.info()          # Workspace info"
echo "  tools.connections()   # Check services"
echo "  tools.tables()        # List tables"
echo "  tools.ls('bronze/')   # Browse S3"
echo ""
