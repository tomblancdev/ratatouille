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

**Catalog:** Nessie REST catalog (Git-like versioning for data)

```python
# Iceberg catalog configuration via Nessie
from pyiceberg.catalog import load_catalog

catalog = load_catalog("nessie", **{
    "type": "rest",
    "uri": "http://nessie:19120/api/v2/iceberg",
    "ref": "main",  # or "feature/branch" - syncs with Git!
    "warehouse": "s3://warehouse/",
    "s3.endpoint": "http://minio:9000",
})
```

> 📖 **See [Git-Nessie Sync](../guide/git-nessie-sync.md)** for automatic branch synchronization.

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
# 🐀 Ratatouille - Architecture Design Document

> **Status:** Draft
> **Last Updated:** 2026-01-29

---

## 1. Overview

### 1.1 Vision
*"Anyone Can Data!"* - A self-hostable, all-in-one data platform for people who refuse to pay Snowflake prices.

### 1.2 Mission
Provide a complete data platform in a single, easy-to-deploy package that handles storage, pipelines, querying, and visualization.

### 1.3 Target Users

| Persona | Description | Needs |
|---------|-------------|-------|
| **Homelab Hero** | Self-hoster, privacy-focused, technical | Full control, no vendor lock-in, runs on own hardware |
| **SMB Data Lead** | 10-50 person company, growing pains | Outgrew spreadsheets, needs structure, limited budget |

### 1.4 Design Principles

1. **All-in-One** - One platform, not 10 tools glued together
2. **Self-Hosted First** - Your data, your servers, your control
3. **Simple to Start** - 5 minutes from zero to working pipeline
4. **Scale When Needed** - Single node → cluster without rewrite

---

## 2. Requirements

### 2.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | Ingest data from APIs, databases, files | Must |
| F2 | Transform data (ETL pipelines) | Must |
| F3 | Store data in queryable format | Must |
| F4 | Query data via SQL | Must |
| F5 | Expose data via API | Must |
| F6 | Web UI for management | Must |
| F7 | Schedule and monitor pipelines | Must |
| F8 | Host data apps (Streamlit, etc.) | Should |
| F9 | Data quality checks | Should |
| F10 | User authentication | Should |

### 2.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NF1 | Data volume | 10-500 GB |
| NF2 | Deployment | Single `docker compose up` |
| NF3 | Memory footprint | < 4 GB idle |
| NF4 | Query latency | < 5s for typical analytics |
| NF5 | Startup time | < 60 seconds |

### 2.3 Out of Scope (MVP)

- Real-time streaming
- Multi-tenant SaaS
- Complex RBAC
- Distributed compute
- Sub-second latency

---

## 3. Architecture

### 3.1 High-Level Design

```
┌──────────────────────────────────────────────────────────────────┐
│                         RATATOUILLE                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      WEB UI                               │   │
│  │  (Pipeline management, monitoring, data exploration)     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌───────────────┬───────────┴───────────┬────────────────┐     │
│  │               │                       │                │     │
│  │   PIPELINES   │        API            │   DATA APPS    │     │
│  │  (ETL/ELT)    │    (REST/GraphQL)     │  (Streamlit)   │     │
│  │               │                       │                │     │
│  └───────┬───────┴───────────┬───────────┴───────┬────────┘     │
│          │                   │                   │              │
│  ┌───────┴───────────────────┴───────────────────┴───────┐      │
│  │                    QUERY ENGINE                        │      │
│  │                  (SQL interface)                       │      │
│  └────────────────────────┬──────────────────────────────┘      │
│                           │                                      │
│  ┌────────────────────────┴──────────────────────────────┐      │
│  │                      STORAGE                           │      │
│  │     ┌─────────┐    ┌─────────┐    ┌─────────┐         │      │
│  │     │ BRONZE  │───▶│ SILVER  │───▶│  GOLD   │         │      │
│  │     │  (Raw)  │    │(Cleaned)│    │(Business)│        │      │
│  │     └─────────┘    └─────────┘    └─────────┘         │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Overview

| Component | Responsibility | Candidates |
|-----------|---------------|------------|
| **Storage** | Persist data in lakehouse format | MinIO, Local FS |
| **Format** | Data file format | Parquet, Delta Lake, Iceberg |
| **Query Engine** | SQL analytics | DuckDB, ClickHouse, Polars |
| **Pipelines** | ETL orchestration | Dagster, Prefect, Hamilton |
| **API** | Data access layer | FastAPI, GraphQL |
| **UI** | Management interface | Custom, Streamlit |
| **Data Apps** | User-built apps | Streamlit, Gradio |

### 3.3 Data Flow

```
                    INGESTION
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
    ▼                   ▼                   ▼
┌───────┐          ┌─────────┐         ┌────────┐
│  API  │          │Database │         │ Files  │
│Sources│          │  CDC    │         │Uploads │
└───┬───┘          └────┬────┘         └───┬────┘
    │                   │                  │
    └───────────────────┼──────────────────┘
                        ▼
                  ┌───────────┐
                  │  LANDING  │  (Raw, as-received)
                  └─────┬─────┘
                        │
                        ▼
                  ┌───────────┐
                  │  BRONZE   │  (Structured, partitioned)
                  └─────┬─────┘
                        │ Transform & Validate
                        ▼
                  ┌───────────┐
                  │  SILVER   │  (Cleaned, deduplicated)
                  └─────┬─────┘
                        │ Aggregate & Model
                        ▼
                  ┌───────────┐
                  │   GOLD    │  (Business-ready)
                  └─────┬─────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
      ┌───────┐    ┌─────────┐   ┌─────────┐
      │  API  │    │   BI    │   │   ML    │
      │Access │    │Dashboard│   │Training │
      └───────┘    └─────────┘   └─────────┘
```

---

## 4. Technology Decisions

See [ADRs](./adr/) for detailed decision records.

| Decision | Status | ADR |
|----------|--------|-----|
| Query Engine | Pending | - |
| Storage Backend | Pending | - |
| Orchestration | Pending | - |
| API Framework | Pending | - |
| UI Approach | Pending | - |

---

## 5. Deployment

### 5.1 Single Command Start

```bash
curl -sSL https://ratatouille.dev/install | sh
# or
docker compose up -d
```

### 5.2 Container Architecture

```yaml
services:
  ratatouille:
    image: ratatouille/ratatouille:latest
    ports:
      - "3000:3000"  # Web UI
      - "8000:8000"  # API
    volumes:
      - ./data:/data
```

---

## 6. Open Questions

1. **Build vs Integrate?** - Custom components or wrap existing tools?
2. **How opinionated?** - Convention over configuration vs flexibility?
3. **Upgrade path?** - How do users upgrade without data loss?
4. **Plugin system?** - Allow community extensions?

---

## 7. References

- [Journal](./journal/) - Development notes
- [ADRs](./adr/) - Decision records
- [CLAUDE.md](../../CLAUDE.md) - Project guidelines
