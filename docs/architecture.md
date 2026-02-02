# 🏗️ Architecture

Deep dive into Ratatouille's technical architecture.

---

## Overview

Ratatouille follows a **Medallion Lakehouse Architecture** with three data layers:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA LAKEHOUSE                                │
│                                                                         │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐            │
│   │   BRONZE    │      │   SILVER    │      │    GOLD     │            │
│   │  (Raw Data) │ ───▶ │  (Cleaned)  │ ───▶ │ (Business)  │            │
│   │             │      │             │      │             │            │
│   │ • Immutable │      │ • Validated │      │ • Aggregated│            │
│   │ • As-is     │      │ • Dedupe'd  │      │ • KPIs      │            │
│   │ • All data  │      │ • Typed     │      │ • Joined    │            │
│   └─────────────┘      └─────────────┘      └─────────────┘            │
│         │                    │                    │                     │
│         └────────────────────┴────────────────────┘                     │
│                              │                                          │
│                    ┌─────────▼─────────┐                               │
│                    │  Apache Iceberg   │                               │
│                    │   (Table Format)  │                               │
│                    └─────────┬─────────┘                               │
│                              │                                          │
│                    ┌─────────▼─────────┐                               │
│                    │      MinIO        │                               │
│                    │ (S3-Compatible)   │                               │
│                    │  Parquet Files    │                               │
│                    └───────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. MinIO (Object Storage)

**Role:** S3-compatible object storage for all data files.

```
s3://
├── landing/          # Raw incoming files (Excel, CSV, etc.)
├── bronze/           # (Reserved for future use)
├── silver/           # (Reserved for future use)
├── gold/             # (Reserved for future use)
└── warehouse/        # Iceberg table data (Parquet files)
    ├── bronze/
    │   └── table_name/
    │       ├── metadata/
    │       └── data/*.parquet
    ├── silver/
    └── gold/
```

**Configuration:**
```yaml
# docker-compose.yml
minio:
  image: minio/minio:latest
  ports:
    - "9000:9000"   # S3 API
    - "9001:9001"   # Web Console
  environment:
    MINIO_ROOT_USER: ratatouille
    MINIO_ROOT_PASSWORD: ratatouille123
```

---

### 2. Apache Iceberg (Table Format)

**Role:** Table format providing ACID transactions, time travel, and schema evolution.

**Why Iceberg over raw Parquet?**
- ✅ **ACID transactions** - No partial writes
- ✅ **Time travel** - Query historical data
- ✅ **Schema evolution** - Add/rename columns safely
- ✅ **Partition evolution** - Change partitioning without rewriting
- ✅ **Hidden partitioning** - No partition columns in queries

**Catalog:** SQLite-based catalog (no external service needed)

```python
# Iceberg catalog configuration
catalog = SqlCatalog(
    "ratatouille",
    uri="sqlite:////app/workspaces/.iceberg/catalog.db",
    warehouse="s3://warehouse/",
    s3.endpoint="http://minio:9000",
)
```

**Table Structure:**
```
s3://warehouse/bronze/sales/
├── metadata/
│   ├── v1.metadata.json
│   ├── v2.metadata.json      # Schema/partition changes
│   └── snap-123456.avro      # Snapshot manifest
└── data/
    ├── 00001-abc.parquet
    ├── 00002-def.parquet     # Data files
    └── 00003-ghi.parquet
```

---

### 3. ClickHouse (Query Engine)

**Role:** Fast OLAP analytics engine for querying lakehouse data.

**Why ClickHouse?**
- ⚡ **Sub-second queries** on millions of rows
- 📊 **Native BI support** - ODBC/JDBC for Power BI, Tableau
- 🔗 **S3 integration** - Query Parquet files directly
- 💾 **Optional materialization** - Create tables for ultra-fast access

**Query Patterns:**

```sql
-- Direct S3 query (federated)
SELECT * FROM s3(
    'http://minio:9000/warehouse/bronze/sales/data/*.parquet',
    'ratatouille', 'ratatouille123', 'Parquet'
)

-- Materialized table (faster, but needs refresh)
CREATE TABLE gold_sales
ENGINE = MergeTree()
ORDER BY date
AS SELECT * FROM s3(...)
```

**Configuration:**
```yaml
# docker-compose.yml
clickhouse:
  image: clickhouse/clickhouse-server:latest
  ports:
    - "8123:8123"   # HTTP API (Power BI, REST)
    - "9440:9000"   # Native protocol
```

---

### 4. Dagster (Orchestration)

**Role:** Pipeline orchestration, scheduling, and monitoring.

**Key Concepts:**

| Concept | Description |
|---------|-------------|
| **Asset** | A data artifact (table, file, model) |
| **Job** | A selection of assets to run together |
| **Sensor** | Triggers jobs based on events (new files, time) |
| **Asset Check** | Data quality validation |

**Asset Example:**
```python
@asset(
    group_name="my_parser",
    deps=[my_bronze],          # Dependency
    compute_kind="sql",         # Icon in UI
)
def my_silver(context):
    result = rat.transform(...)
    return MaterializeResult(metadata={...})
```

**File Structure:**
```
pipelines/
├── __init__.py           # Exports all_assets, all_sensors, etc.
└── example/
    ├── __init__.py       # Exports my_bronze, my_silver
    ├── assets.py         # Asset definitions
    └── checks.py         # Quality checks
```

