#!/bin/bash
# 🐀 Ratatouille Workspace Setup

set -e

echo "🐀 Setting up Ratatouille workspace..."

# Try to install ratatouille
# Priority: 1) Local mount (for development), 2) Git repo, 3) PyPI (future)

if [ -d "/ratatouille/src/ratatouille" ]; then
    echo "📦 Installing ratatouille from local mount (development mode)..."
    pip install -e "/ratatouille[dev]"
elif pip install "ratatouille @ git+https://github.com/ratatouille-data/ratatouille.git" 2>/dev/null; then
    echo "📦 Installed ratatouille from git..."
else
    echo "⚠️  Could not install ratatouille from git. Using pre-installed dependencies."
    echo "    To develop locally, mount the ratatouille repo to /ratatouille"
fi

# Create MinIO bucket for this workspace
echo "🪣 Setting up MinIO bucket..."
python << 'EOF'
import os
import boto3
from botocore.client import Config

endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
access_key = os.environ.get("MINIO_ACCESS_KEY", "ratatouille")
secret_key = os.environ.get("MINIO_SECRET_KEY", "ratatouille123")
workspace = os.environ.get("RATATOUILLE_WORKSPACE", "demo")

try:
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )

    bucket = f"ratatouille-{workspace}"

    # Create bucket if not exists
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"✅ Bucket '{bucket}' exists")
    except:
        s3.create_bucket(Bucket=bucket)
        print(f"✅ Created bucket '{bucket}'")

except Exception as e:
    print(f"⚠️  Could not setup MinIO bucket: {e}")
    print("   MinIO may not be ready yet. Run this script again later.")
EOF

# Create Nessie branch for this workspace
echo "🌿 Setting up Nessie branch..."
python << 'EOF'
import os
import httpx

nessie_uri = os.environ.get("NESSIE_URI", "http://nessie:19120/api/v1")
workspace = os.environ.get("RATATOUILLE_WORKSPACE", "demo")
branch = f"workspace/{workspace}"

try:
    # Get default branch hash
    resp = httpx.get(f"{nessie_uri}/trees/main")
    if resp.status_code == 200:
        main_hash = resp.json().get("hash")

        # Create workspace branch
        resp = httpx.post(
            f"{nessie_uri}/trees",
            json={
                "name": branch,
                "type": "BRANCH",
                "hash": main_hash
            }
        )

        if resp.status_code == 200:
            print(f"✅ Created Nessie branch '{branch}'")
        elif resp.status_code == 409:
            print(f"✅ Nessie branch '{branch}' exists")
        else:
            print(f"⚠️  Could not create branch: {resp.text}")
    else:
        print(f"⚠️  Could not connect to Nessie: {resp.status_code}")

except Exception as e:
    print(f"⚠️  Could not setup Nessie branch: {e}")
    print("   Nessie may not be ready yet. Run this script again later.")
EOF

echo ""
echo "🐀 Workspace ready!"
echo ""
echo "📁 Your workspace: /workspace"
echo "🪣 MinIO bucket:   ratatouille-${RATATOUILLE_WORKSPACE}"
echo "🌿 Nessie branch:  workspace/${RATATOUILLE_WORKSPACE}"
echo ""
echo "Quick start:"
echo "  from ratatouille import sdk"
echo "  sdk.query('SELECT 1')"
echo ""
