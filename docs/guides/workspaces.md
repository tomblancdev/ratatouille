# 🏢 Workspaces Guide

Workspaces provide **isolation** for teams and projects, with separate storage, catalog branches, and configurations.

## Overview

```
┌────────────────────────────────────────────────────────────────┐
│                      RATATOUILLE                                │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐│
│  │   Workspace A   │  │   Workspace B   │  │   Workspace C   ││
│  │  ─────────────  │  │  ─────────────  │  │  ─────────────  ││
│  │  Nessie: ws/a   │  │  Nessie: ws/b   │  │  Nessie: ws/c   ││
│  │  S3: acme/*     │  │  S3: analytics/*│  │  S3: finance/*  ││
│  │                 │  │                 │  │                 ││
│  │  pipelines/     │  │  pipelines/     │  │  pipelines/     ││
│  │  ├─ bronze/     │  │  ├─ bronze/     │  │  ├─ bronze/     ││
│  │  ├─ silver/     │  │  ├─ silver/     │  │  ├─ silver/     ││
│  │  └─ gold/       │  │  └─ gold/       │  │  └─ gold/       ││
│  └─────────────────┘  └─────────────────┘  └─────────────────┘│
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │              Shared Services                                ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                  ││
│  │  │  Nessie  │  │  MinIO   │  │  DuckDB  │                  ││
│  │  │ (Catalog)│  │   (S3)   │  │ (Engine) │                  ││
│  │  └──────────┘  └──────────┘  └──────────┘                  ││
│  └────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────┘
```

## Isolation Model

Each workspace has:

| Isolation | How |
|-----------|-----|
| **Catalog** | Dedicated Nessie branch |
| **Storage** | Dedicated S3 prefix |
| **Resources** | Configurable limits |
| **Pipelines** | Own pipeline definitions |

## Creating a Workspace

### Via Code

```python
from ratatouille.workspace import Workspace

ws = Workspace.create(
    name="analytics",
    description="Analytics team workspace",
)

print(f"Created: {ws.name}")
print(f"Nessie branch: {ws.nessie_branch}")
print(f"S3 prefix: {ws.s3_prefix}")
```

### Directory Structure

```
workspaces/
└── analytics/
    ├── workspace.yaml      # Configuration
    ├── pipelines/
    │   ├── bronze/         # Raw data ingestion
    │   ├── silver/         # Cleaned data
    │   └── gold/           # Business metrics
    ├── schemas/            # Shared schemas
    ├── macros/             # Shared SQL macros
    └── notebooks/          # Jupyter notebooks
```

## Workspace Configuration

### workspace.yaml

```yaml
# 🐀 Analytics Workspace
name: analytics
version: "1.0"
description: "Analytics team workspace - BI and reporting"

# Isolation settings
isolation:
  nessie_branch: "workspace/analytics"
  s3_prefix: "analytics"

# Resource limits
resources:
  profile: small           # Use small.yaml profile
  overrides:
    max_memory_mb: 8192    # Override specific settings
    max_parallel_pipelines: 4

# Medallion layer settings
layers:
  bronze:
    retention_days: 90
    partition_by: [_ingested_date]
  silver:
    retention_days: 365
    partition_by: [_date]
  gold:
    retention_days: null    # Keep forever

# Data products published by this workspace
products:
  - name: daily_sales_kpis
    source: gold.daily_sales
    access:
      - workspace: "*"
        level: read

# Data products consumed from other workspaces
subscriptions:
  - product: external/inventory
    alias: inventory
    version_constraint: "^1.0.0"
```

### Configuration Options

#### Isolation

```yaml
isolation:
  nessie_branch: "workspace/my-team"   # Catalog branch
  s3_prefix: "my-team"                  # S3 path prefix
```

#### Resources

```yaml
resources:
  profile: small  # tiny, small, medium, large
  overrides:
    max_memory_mb: 4096
    max_parallel_pipelines: 2
    chunk_size_rows: 50000
```

#### Layers

```yaml
layers:
  bronze:
    retention_days: 90      # Auto-delete after 90 days
    partition_by: [_date]   # Default partition columns
  silver:
    retention_days: 365
  gold:
    retention_days: null    # Never delete
```

## Resource Profiles

Pre-configured profiles for different VM sizes:

### tiny.yaml (4GB VM)

```yaml
resources:
  max_memory_mb: 1024
  duckdb_memory_mb: 2048
  chunk_size_rows: 10000
  max_parallel_pipelines: 1
```

### small.yaml (20GB VM)

```yaml
resources:
  max_memory_mb: 4096
  duckdb_memory_mb: 8192
  chunk_size_rows: 50000
  max_parallel_pipelines: 2
```

### medium.yaml (64GB VM)

```yaml
resources:
  max_memory_mb: 16384
  duckdb_memory_mb: 32768
  chunk_size_rows: 200000
  max_parallel_pipelines: 4
```

### large.yaml (128GB+ VM)

```yaml
resources:
  max_memory_mb: 65536
  duckdb_memory_mb: 98304
  chunk_size_rows: 500000
  max_parallel_pipelines: 8
```

## Working with Workspaces

### Loading a Workspace

```python
from ratatouille.workspace import Workspace, get_workspace

# Load by name
ws = Workspace.load("analytics")

# Get cached workspace (recommended)
ws = get_workspace("analytics")

# Load from environment variable WORKSPACE
ws = get_workspace()  # Uses $WORKSPACE or "default"
```

### Using the Engine

