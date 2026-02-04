"""
🐀 Ratatouille Workspace Templates

Scaffolds new workspaces with all necessary files.
"""

import os
from pathlib import Path
from typing import Any

# Template strings embedded for portability
# (no need to ship template files separately)

WORKSPACE_YAML = '''# 🐀 Ratatouille Workspace Configuration

name: {name}
version: "1.0"

description: |
  {name} workspace.

  Add your description here.

# Workspace isolation settings
isolation:
  nessie_branch: "workspace/{name}"
  s3_prefix: "{name}"

# Default resource profile for pipelines
defaults:
  resource_profile: small

# Data quality settings
quality:
  fail_on_error: true
  warn_threshold: 0.01

# Freshness monitoring
freshness:
  default_warn_hours: 12
  default_error_hours: 24
'''

# DevContainer connects to existing infrastructure (started via `make up`)
DEVCONTAINER_JSON = '''{{
  "name": "Ratatouille Workspace: {name}",
  "build": {{
    "dockerfile": "Dockerfile",
    "context": "."
  }},
  "workspaceFolder": "/workspace",

  "features": {{
    "ghcr.io/devcontainers/features/git:1": {{}}
  }},

  "customizations": {{
    "vscode": {{
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-toolsai.jupyter",
        "redhat.vscode-yaml",
        "charliermarsh.ruff"
      ],
      "settings": {{
        "python.defaultInterpreterPath": "/usr/local/bin/python",
        "[python]": {{
          "editor.defaultFormatter": "charliermarsh.ruff"
        }}
      }}
    }}
  }},

  "mounts": [
    "source=${{localWorkspaceFolder}},target=/workspace,type=bind",
    "source=${{localWorkspaceFolder}}/../..,target=/ratatouille,type=bind,readonly"
  ],

  "runArgs": [
    "--network=ratatouille_default"
  ],

  "containerEnv": {{
    "RATATOUILLE_WORKSPACE": "{name}",
    "MINIO_ENDPOINT": "http://ratatouille-minio:9000",
    "MINIO_ACCESS_KEY": "ratatouille",
    "MINIO_SECRET_KEY": "ratatouille123",
    "NESSIE_URI": "http://ratatouille-nessie:19120/api/v1",
    "PYTHONPATH": "/ratatouille/src"
  }},

  "postCreateCommand": "bash .devcontainer/post-create.sh",
  "postStartCommand": "echo '🐀 Connected to Ratatouille services!'",

  "remoteUser": "vscode"
}}
'''

DOCKERFILE = '''# 🐀 Ratatouille Workspace DevContainer
# Connects to existing Ratatouille infrastructure (MinIO, Nessie, etc.)

FROM mcr.microsoft.com/devcontainers/python:3.11

RUN apt-get update && apt-get install -y --no-install-recommends \\
    curl git && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN pip install --upgrade pip && pip install --no-cache-dir \\
    duckdb>=1.0.0 pandas>=2.0.0 pyarrow>=15.0.0 \\
    pyyaml>=6.0.0 jinja2>=3.1.0 rich>=13.0.0 \\
    boto3>=1.34.0 httpx>=0.27.0 jupyterlab>=4.0.0
'''

POST_CREATE_SH = '''#!/bin/bash
# 🐀 Ratatouille Workspace Setup
# Connects to existing infrastructure started via `make up`

echo "🐀 Setting up Ratatouille workspace..."
echo ""

# Check if services are running
echo "🔍 Checking services..."

check_service() {{
    local name=$1
    local url=$2
    if curl -sf "$url" > /dev/null 2>&1; then
        echo "   ✅ $name is running"
        return 0
    else
        echo "   ❌ $name is NOT running at $url"
        return 1
    fi
}}

SERVICES_OK=true
check_service "MinIO" "http://ratatouille-minio:9000/minio/health/live" || SERVICES_OK=false
check_service "Nessie" "http://ratatouille-nessie:19120/api/v2/config" || SERVICES_OK=false

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

# Install ratatouille - use PYTHONPATH for local development
echo ""
echo "📦 Setting up ratatouille..."

if [ -d "/ratatouille/src/ratatouille" ]; then
    echo "   ✅ Using local ratatouille via PYTHONPATH"
    echo "   Path: /ratatouille/src"
    pip install -q duckdb pandas pyarrow pyyaml jinja2 rich boto3 httpx 2>/dev/null || true
else
    echo "   📥 Installing from git..."
    if pip install -q "ratatouille @ git+https://github.com/ratatouille-data/ratatouille.git" 2>/dev/null; then
        echo "   ✅ Installed from git"
    else
        echo "   ⚠️  Git install failed"
        echo "   Install manually: pip install git+https://github.com/ratatouille-data/ratatouille.git"
    fi
fi

# Create workspace bucket if services are running
if [ "$SERVICES_OK" = true ]; then
    echo ""
    echo "🪣 Setting up workspace bucket..."
    python << 'EOF'
import os
import sys
if os.path.exists("/ratatouille/src"):
    sys.path.insert(0, "/ratatouille/src")

import boto3
from botocore.client import Config

try:
    s3 = boto3.client("s3",
        endpoint_url=os.environ.get("MINIO_ENDPOINT"),
        aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY"),
        config=Config(signature_version="s3v4"))

    workspace = os.environ.get("RATATOUILLE_WORKSPACE", "default")
    bucket = f"ratatouille-{{workspace}}"

    try:
        s3.head_bucket(Bucket=bucket)
        print(f"   ✅ Bucket '{{bucket}}' exists")
    except:
        s3.create_bucket(Bucket=bucket)
        print(f"   ✅ Created bucket '{{bucket}}'")
except Exception as e:
    print(f"   ⚠️  Bucket setup: {{e}}")
EOF
fi

echo ""
echo "🐀 Workspace ready!"
echo ""
echo "Quick start:"
echo "  from ratatouille import tools"
echo "  tools.info()"
echo ""
'''