---

### 5. Jupyter Lab (Development)

**Role:** Interactive development environment with LSP and linting.

**Features:**
- 🔧 **Language Server Protocol (LSP)** - Autocomplete, go-to-definition
- 📝 **Ruff Linting** - Fast Python linting
- 📁 **Workspace mount** - Edit files that persist

**Access:**
- URL: http://localhost:8889
- Token: `ratatouille`
- Notebook directory: `/app/workspaces`

---

## Data Flow

### Ingestion Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Source File  │     │   Parser     │     │   Iceberg    │
│  (Excel/CSV) │ ──▶ │ (Transform)  │ ──▶ │   (Bronze)   │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │
       │    rat.ice_ingest("landing/...",       │
       │        "bronze.table", parser=my_parser)   │
       │                                         │
       ▼                                         ▼
 ┌───────────┐                          ┌──────────────┐
 │ MinIO     │                          │ File Tracking│
 │ landing/  │                          │ (Registry)   │
 └───────────┘                          └──────────────┘
```

### Transform Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Bronze     │     │  ClickHouse  │     │   Silver     │
│  (Iceberg)   │ ──▶ │  (SQL Query) │ ──▶ │  (Iceberg)   │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │
       │    rat.transform(                       │
       │        sql="SELECT ... FROM {bronze.x}",│
       │        target="silver.y",               │
       │        merge_keys=[...])                │
       │                                         │
       ▼                                         ▼
   Read via                              Write via
   s3() function                         PyIceberg
```

---

## Service Communication

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network                           │
│                                                             │
│  ┌─────────────┐         ┌─────────────┐                   │
│  │   Jupyter   │ ──────▶ │  ClickHouse │                   │
│  │  :8888      │         │   :8123     │                   │
│  └──────┬──────┘         └──────┬──────┘                   │
│         │                       │                           │
│         │ S3 API                │ S3 API                    │
│         ▼                       ▼                           │
│  ┌─────────────────────────────────────┐                   │
│  │              MinIO                   │                   │
│  │              :9000                   │                   │
│  └─────────────────────────────────────┘                   │
│         ▲                                                   │
│         │                                                   │
│  ┌──────┴──────┐                                           │
│  │   Dagster   │                                           │
│  │   :3000     │                                           │
│  └─────────────┘                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
    localhost:     localhost:     localhost:     localhost:
       8889           8123           3030         9000/9001
     (Jupyter)    (ClickHouse)    (Dagster)       (MinIO)
```

**Internal hostnames:**
- `minio:9000` - MinIO S3 API
- `clickhouse:8123` - ClickHouse HTTP
- Services discover each other by container name

---

## Workspace Auto-Discovery

Pipelines in `workspaces/*/pipelines/*.py` are automatically loaded:

```python
# ratatouille/discovery.py

def discover_workspace_assets():
    # Scan: workspaces/*/pipelines/*.py
    for file in glob("workspaces/*/pipelines/*.py"):
        module = load_module(file)
        for obj in dir(module):
            if isinstance(obj, AssetsDefinition):
                yield obj
```

**Conventions:**
1. Place `.py` files in `workspaces/<name>/pipelines/`
2. Use `@asset` decorator from Dagster
3. Dagster auto-discovers on startup

---

## File Tracking (Production)

For production ingestion, file tracking prevents re-processing:

```python
# Enable tracking
df, stats = rat.ice_ingest_batch(
    "landing/sales/",
    "bronze.sales",
    skip_existing=True  # ← Check registry before ingesting
)
```

**Registry table:** `bronze._file_registry`

| Column | Description |
|--------|-------------|
| `file_path` | S3 path of ingested file |
| `file_hash` | MD5 hash of file contents |
| `target_table` | Destination Iceberg table |
| `rows_ingested` | Number of rows written |
| `ingested_at` | Timestamp |
| `status` | success / failed / skipped |

---

## Security Considerations

⚠️ **Default credentials are for development only!**

| Service | Default User | Default Password |
|---------|--------------|------------------|
| MinIO | `ratatouille` | `ratatouille123` |
| ClickHouse | `ratatouille` | `ratatouille123` |
| Jupyter | - | Token: `ratatouille` |

For production:
1. Change all passwords in `docker-compose.yml`
2. Use secrets management (Docker secrets, Vault)
3. Enable TLS/HTTPS
4. Restrict network access

---

## Scaling Considerations

### Current: Single Node

```
┌──────────────────────────────────┐
│         Your Machine             │
│                                  │
│  ┌────────┐ ┌────────┐ ┌───────┐│
│  │ MinIO  │ │ Click  │ │Dagster││
│  │        │ │ House  │ │       ││
│  └────────┘ └────────┘ └───────┘│
└──────────────────────────────────┘
```

### Future: Kubernetes (K3s)

Same container specs work with K3s/Kubernetes:

```yaml
# Convert docker-compose.yml → k8s manifests
# Podman pod specs are K8s-compatible!

apiVersion: apps/v1
kind: Deployment
metadata:
  name: ratatouille-clickhouse
spec:
  replicas: 1  # Scale to 3 for HA
  ...
```

**Scale-out path:**
1. MinIO → MinIO Cluster (or real S3)
2. ClickHouse → ClickHouse Cluster
3. Dagster → Dagster Cloud or K8s deployment