```python
ws = Workspace.load("analytics")
engine = ws.get_engine()

# Query data
df = engine.query("SELECT * FROM bronze.sales LIMIT 100")

# Write data
engine.write_parquet(df, ws.s3_path("silver", "cleaned_sales"))
```

### Listing Pipelines

```python
ws = Workspace.load("analytics")
pipelines = ws.list_pipelines()

print("Bronze pipelines:", pipelines["bronze"])
print("Silver pipelines:", pipelines["silver"])
print("Gold pipelines:", pipelines["gold"])
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WORKSPACE` | Default workspace name | `default` |
| `S3_ENDPOINT` | MinIO/S3 endpoint | `http://localhost:9000` |
| `S3_ACCESS_KEY` | S3 access key | `ratatouille` |
| `S3_SECRET_KEY` | S3 secret key | `ratatouille123` |
| `NESSIE_URI` | Nessie API URL | `http://localhost:19120/api/v2` |
| `ICEBERG_WAREHOUSE` | Base S3 path | `s3://warehouse` |
| `RAT_PROFILE` | Resource profile | `small` |

## Multi-Workspace Setup

### Development + Production

```
workspaces/
├── dev/                   # Development workspace
│   └── workspace.yaml
├── staging/               # Staging workspace
│   └── workspace.yaml
└── prod/                  # Production workspace
    └── workspace.yaml
```

### Team-Based

```
workspaces/
├── analytics/             # Analytics team
├── finance/               # Finance team
├── marketing/             # Marketing team
└── platform/              # Platform/shared
```

### Project-Based

```
workspaces/
├── customer-360/          # Customer 360 project
├── supply-chain/          # Supply chain project
└── fraud-detection/       # Fraud detection project
```

## Mounting External Workspaces

You can mount workspaces from anywhere on your filesystem using Docker/Podman volumes. This is useful for:

- Keeping workspaces in project-specific directories
- Working with client projects in separate locations
- Sharing workspaces across multiple Ratatouille installations

### Basic Volume Mount

Add volume mounts to your `docker-compose.yml`:

```yaml
services:
  dagster:
    volumes:
      - ./src:/app/src
      - ./workspaces:/app/workspaces
      # Mount external workspaces 👇
      - /home/tom/projects/analytics:/app/workspaces/analytics
      - /home/tom/clients/acme:/app/workspaces/acme
      - ~/finance-data:/app/workspaces/finance

  jupyter:
    volumes:
      - ./src:/app/src
      - ./workspaces:/app/workspaces
      # Same mounts for Jupyter 👇
      - /home/tom/projects/analytics:/app/workspaces/analytics
      - /home/tom/clients/acme:/app/workspaces/acme
      - ~/finance-data:/app/workspaces/finance
```

Then access them normally:

```bash
rat test -w analytics
rat docs generate -w acme
rat test -w finance
```

### Using docker-compose.override.yml

Keep custom mounts separate from the main config using an override file:

```yaml
# docker-compose.override.yml (add to .gitignore)
services:
  dagster:
    volumes:
      - /home/tom/projects/analytics:/app/workspaces/analytics
      - /home/tom/clients/acme:/app/workspaces/acme

  jupyter:
    volumes:
      - /home/tom/projects/analytics:/app/workspaces/analytics
      - /home/tom/clients/acme:/app/workspaces/acme
```

Docker Compose automatically merges `docker-compose.override.yml` with the main file.

### Environment-Based Mounts

Use environment variables for flexible paths:

```yaml
# docker-compose.yml
services:
  dagster:
    volumes:
      - ${ANALYTICS_PATH:-./workspaces/analytics}:/app/workspaces/analytics
      - ${FINANCE_PATH:-./workspaces/finance}:/app/workspaces/finance
```

```bash
# .env
ANALYTICS_PATH=/home/tom/projects/analytics
FINANCE_PATH=/home/tom/clients/acme/finance
```

### Mount Patterns

| Pattern | Use Case |
|---------|----------|
| `./workspaces:/app/workspaces` | Default - local workspaces folder |
| `/abs/path:/app/workspaces/name` | Mount external directory as workspace |
| `~/projects/foo:/app/workspaces/foo` | Mount from home directory |
| `${VAR}:/app/workspaces/name` | Dynamic path from environment |

### Important Notes

1. **Both services need mounts** - Add the same volumes to both `dagster` and `jupyter` services
2. **Workspace name = mount name** - The directory name under `/app/workspaces/` becomes the workspace name
3. **Permissions** - Ensure the container user can read/write the mounted directory
4. **Restart required** - Run `podman compose down && podman compose up -d` after changing mounts

---

## Best Practices

### 1. One Workspace Per Team/Project

Keep workspaces focused and isolated:
- Analytics team → `analytics` workspace
- Finance team → `finance` workspace
- Shared data → Use Data Products to share

### 2. Use Resource Profiles

Match profile to your VM:

```yaml
resources:
  profile: small  # For 20GB VM
```

### 3. Set Retention Policies

Don't keep data forever:

```yaml
layers:
  bronze:
    retention_days: 90   # Raw data expires
  gold:
    retention_days: null # Business metrics kept
```

### 4. Document Your Workspace

```yaml
description: |
  Analytics team workspace for BI and reporting.

  Key pipelines:
  - daily_sales: Daily sales KPIs
  - customer_segments: Customer segmentation

  Contact: analytics-team@company.com
```

### 5. Share Data via Products

Don't access other workspaces directly - use Data Products:

```yaml
# Don't do this:
# SELECT * FROM other_workspace.gold.metrics

# Do this:
subscriptions:
  - product: shared_metrics
    alias: metrics
```

Then use:
```sql
SELECT * FROM products.metrics
```
