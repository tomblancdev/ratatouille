"""
🐀 Ratatouille Workspace Templates

Scaffolds new workspaces with all necessary files.
"""

from pathlib import Path

# Template strings embedded for portability

WORKSPACE_YAML = """# 🐀 Ratatouille Workspace Configuration

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
"""

# DevContainer uses pre-built image
DEVCONTAINER_JSON = """{{
  "name": "Ratatouille Workspace: {name}",
  "image": "ratatouille-workspace:latest",
  "workspaceFolder": "/workspace",

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
    "source=${{localWorkspaceFolder}},target=/workspace,type=bind"
  ],

  "runArgs": [
    "--add-host=host.docker.internal:host-gateway"
  ],

  "containerEnv": {{
    "RATATOUILLE_WORKSPACE": "{name}",
    "MINIO_ENDPOINT": "http://host.docker.internal:9000",
    "MINIO_ACCESS_KEY": "ratatouille",
    "MINIO_SECRET_KEY": "ratatouille123",
    "NESSIE_URI": "http://host.docker.internal:19120/api/v2"
  }},

  "postStartCommand": "bash -c 'echo \\"🐀 Workspace ready!\\" && python -c \\"from ratatouille import tools; tools.connections()\\" 2>/dev/null || echo \\"Run make up first!\\"'",

  "remoteUser": "vscode"
}}
"""

CLAUDE_MD = """# 🐀 Ratatouille Workspace - Claude Guidelines

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
"""

CLAUDE_SETTINGS = """{{
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
"""

GITIGNORE = """# Data
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
"""

README_MD = """# 🐀 {name}

A Ratatouille data workspace.

## Prerequisites

1. **Build the workspace image** (first time only):
   ```bash
   cd /path/to/ratatouille
   make build-workspace
   ```

2. **Start the infrastructure**:
   ```bash
   make up
   ```

## Quick Start

1. Open this folder in VS Code
2. Click "Reopen in Container" when prompted
3. The devcontainer uses the pre-built image and connects to running services

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
"""

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

    # Write files (no Dockerfile or post-create.sh needed with pre-built image)
    files: dict[str, str] = {
        "workspace.yaml": WORKSPACE_YAML.format(name=name),
        ".devcontainer/devcontainer.json": DEVCONTAINER_JSON.format(name=name),
        ".claude/settings.json": CLAUDE_SETTINGS,
        "CLAUDE.md": CLAUDE_MD,
        ".gitignore": GITIGNORE,
        "README.md": README_MD.format(name=name),
        "pipelines/bronze/example_ingest.py": EXAMPLE_BRONZE_PY,
    }

    for path, content in files.items():
        file_path = target / path
        file_path.write_text(content)
