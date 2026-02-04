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

DEVCONTAINER_JSON = '''{{
  "name": "Ratatouille Workspace: {name}",
  "dockerComposeFile": "docker-compose.yml",
  "service": "workspace",
  "workspaceFolder": "/workspace",

  "features": {{
    "ghcr.io/devcontainers/features/python:1": {{
      "version": "3.11"
    }},
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

  "forwardPorts": [8888, 9000, 9001, 19120],
  "postCreateCommand": "bash .devcontainer/post-create.sh",

  "remoteEnv": {{
    "RATATOUILLE_WORKSPACE": "{name}",
    "MINIO_ENDPOINT": "http://minio:9000",
    "MINIO_ACCESS_KEY": "ratatouille",
    "MINIO_SECRET_KEY": "ratatouille123",
    "NESSIE_URI": "http://nessie:19120/api/v1"
  }}
}}
'''

DOCKER_COMPOSE_YML = '''# 🐀 Ratatouille Workspace DevContainer Services
version: "3.8"

services:
  workspace:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ..:/workspace:cached
    environment:
      - RATATOUILLE_WORKSPACE={name}
      - MINIO_ENDPOINT=http://minio:9000
      - MINIO_ACCESS_KEY=ratatouille
      - MINIO_SECRET_KEY=ratatouille123
      - NESSIE_URI=http://nessie:19120/api/v1
    depends_on:
      - minio
      - nessie
    command: sleep infinity

  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: ratatouille
      MINIO_ROOT_PASSWORD: ratatouille123
    command: server /data --console-address ":9001"
    volumes:
      - minio-data:/data

  nessie:
    image: ghcr.io/projectnessie/nessie:latest
    ports:
      - "19120:19120"
    environment:
      - NESSIE_VERSION_STORE_TYPE=IN_MEMORY

  jupyter:
    image: jupyter/minimal-notebook:python-3.11
    ports:
      - "8888:8888"
    environment:
      - JUPYTER_TOKEN=ratatouille
    volumes:
      - ..:/home/jovyan/workspace:cached
    profiles:
      - jupyter

volumes:
  minio-data:
'''

DOCKERFILE = '''# 🐀 Ratatouille Workspace DevContainer
FROM mcr.microsoft.com/devcontainers/python:3.11

RUN apt-get update && apt-get install -y --no-install-recommends \\
    curl git && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN pip install --upgrade pip && pip install --no-cache-dir \\
    duckdb>=1.0.0 pandas>=2.0.0 pyarrow>=15.0.0 \\
    pyyaml>=6.0.0 jinja2>=3.1.0 rich>=13.0.0 jupyterlab>=4.0.0
'''

POST_CREATE_SH = '''#!/bin/bash
# 🐀 Ratatouille Workspace Setup
set -e

echo "🐀 Setting up Ratatouille workspace..."

# Install ratatouille from git
if pip install "ratatouille @ git+https://github.com/ratatouille-data/ratatouille.git" 2>/dev/null; then
    echo "📦 Installed ratatouille from git"
else
    echo "⚠️  Could not install ratatouille. Install manually or check network."
fi

# Create MinIO bucket
echo "🪣 Setting up MinIO bucket..."
python << 'EOF'
import os, boto3
from botocore.client import Config

try:
    s3 = boto3.client("s3",
        endpoint_url=os.environ.get("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY", "ratatouille"),
        aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY", "ratatouille123"),
        config=Config(signature_version="s3v4"))
    bucket = f"ratatouille-{os.environ.get('RATATOUILLE_WORKSPACE', 'default')}"
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"✅ Bucket '{{bucket}}' exists")
    except:
        s3.create_bucket(Bucket=bucket)
        print(f"✅ Created bucket '{{bucket}}'")
except Exception as e:
    print(f"⚠️  MinIO setup: {{e}}")
EOF

echo ""
echo "🐀 Workspace ready!"
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

CLAUDE_SETTINGS = '''{
  "$schema": "https://claude.ai/claude-code/settings.schema.json",
  "permissions": {
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
  }
}
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

## Quick Start

1. Open this folder in VS Code
2. Click "Reopen in Container" when prompted
3. Start building pipelines!

```python
from ratatouille import sdk

# Query data
sdk.query("SHOW TABLES")

# Run a pipeline
sdk.run("silver.my_pipeline")
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

## Services

| Service | URL |
|---------|-----|
| MinIO | http://localhost:9001 |
| Nessie | http://localhost:19120 |
| Jupyter | http://localhost:8888 (optional) |
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

    return pd.DataFrame({
        "id": [1, 2, 3],
        "value": ["a", "b", "c"],
        "timestamp": [datetime.now()] * 3
    })


if __name__ == "__main__":
    df = ingest()
    print(f"Ingested {len(df)} rows")
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
        ".devcontainer/docker-compose.yml": DOCKER_COMPOSE_YML.format(name=name),
        ".devcontainer/Dockerfile": DOCKERFILE,
        ".devcontainer/post-create.sh": POST_CREATE_SH,
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
