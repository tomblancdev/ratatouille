# 🐀 Demo Workspace

A demo workspace showcasing Ratatouille's data pipeline capabilities.

## Prerequisites

**Start the Ratatouille infrastructure first:**

```bash
# From the ratatouille repo root
make up
```

This starts MinIO, Nessie, Dagster, and Jupyter. The devcontainer will connect to these services.

## Quick Start

### Option 1: VS Code DevContainer (Recommended)

1. Make sure `make up` is running
2. Open this folder (`workspaces/demo/`) in VS Code
3. Click "Reopen in Container" when prompted
4. The devcontainer connects to the running services

### Option 2: Use Jupyter (already running)

```bash
# Open http://localhost:8889 (token: ratatouille)
# Navigate to workspaces/demo/
```

### Option 3: Manual Python

```bash
# Set environment variables
export MINIO_ENDPOINT=http://localhost:9000
export MINIO_ACCESS_KEY=ratatouille
export MINIO_SECRET_KEY=ratatouille123
export NESSIE_URI=http://localhost:19120/api/v1
export RATATOUILLE_WORKSPACE=demo

# Install and use
pip install git+https://github.com/ratatouille-data/ratatouille.git
python -c "from ratatouille import tools; tools.info()"
```

## What's Included

### 📊 POS Sales Pipeline
```
bronze/ingest_sales.py  →  silver/sales.sql  →  gold/daily_sales.sql
```

### 🌐 Web Analytics Pipeline
```
bronze/ingest_events.py  →  silver/events.sql  →  gold/page_metrics.sql
                                              →  gold/device_metrics.sql
```

## Usage

```python
from ratatouille import tools

# Explore workspace
tools.info()              # Workspace details
tools.connections()       # Check service health
tools.env()               # Environment config

# Browse data
tools.ls()                # List S3 root
tools.ls("bronze/")       # List bronze layer
tools.tables()            # List all tables
tools.tree()              # Folder structure

# Inspect tables
tools.schema("silver.events")   # Column schema
tools.count("silver.events")    # Row count
tools.preview("silver.events")  # First 10 rows
tools.describe("silver.events") # Full stats

# Get paths
tools.s3_uri("silver", "events")  # Full S3 URI
tools.bucket_name()               # Bucket name
```

## Services (via `make up`)

| Service | URL | Credentials |
|---------|-----|-------------|
| MinIO Console | http://localhost:9001 | ratatouille / ratatouille123 |
| Nessie | http://localhost:19120 | - |
| Dagster | http://localhost:3030 | - |
| Jupyter | http://localhost:8889 | token: ratatouille |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Host Machine                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │          make up (docker-compose)                    │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │
│  │  │  MinIO  │ │ Nessie  │ │ Dagster │ │ Jupyter │   │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │   │
│  │       └───────────┴───────────┴───────────┘         │   │
│  │                    Network: ratatouille_default     │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│  ┌───────────────────────────┴─────────────────────────┐   │
│  │           Workspace DevContainer                     │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  Python + ratatouille tools                 │    │   │
│  │  │  Connects to services via network           │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
demo/
├── .devcontainer/       # DevContainer config (connects to services)
├── .claude/             # Claude Code security rules
├── pipelines/
│   ├── bronze/          # Raw data ingestion
│   ├── silver/          # Cleaned & validated
│   └── gold/            # Business-ready KPIs
├── workspace.yaml       # Workspace configuration
├── CLAUDE.md            # AI assistant guidelines
└── README.md
```
