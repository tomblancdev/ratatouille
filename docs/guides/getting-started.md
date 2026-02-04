# 🚀 Getting Started with Ratatouille

Get your self-hosted data platform running in minutes!

## Prerequisites

- Docker or Podman
- Python 3.11+
- 4GB+ RAM (8GB recommended)

## Quick Start

### 1. Start Infrastructure

```bash
# Start MinIO (S3), Nessie (Catalog), and other services
podman compose up -d

# Or with Docker
docker compose up -d
```

### 2. Install Ratatouille

```bash
# Install with pip
pip install -e ".[dev]"

# Or use the requirements.txt
pip install -r requirements.txt
```

### 3. Create Your First Workspace

```python
from ratatouille.workspace import Workspace

# Create a workspace
ws = Workspace.create(
    name="my-project",
    description="My first Ratatouille project",
)
```

### 4. Create a Pipeline

Create `workspaces/my-project/pipelines/bronze/ingest.py`:

```python
from ratatouille.pipeline import bronze_pipeline
import pandas as pd

@bronze_pipeline(name="raw_sales")
def ingest_sales(context):
    # Your ingestion logic
    df = pd.DataFrame({
        "id": range(100),
        "amount": [i * 10.0 for i in range(100)],
    })
    context.write("bronze.raw_sales", df)
```

Create `workspaces/my-project/pipelines/silver/sales.sql`:

```sql
-- @name: silver_sales
-- @materialized: incremental
-- @unique_key: id

SELECT
    id,
    amount,
    amount * 0.1 AS tax,
    NOW() AS _processed_at
FROM {{ ref('bronze.raw_sales') }}
WHERE amount > 0
{% if is_incremental() %}
  AND _ingested_at > '{{ watermark("_ingested_at") }}'
{% endif %}
```

### 5. Run Your Pipeline

```python
from ratatouille.workspace import Workspace
from ratatouille.pipeline import discover_pipelines, build_dag, PipelineExecutor

ws = Workspace.load("my-project")
pipelines = discover_pipelines(ws.path / "pipelines")
dag = build_dag(pipelines)

executor = PipelineExecutor(ws)
executor.run_pipeline("silver_sales")
```

## Project Structure

```
ratatouille/
├── workspaces/
│   └── my-project/
│       ├── workspace.yaml      # Workspace config
│       └── pipelines/
│           ├── bronze/         # Raw data
│           │   └── ingest.py
│           ├── silver/         # Cleaned data
│           │   ├── sales.sql
│           │   └── sales.yaml
│           └── gold/           # Business metrics
│               ├── kpis.sql
│               └── kpis.yaml
├── config/
│   └── profiles/               # Resource profiles
│       ├── tiny.yaml
│       ├── small.yaml
│       └── medium.yaml
└── docker-compose.yml          # Infrastructure
```

## Key Concepts

### Medallion Architecture

| Layer | Purpose | Example |
|-------|---------|---------|
| **Bronze** | Raw, immutable data | `bronze.raw_sales` |
| **Silver** | Cleaned, validated | `silver.sales` |
| **Gold** | Business aggregations | `gold.daily_kpis` |

### Workspaces

Isolated environments with:
- Own Nessie branch (catalog)
- Own S3 prefix (storage)
- Own pipelines and config

### Data Products

Share data between workspaces:
```yaml
# Publisher workspace
products:
  - name: sales_metrics
    source: gold.daily_sales

# Consumer workspace
subscriptions:
  - product: sales_metrics
    alias: sales
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `S3_ENDPOINT` | MinIO/S3 URL | `http://localhost:9000` |
| `S3_ACCESS_KEY` | S3 access key | `ratatouille` |
| `S3_SECRET_KEY` | S3 secret key | `ratatouille123` |
| `NESSIE_URI` | Nessie catalog URL | `http://localhost:19120/api/v2` |
| `RAT_PROFILE` | Resource profile | `small` |

## Next Steps

- 📖 [Pipeline Development Guide](./pipelines.md)
- 🏢 [Workspaces Guide](./workspaces.md)
- 📦 [Data Products Guide](./data-products.md)

## Troubleshooting

### Services not starting?

```bash
# Check service status
podman compose ps

# View logs
podman compose logs nessie
podman compose logs minio
```

### Out of memory?

Use a smaller resource profile:

```yaml
# workspace.yaml
resources:
  profile: tiny  # For 4GB VM
```

### Connection refused?

Ensure services are running and environment variables are set:

```bash
export S3_ENDPOINT=http://localhost:9000
export NESSIE_URI=http://localhost:19120/api/v2
```
