# 🐀 Ratatouille v2 - Architecture Rework

> **Status**: APPROVED
> **Date**: 2026-02-04
> **Decisions**: Final

---

## 🎯 Final Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Table Format** | Iceberg + Nessie | Git-like branching, multi-tenant, REST API for permissions |
| **Query Engine** | DuckDB only | Embedded, low memory, no extra service, perfect for 20GB VM |
| **SDK Style** | dbt-like native | SQL + YAML + Python escape hatch - scales to 10B rows |
| **Data Sharing** | Data Products | Publish/Subscribe with versioning and permissions |
| **Partitioning** | Configurable per pipeline | Each pipeline defines its own strategy |
| **Resources** | Balanced profiles | Configurable for tiny → large VMs |

---

## 🏗️ Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RATATOUILLE v2                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────── DATA PRODUCTS ────────────────────────────────┐ │
│  │                     (Shared Catalog - Versioned)                       │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                       │ │
│  │  │ sales_kpis │  │ inventory  │  │ customers  │                       │ │
│  │  │ v2.1.0     │  │ v1.0.0     │  │ v3.0.0     │      publish ↑       │ │
│  │  │ owner:ws-a │  │ owner:ws-b │  │ owner:ws-a │      subscribe ↓     │ │
│  │  └────────────┘  └────────────┘  └────────────┘                       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    │                                        │
│          ┌─────────────────────────┼─────────────────────────┐             │
│          ▼                         ▼                         ▼             │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐      │
│  │    WORKSPACE A    │  │    WORKSPACE B    │  │    WORKSPACE C    │      │
│  │  ───────────────  │  │  ───────────────  │  │  ───────────────  │      │
│  │  pipelines/       │  │  pipelines/       │  │  pipelines/       │      │
│  │   ├─ bronze/      │  │   ├─ bronze/      │  │   ├─ bronze/      │      │
│  │   │  └─ *.py      │  │   │  └─ *.py      │  │   │  └─ *.py      │      │
│  │   ├─ silver/      │  │   ├─ silver/      │  │   ├─ silver/      │      │
│  │   │  ├─ *.sql     │  │   │  ├─ *.sql     │  │   │  ├─ *.sql     │      │
│  │   │  └─ *.yaml    │  │   │  └─ *.yaml    │  │   │  └─ *.yaml    │      │
│  │   └─ gold/        │  │   └─ gold/        │  │   └─ gold/        │      │
│  │      ├─ *.sql     │  │      ├─ *.sql     │  │      ├─ *.sql     │      │
│  │      └─ *.yaml    │  │      └─ *.yaml    │  │      └─ *.yaml    │      │
│  │  ───────────────  │  │  ───────────────  │  │  ───────────────  │      │
│  │  Isolated:        │  │  Isolated:        │  │  Isolated:        │      │
│  │  • Nessie branch  │  │  • Nessie branch  │  │  • Nessie branch  │      │
│  │  • S3: ws-a/*     │  │  • S3: ws-b/*     │  │  • S3: ws-c/*     │      │
│  └───────────────────┘  └───────────────────┘  └───────────────────┘      │
│                                                                              │
│  ┌────────────────────────── CORE SERVICES ─────────────────────────────┐  │
│  │                                                                        │  │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │  │
│  │   │   Nessie    │    │   DuckDB    │    │   MinIO     │              │  │
│  │   │  (Catalog)  │    │  (Engine)   │    │    (S3)     │              │  │
│  │   │             │    │             │    │             │              │  │
│  │   │ • Branches  │    │ • Embedded  │    │ • Parquet   │              │  │
│  │   │ • Commits   │    │ • Low RAM   │    │ • Iceberg   │              │  │
│  │   │ • REST API  │    │ • 10B rows  │    │ • Products  │              │  │
│  │   └─────────────┘    └─────────────┘    └─────────────┘              │  │
│  │                                                                        │  │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │  │
│  │   │   Dagster   │    │  Product    │    │  Lineage    │              │  │
│  │   │  (Orchestr) │    │  Registry   │    │  Tracker    │              │  │
│  │   └─────────────┘    └─────────────┘    └─────────────┘              │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 New Project Structure

```
ratatouille/
│
├── src/ratatouille/
│   ├── __init__.py              # Exports: rat, pipeline, ref, etc.
│   ├── rat.py                   # Main SDK entry point (simplified)
│   │
│   ├── workspace/               # 🆕 Workspace Management
│   │   ├── __init__.py
│   │   ├── manager.py           # Workspace CRUD, isolation
│   │   ├── config.py            # WorkspaceConfig (Pydantic)
│   │   └── context.py           # Current workspace context
│   │
│   ├── catalog/                 # 🆕 Nessie Catalog Integration
│   │   ├── __init__.py
│   │   ├── nessie.py            # Nessie REST client
│   │   ├── iceberg.py           # Iceberg table operations
│   │   └── branches.py          # Branch management
│   │
│   ├── engine/                  # 🆕 DuckDB Query Engine
│   │   ├── __init__.py
│   │   ├── duckdb.py            # DuckDB connection + queries
│   │   ├── iceberg_ext.py       # DuckDB Iceberg extension
│   │   └── memory.py            # Memory management
│   │
│   ├── pipeline/                # 🆕 dbt-like Pipeline Framework
│   │   ├── __init__.py
│   │   ├── loader.py            # Load SQL + YAML files
│   │   ├── parser.py            # Parse {{ ref() }}, {% if %}
│   │   ├── compiler.py          # Compile to executable SQL
│   │   ├── executor.py          # Run pipelines
│   │   ├── incremental.py       # Incremental logic
│   │   └── python_bridge.py     # Python pipeline support
│   │
│   ├── products/                # 🆕 Data Products
│   │   ├── __init__.py
│   │   ├── registry.py          # Product catalog (SQLite)
│   │   ├── publish.py           # Publish tables as products
│   │   ├── consume.py           # Consume products
│   │   └── permissions.py       # Access control
│   │
│   ├── schema/                  # 🆕 Schema Management
│   │   ├── __init__.py
│   │   ├── validator.py         # Validate DataFrames
│   │   ├── tests.py             # not_null, unique, positive, etc.
│   │   └── evolution.py         # Schema evolution
│   │
│   ├── lineage/                 # 🆕 Lineage Tracking
│   │   ├── __init__.py
│   │   ├── tracker.py           # Record transformations
│   │   └── graph.py             # Query lineage DAG
│   │
│   ├── storage/                 # S3/Parquet Operations
│   │   ├── __init__.py
│   │   ├── s3.py                # MinIO/S3 client
│   │   └── parquet.py           # Parquet read/write
│   │
│   └── resources/               # Resource Management
│       ├── __init__.py
│       ├── config.py            # ResourceConfig
│       └── profiles.py          # tiny/small/medium/large
│
├── workspaces/                  # Workspace Instances
│   └── default/
│       ├── workspace.yaml       # Workspace configuration
│       ├── pipelines/
│       │   ├── bronze/          # Python ingestion
│       │   │   └── ingest_*.py
│       │   ├── silver/          # SQL transforms
│       │   │   ├── *.sql
│       │   │   └── *.yaml
│       │   └── gold/            # SQL aggregations
│       │       ├── *.sql
│       │       └── *.yaml
│       ├── macros/              # Reusable SQL snippets
│       ├── schemas/             # Schema definitions
│       └── notebooks/
│
├── config/
│   ├── profiles/
│   │   ├── tiny.yaml            # 4GB VM
│   │   ├── small.yaml           # 20GB VM (default)
│   │   ├── medium.yaml          # 64GB VM
│   │   └── large.yaml           # 128GB+ VM
│   └── nessie/
│       └── application.yaml     # Nessie config
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── docker-compose.yml           # Full stack
├── docker-compose.minimal.yml   # DuckDB + MinIO only (no Nessie)
├── .github/workflows/ci.yml
├── .pre-commit-config.yaml
└── pyproject.toml
```

---

## 🔧 Core Components Detail

### 1. Pipeline SDK (dbt-like)

#### SQL Pipeline Example
```sql
-- workspaces/acme/pipelines/silver/sales.sql

-- Pipeline metadata (parsed by Ratatouille)
-- @name: silver_sales
-- @materialized: incremental
-- @unique_key: txn_id
-- @partition_by: _date
-- @owner: data-team

SELECT
    txn_id,
    store_id,
    product_id,
    quantity,
    unit_price,
    quantity * unit_price AS total_amount,
    payment_method,
    transaction_time,
    CAST(transaction_time AS DATE) AS _date,
    NOW() AS _processed_at
FROM {{ ref('bronze.raw_sales') }}
WHERE quantity > 0
  AND unit_price > 0
{% if is_incremental() %}
  AND transaction_time > '{{ watermark("transaction_time") }}'
{% endif %}
```

#### YAML Config Example
```yaml
# workspaces/acme/pipelines/silver/sales.yaml

description: |
  Cleaned and validated sales transactions.
  - Filters invalid records (qty <= 0, price <= 0)
  - Adds calculated total_amount
  - Partitioned by date for efficient incremental processing

owner: data-team@acme.com

# Schema definition & tests
columns:
  - name: txn_id
    type: string
    description: Unique transaction identifier
    tests:
      - not_null
      - unique

  - name: store_id
    type: string
    tests: [not_null]

  - name: quantity
    type: int
    tests:
      - not_null
      - positive

  - name: total_amount
    type: decimal(12,2)
    tests:
      - not_null
      - positive

  - name: _date
    type: date
    description: Partition column
    tests: [not_null]

# Freshness SLA
freshness:
  warn_after: { hours: 6 }
  error_after: { hours: 24 }

# Custom tests
tests:
  - name: total_equals_qty_times_price
    sql: |
      SELECT COUNT(*) FROM {{ this }}
      WHERE ABS(total_amount - quantity * unit_price) > 0.01
    expect: 0
```

#### Python Pipeline Example (for ingestion)
```python
# workspaces/acme/pipelines/bronze/ingest_sales.py

from ratatouille import pipeline, ingest
from ratatouille.parsers import excel_parser
import re

@pipeline(
    name="bronze_raw_sales",
    layer="bronze",
    schedule="0 * * * *",  # Hourly
)
def ingest_sales():
    """Ingest sales files from landing zone."""

    files = rat.ls("landing/sales/*.xlsx")

    for file_path in files:
        # Skip already processed
        if rat.is_ingested(file_path):
            continue

        # Extract metadata from filename
        # e.g., "sales_STORE001_2024-01-15.xlsx"
        match = re.match(r"sales_(\w+)_(\d{4}-\d{2}-\d{2})\.xlsx", file_path)
        if not match:
            rat.log.warning(f"Skipping {file_path}: unexpected filename format")
            continue

        store_id, date = match.groups()

        # Parse Excel with custom logic
        df = excel_parser(
            rat.read_file(file_path),
            skip_rows=3,  # Header junk
            columns_map={
                "Transaction ID": "txn_id",
                "Qty": "quantity",
                "Price": "unit_price",
            }
        )

        # Add metadata
        df["store_id"] = store_id
        df["_source_file"] = file_path
        df["_ingested_at"] = rat.now()

        # Append to bronze table
        rat.append("bronze.raw_sales", df)
        rat.mark_ingested(file_path)

        rat.log.info(f"✅ Ingested {len(df)} rows from {file_path}")
```

---

### 2. Workspace Configuration

```yaml
# workspaces/acme/workspace.yaml

name: acme
version: "1.0"
description: "ACME Corp data workspace"

# Isolation settings
isolation:
  nessie_branch: "workspace/acme"  # Dedicated Nessie branch
  s3_prefix: "acme"                 # s3://acme/bronze/*, s3://acme/silver/*

# Resource limits for this workspace
resources:
  profile: small  # Use small.yaml profile
  overrides:
    max_memory_mb: 4096
    max_parallel_pipelines: 2

# Medallion layer config
layers:
  bronze:
    retention_days: 90
    partition_by: [_ingested_date]
  silver:
    retention_days: 365
    partition_by: [_date]
  gold:
    retention_days: null  # Forever
    partition_by: []

# Data products this workspace publishes
products:
  - name: sales_kpis
    source: gold.daily_sales_kpis
    access:
      - workspace: "*"
        level: read  # Public within org
    sla:
      freshness_hours: 24

# Data products this workspace consumes
subscriptions:
  - product: inventory/stock_levels
    alias: ext_inventory  # Access as {{ ref('ext_inventory') }}
```

---

### 3. Data Products

```python
# Publishing a data product
rat.publish(
    source="gold.daily_sales_kpis",
    product="sales_kpis",
    version="2.1.0",
    description="Daily sales KPIs by store and product category",
    schema="schemas/sales_kpis.yaml",
    access=[
        {"workspace": "analytics", "level": "read"},
        {"workspace": "reporting", "level": "read"},
    ]
)

# Consuming in another workspace
# In SQL:
SELECT * FROM {{ ref('products.sales_kpis') }}

# In Python:
df = rat.consume("sales_kpis")
df = rat.consume("sales_kpis", version="2.x")  # Semver
```

**Product Registry Schema:**
```sql
-- Stored in shared SQLite or PostgreSQL

CREATE TABLE products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    owner_workspace TEXT NOT NULL,
    description TEXT,
    schema_json TEXT,
    storage_path TEXT,  -- s3://products/sales_kpis/v2.1.0/
    iceberg_snapshot_id BIGINT,
    created_at TIMESTAMP,
    created_by TEXT,
    UNIQUE(name, version)
);

CREATE TABLE product_access (
    id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    workspace TEXT NOT NULL,  -- '*' for all
    access_level TEXT NOT NULL,  -- 'read', 'write', 'none'
    granted_at TIMESTAMP,
    granted_by TEXT
);

CREATE TABLE product_subscriptions (
    id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    consumer_workspace TEXT NOT NULL,
    alias TEXT,  -- Local name in consumer workspace
    version_constraint TEXT,  -- '2.x', '^2.0.0', 'latest'
    subscribed_at TIMESTAMP
);
```

---

### 4. Nessie Integration

```
┌─────────────────────────────────────────────────────────────────┐
│  NESSIE CATALOG STRUCTURE                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Branches:                                                      │
│   ─────────                                                      │
│   main                        ← Production (protected)          │
│   ├── workspace/acme          ← Workspace A isolation           │
│   │   ├── dev/feature-x       ← Dev branch for feature          │
│   │   └── dev/bugfix-y        ← Another dev branch              │
│   ├── workspace/analytics     ← Workspace B isolation           │
│   └── products                ← Published data products          │
│                                                                  │
│   Tables (in each branch):                                      │
│   ────────────────────────                                       │
│   bronze.raw_sales                                               │
│   bronze.raw_inventory                                           │
│   silver.sales                                                   │
│   silver.inventory                                               │
│   gold.daily_sales_kpis                                          │
│   gold.inventory_snapshot                                        │
│                                                                  │
│   Operations:                                                    │
│   ───────────                                                    │
│   • Commit: atomic multi-table updates                          │
│   • Merge: promote dev → workspace → main                       │
│   • Cherry-pick: selective changes                              │
│   • Time-travel: query any commit                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Nessie Docker Setup:**
```yaml
# docker-compose.yml

services:
  nessie:
    image: ghcr.io/projectnessie/nessie:latest
    container_name: ratatouille-nessie
    environment:
      NESSIE_VERSION_STORE_TYPE: ROCKSDB
      QUARKUS_HTTP_PORT: 19120
    ports:
      - "19120:19120"
    volumes:
      - nessie_data:/nessie/data
    deploy:
      resources:
        limits:
          memory: 512M  # Lightweight!
```

---

### 5. DuckDB + Iceberg

```python
# src/ratatouille/engine/duckdb.py

import duckdb
from pathlib import Path

class DuckDBEngine:
    """DuckDB with Iceberg extension for Ratatouille."""

    def __init__(self, workspace: "Workspace"):
        self.workspace = workspace
        self.conn = duckdb.connect()
        self._setup_extensions()
        self._setup_iceberg()

    def _setup_extensions(self):
        """Load required extensions."""
        self.conn.execute("INSTALL iceberg; LOAD iceberg;")
        self.conn.execute("INSTALL httpfs; LOAD httpfs;")

        # Configure S3/MinIO
        self.conn.execute(f"""
            SET s3_endpoint = '{self.workspace.s3_endpoint}';
            SET s3_access_key_id = '{self.workspace.s3_key}';
            SET s3_secret_access_key = '{self.workspace.s3_secret}';
            SET s3_url_style = 'path';
        """)

    def _setup_iceberg(self):
        """Configure Iceberg catalog (Nessie)."""
        self.conn.execute(f"""
            ATTACH '{self.workspace.nessie_uri}' AS iceberg (
                TYPE ICEBERG,
                CATALOG_TYPE NESSIE,
                NESSIE_REF '{self.workspace.nessie_branch}'
            );
        """)

    def query(self, sql: str) -> "DataFrame":
        """Execute query with memory limits."""
        # Set memory limit based on profile
        max_mem = self.workspace.resources.max_memory_mb
        self.conn.execute(f"SET memory_limit = '{max_mem}MB';")

        return self.conn.execute(sql).df()

    def execute_pipeline(self, pipeline: "Pipeline"):
        """Execute a compiled pipeline."""
        sql = pipeline.compile(self.workspace)

        if pipeline.is_incremental:
            # Get watermark from last run
            watermark = self._get_watermark(pipeline.name)
            sql = sql.replace("{{ watermark }}", watermark)

        # Execute and write to Iceberg
        result = self.query(sql)
        self._write_iceberg(pipeline.target, result, pipeline.unique_key)

        # Update watermark
        if pipeline.is_incremental:
            self._update_watermark(pipeline.name, result)

        return {"rows": len(result)}
```

---

### 6. Resource Profiles

```yaml
# config/profiles/small.yaml (20GB VM - YOUR TARGET)

description: "Optimized for 20GB RAM VMs"

resources:
  # Memory limits
  max_memory_mb: 4096          # Max per pipeline
  duckdb_memory_mb: 8192       # DuckDB total

  # Processing
  chunk_size_rows: 50000       # Batch size for large tables
  max_parallel_pipelines: 2    # Concurrent pipelines

  # DuckDB settings
  duckdb:
    threads: 2
    memory_limit: "8GB"
    temp_directory: "/tmp/duckdb"

  # Nessie
  nessie:
    memory_mb: 512

  # MinIO
  minio:
    memory_mb: 1024


# config/profiles/tiny.yaml (4GB VM / Raspberry Pi)

description: "Minimal footprint for tiny VMs"

resources:
  max_memory_mb: 1024
  duckdb_memory_mb: 2048
  chunk_size_rows: 10000
  max_parallel_pipelines: 1

  duckdb:
    threads: 1
    memory_limit: "2GB"


# config/profiles/large.yaml (128GB+ VM)

description: "Full performance for large VMs"

resources:
  max_memory_mb: 32768
  duckdb_memory_mb: 65536
  chunk_size_rows: 500000
  max_parallel_pipelines: 8

  duckdb:
    threads: 8
    memory_limit: "64GB"
```

---

## 🐳 Docker Compose

```yaml
# docker-compose.yml

version: "3.8"

services:
  # ═══════════════════════════════════════════════════════════
  # Storage: MinIO (S3-compatible)
  # ═══════════════════════════════════════════════════════════
  minio:
    image: minio/minio:latest
    container_name: ratatouille-minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-ratatouille}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-ratatouille123}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    deploy:
      resources:
        limits:
          memory: ${MINIO_MEMORY:-1G}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 3

  minio-init:
    image: minio/mc:latest
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        mc alias set minio http://minio:9000 $${MINIO_ROOT_USER} $${MINIO_ROOT_PASSWORD}
        mc mb --ignore-existing minio/warehouse
        mc mb --ignore-existing minio/products
        echo "✅ Buckets ready!"

  # ═══════════════════════════════════════════════════════════
  # Catalog: Nessie (Git-like Iceberg catalog)
  # ═══════════════════════════════════════════════════════════
  nessie:
    image: ghcr.io/projectnessie/nessie:latest
    container_name: ratatouille-nessie
    environment:
      NESSIE_VERSION_STORE_TYPE: ROCKSDB
      QUARKUS_HTTP_PORT: 19120
    ports:
      - "19120:19120"
    volumes:
      - nessie_data:/nessie/data
    deploy:
      resources:
        limits:
          memory: ${NESSIE_MEMORY:-512M}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:19120/api/v2/config"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ═══════════════════════════════════════════════════════════
  # Orchestration: Dagster
  # ═══════════════════════════════════════════════════════════
  dagster:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ratatouille-dagster
    environment:
      # S3
      S3_ENDPOINT: http://minio:9000
      S3_ACCESS_KEY: ${MINIO_ROOT_USER:-ratatouille}
      S3_SECRET_KEY: ${MINIO_ROOT_PASSWORD:-ratatouille123}
      # Nessie
      NESSIE_URI: http://nessie:19120/api/v2
      # Resources
      RAT_PROFILE: ${RAT_PROFILE:-small}
    ports:
      - "3030:3000"
    volumes:
      - ./src:/app/src
      - ./workspaces:/app/workspaces
      - dagster_storage:/app/storage
    depends_on:
      minio:
        condition: service_healthy
      nessie:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: ${DAGSTER_MEMORY:-2G}
    command: dagster dev -h 0.0.0.0 -p 3000

  # ═══════════════════════════════════════════════════════════
  # Development: JupyterLab
  # ═══════════════════════════════════════════════════════════
  jupyter:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ratatouille-jupyter
    environment:
      S3_ENDPOINT: http://minio:9000
      S3_ACCESS_KEY: ${MINIO_ROOT_USER:-ratatouille}
      S3_SECRET_KEY: ${MINIO_ROOT_PASSWORD:-ratatouille123}
      NESSIE_URI: http://nessie:19120/api/v2
      JUPYTER_TOKEN: ${JUPYTER_TOKEN:-ratatouille}
      RAT_PROFILE: ${RAT_PROFILE:-small}
    ports:
      - "8889:8888"
    volumes:
      - ./src:/app/src
      - ./workspaces:/app/workspaces
    depends_on:
      minio:
        condition: service_healthy
      nessie:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: ${JUPYTER_MEMORY:-2G}
    command: >
      jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root
      --ServerApp.token=${JUPYTER_TOKEN:-ratatouille}
      --notebook-dir=/app/workspaces

networks:
  default:
    driver: bridge

volumes:
  minio_data:
  nessie_data:
  dagster_storage:
```

---

## 📋 Migration Plan

### Phase 1: Core Infrastructure ✅ COMPLETE
- [x] Set up Nessie service (docker-compose.yml)
- [x] Implement DuckDB + Iceberg integration (engine/duckdb.py)
- [x] Create workspace isolation layer (workspace/manager.py, workspace/config.py)
- [x] Build resource profiles system (resources/config.py, resources/profiles.py)

### Phase 2: Pipeline SDK ✅ COMPLETE
- [x] SQL pipeline parser with {{ ref() }}, {% if %} (pipeline/parser.py)
- [x] YAML config loader (pipeline/config.py)
- [x] Incremental processing with watermarks (pipeline/incremental.py)
- [x] Python pipeline decorators (pipeline/decorators.py)
- [x] Pipeline loader and DAG builder (pipeline/loader.py)
- [x] Pipeline executor (pipeline/executor.py)

### Phase 3: Data Products ✅ COMPLETE
- [x] Product registry with SQLite storage (products/registry.py)
- [x] Publish APIs with schema extraction (products/publish.py)
- [x] Consume APIs with version resolution (products/consume.py)
- [x] Permission system with patterns (products/permissions.py)
- [x] Semver version management with constraints (^1.0.0, ~1.2.0, etc.)

### Phase 4: Migration & Polish ✅ COMPLETE
- [x] Migrated example pipelines to new dbt-like format
- [x] CI/CD setup (GitHub Actions: lint, typecheck, unit tests, integration tests, docker)
- [x] Documentation (guides: pipelines.md, data-products.md, workspaces.md)
- [x] Unit tests for parser, products, workspace
- [x] Integration tests for DuckDB engine
- [x] Updated pyproject.toml with proper packaging

---

## ✅ Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| Memory usage (1M row merge) | OOM | < 500MB |
| Memory usage (10B row query) | N/A | < 4GB (streaming) |
| Pipeline code duplication | ~60% | < 5% |
| Time to create workspace | Manual | < 2 min |
| Schema validation | 0% | 100% |
| Lineage tracking | None | Full DAG |
| Data product creation | N/A | < 5 min |

---

## 🔗 References

- [Project Nessie](https://projectnessie.org/)
- [DuckDB Iceberg Extension](https://duckdb.org/docs/extensions/iceberg)
- [Apache Iceberg](https://iceberg.apache.org/)
- [dbt Core Concepts](https://docs.getdbt.com/docs/build/projects)

---

*"Anyone can data!" 🐀*