CLAUDE_MD = '''# 🐀 Ratatouille Workspace - Claude Guidelines

## ⛔ STRICT SECURITY RULES

### NEVER Read These Files
- `*.parquet`, `*.csv`, `*.duckdb` - Data files
- `.env*`, `credentials*`, `secrets*` - Secrets
- `data/` directory - Any data content

### NEVER Execute
- `cat`/`head`/`tail` on data files
- `SELECT *` queries that return actual data
- Commands that expose credentials or env vars

## ✅ ALLOWED Actions

### You CAN:
- Read/write pipeline files (`pipelines/**/*.sql`, `*.yaml`, `*.py`)
- Read/write `workspace.yaml`
- Run schema queries: `DESCRIBE`, `SHOW TABLES`, `COUNT(*)`
- Run `make` commands
- Create new pipeline files

### Safe Query Examples:
```sql
DESCRIBE table_name;
SHOW TABLES;
SELECT COUNT(*) FROM events;
SELECT device, COUNT(*) FROM events GROUP BY device;
```

## 💬 When User Asks for Data

1. **Politely decline** - You cannot access data directly
2. **Suggest alternatives** - Ask user to run query and share results
3. **Help debug** - Work with schemas and user descriptions
'''

CLAUDE_SETTINGS = '''{{
  "$schema": "https://claude.ai/claude-code/settings.schema.json",
  "permissions": {{
    "deny": [
      "Read(data/**)",
      "Read(**/*.parquet)",
      "Read(**/*.csv)",
      "Read(**/*.duckdb)",
      "Read(**/.env*)",
      "Read(**/credentials*)",
      "Read(**/secrets*)"
    ],
    "allow": [
      "Read(pipelines/**)",
      "Read(workspace.yaml)",
      "Read(CLAUDE.md)",
      "Read(README.md)",
      "Read(.devcontainer/**)",
      "Edit(pipelines/**)",
      "Write(pipelines/**)",
      "Bash(make *)",
      "Bash(git *)"
    ]
  }}
}}
'''

GITIGNORE = '''# Data
data/
*.parquet
*.csv
*.duckdb

# Python
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/

# Environment
.env
.env.*

# IDE
.idea/
.vscode/*
!.vscode/settings.json
'''

README_MD = '''# 🐀 {name}

A Ratatouille data workspace.

## Prerequisites

**Start the Ratatouille infrastructure first:**

```bash
# From the ratatouille repo root
make up
```

## Quick Start

1. Make sure `make up` is running
2. Open this folder in VS Code
3. Click "Reopen in Container" when prompted
4. The devcontainer connects to the running services

```python
from ratatouille import tools

tools.info()              # Workspace info
tools.connections()       # Check services
tools.tables()            # List tables
tools.ls("bronze/")       # Browse S3
```

## Structure

```
{name}/
├── .devcontainer/    # DevContainer config
├── .claude/          # Claude Code settings
├── pipelines/
│   ├── bronze/       # Raw data ingestion
│   ├── silver/       # Cleaned & validated
│   └── gold/         # Business-ready
├── workspace.yaml    # Configuration
└── CLAUDE.md         # AI assistant rules
```

## Services (via `make up`)

| Service | URL |
|---------|-----|
| MinIO | http://localhost:9001 |
| Nessie | http://localhost:19120 |
| Dagster | http://localhost:3030 |
| Jupyter | http://localhost:8889 |
'''

EXAMPLE_BRONZE_PY = '''"""
🐀 Bronze: Example Data Ingestion

This is a placeholder. Replace with your data source.
"""

import pandas as pd
from datetime import datetime


def ingest() -> pd.DataFrame:
    """Generate or fetch raw data."""
    # TODO: Replace with actual data source
    # Examples:
    #   - API fetch
    #   - Database query
    #   - File read

    return pd.DataFrame({{
        "id": [1, 2, 3],
        "value": ["a", "b", "c"],
        "timestamp": [datetime.now()] * 3
    }})


if __name__ == "__main__":
    df = ingest()
    print(f"Ingested {{len(df)}} rows")
'''


def scaffold_workspace(name: str, target: Path) -> None:
    """Create a new workspace with all necessary files."""
    target.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    dirs = [
        ".devcontainer",
        ".claude",
        "pipelines/bronze",
        "pipelines/silver",
        "pipelines/gold",
    ]
    for d in dirs:
        (target / d).mkdir(parents=True, exist_ok=True)

    # Write files
    files: dict[str, str] = {
        "workspace.yaml": WORKSPACE_YAML.format(name=name),
        ".devcontainer/devcontainer.json": DEVCONTAINER_JSON.format(name=name),
        ".devcontainer/Dockerfile": DOCKERFILE,
        ".devcontainer/post-create.sh": POST_CREATE_SH.format(name=name),
        ".claude/settings.json": CLAUDE_SETTINGS,
        "CLAUDE.md": CLAUDE_MD,
        ".gitignore": GITIGNORE,
        "README.md": README_MD.format(name=name),
        "pipelines/bronze/example_ingest.py": EXAMPLE_BRONZE_PY,
    }

    for path, content in files.items():
        file_path = target / path
        file_path.write_text(content)

    # Make post-create.sh executable
    post_create = target / ".devcontainer" / "post-create.sh"
    post_create.chmod(post_create.stat().st_mode | 0o111)
