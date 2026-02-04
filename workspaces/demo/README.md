# 🐀 Demo Workspace

A demo workspace showcasing Ratatouille's data pipeline capabilities.

## Quick Start

### Option 1: VS Code DevContainer (Recommended)

1. Open this folder in VS Code
2. Click "Reopen in Container" when prompted
3. Wait for setup to complete

### Option 2: Manual Setup

```bash
# Start services
docker compose -f .devcontainer/docker-compose.yml up -d minio nessie

# Install ratatouille
pip install git+https://github.com/ratatouille-data/ratatouille.git

# Run setup
bash .devcontainer/post-create.sh
```

## What's Included

This workspace demonstrates two data scenarios:

### 📊 POS Sales Pipeline
Transaction data from retail stores → Daily KPIs

```
bronze/ingest_sales.py  →  silver/sales.sql  →  gold/daily_sales.sql
```

### 🌐 Web Analytics Pipeline
User events from web tracking → Page & device metrics

```
bronze/ingest_events.py  →  silver/events.sql  →  gold/page_metrics.sql
                                              →  gold/device_metrics.sql
```

## Usage

```python
from ratatouille import sdk

# Query data
df = sdk.query("SELECT * FROM gold.daily_sales LIMIT 10")

# Run a pipeline
sdk.run("silver.sales")

# Run with full refresh
sdk.run("gold.daily_sales", full_refresh=True)
```

## Services

| Service | URL | Credentials |
|---------|-----|-------------|
| MinIO Console | http://localhost:9001 | ratatouille / ratatouille123 |
| Nessie | http://localhost:19120 | - |
| Jupyter (optional) | http://localhost:8888 | token: ratatouille |

To enable Jupyter:
```bash
docker compose -f .devcontainer/docker-compose.yml --profile jupyter up -d
```

## File Structure

```
demo/
├── .devcontainer/       # DevContainer config
├── pipelines/
│   ├── bronze/          # Raw data ingestion
│   ├── silver/          # Cleaned & validated
│   └── gold/            # Business-ready KPIs
├── workspace.yaml       # Workspace configuration
└── README.md
```
