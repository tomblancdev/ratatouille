# 🐀 Ratatouille Documentation

> *"Anyone Can Data!"* - A self-hostable, lightweight data platform for people who refuse to pay Snowflake prices.

---

## 📚 Documentation Index

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Quick setup, first pipeline in 5 minutes |
| [Architecture](architecture.md) | System design, tech stack, data flow |
| [SDK Reference](sdk-reference.md) | Complete API reference for `rat.*` |
| [Building Pipelines](pipelines.md) | How to create Dagster assets & jobs |
| [Dev Mode](dev-mode.md) | Iceberg branches for isolated development |
| [Operations](operations.md) | Running, monitoring, troubleshooting |

---

## 🎯 What is Ratatouille?

Ratatouille is a **self-hosted data platform** that provides:

- 🏠 **Medallion Lakehouse** - Bronze → Silver → Gold architecture with Apache Iceberg
- ⚡ **Fast Analytics** - ClickHouse for sub-second OLAP queries
- 📊 **Orchestration** - Dagster for pipeline management and monitoring
- 🔬 **Interactive Development** - Jupyter Lab with LSP and linting
- 📦 **S3-Compatible Storage** - MinIO for object storage

All running on your machine with a single `make up` command.

---

## 🏗️ Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Data Files                          │
│              (Excel, CSV, JSON, Parquet, APIs)                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     LANDING ZONE (MinIO)                         │
│                    s3://landing/your_data/                       │
└──────────────────────────┬───────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          │          RATATOUILLE SDK        │
          │     from ratatouille import rat │
          └────────────────┬────────────────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    │                      │                      │
    ▼                      ▼                      ▼
┌────────┐           ┌────────┐            ┌────────┐
│ BRONZE │    ───▶   │ SILVER │    ───▶    │  GOLD  │
│  Raw   │           │ Clean  │            │Business│
│Iceberg │           │Iceberg │            │Iceberg │
└────────┘           └────────┘            └────────┘
                                                │
                           ┌────────────────────┘
                           │
                           ▼
              ┌───────────────────────┐
              │      CLICKHOUSE       │
              │   Materialized Views  │
              │   for BI Dashboards   │
              └───────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
        ┌──────────┐             ┌──────────┐
        │ Power BI │             │ Grafana  │
        │ Tableau  │             │  Metabase│
        │   etc.   │             │   etc.   │
        └──────────┘             └──────────┘
```

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Storage** | MinIO | S3-compatible object storage |
| **Lakehouse** | Apache Iceberg | Table format with time travel, ACID, branches |
| **Query Engine** | ClickHouse | Fast OLAP analytics |
| **Transforms** | Ibis | Python syntax → ClickHouse SQL |
| **Orchestration** | Dagster | Pipeline management & scheduling |
| **Development** | Jupyter Lab | Interactive notebooks with LSP |
| **SDK** | Python | Unified data operations API |

---

## 🚀 Quick Start

```bash
# Clone and start
cd ratatouille
make up

# Access UIs
# Dagster:    http://localhost:3030
# Jupyter:    http://localhost:8889 (token: ratatouille)
# MinIO:      http://localhost:9001 (ratatouille/ratatouille123)
# ClickHouse: http://localhost:8123
```

In Jupyter:

```python
from ratatouille import rat
from ibis import _

# Ingest a file to bronze layer
df, rows = rat.ice_ingest("landing/data.xlsx", "bronze.my_table")

# Transform with SQL
rat.transform(
    sql="SELECT *, price * qty AS total FROM {bronze.my_table}",
    target="silver.my_table",
    merge_keys=["id"]
)

# Or transform with Python (Ibis) - same performance!
(rat.t("bronze.my_table")
    .filter(_.qty > 0)
    .mutate(total=_.price * _.qty)
    .to_iceberg("silver.my_table", merge_keys=["id"]))

# Read the result
df = rat.df("{silver.my_table}")
```

See [Getting Started](getting-started.md) for the full tutorial.

---

## 📁 Project Structure

```
ratatouille/
├── docker-compose.yml      # Platform services
├── Makefile                 # make up/down/logs/etc
├── Dockerfile               # App container
│
├── src/ratatouille/         # Core SDK
│   ├── sdk.py               # Main API (rat.*)
│   ├── core/                # Storage, Iceberg, utilities
│   ├── parsers/             # File format parsers
│   ├── pipelines/           # Demo pipelines
│   ├── discovery.py         # Workspace auto-loader
│   └── definitions.py       # Dagster config
│
├── pipelines/               # Production pipelines (add yours here!)
│   └── __init__.py          # Pipeline exports
│
├── workspaces/              # User workspace area
│   └── default/
│       ├── pipelines/       # Your custom pipelines
│       └── notebooks/       # Your Jupyter notebooks
│
└── docs/                    # This documentation
```

---

## 🐀 Philosophy

**Why "Ratatouille"?**

Like Remy the rat proving that "anyone can cook", this project proves that **anyone can build enterprise-grade data pipelines** without enterprise budgets.

**Core Principles:**

1. **💸 Low Cost** - Run on a single machine, scale when needed
2. **🦭 Container-First** - Everything in Docker/Podman, nothing installed on host
3. **📦 Batteries Included** - SDK, UI, notebooks all pre-configured
4. **🎯 OLAP-Focused** - Optimized for analytics, not transactions

---

## 📖 Next Steps

1. **[Getting Started](getting-started.md)** - Setup and first pipeline
2. **[SDK Reference](sdk-reference.md)** - Learn all `rat.*` methods
3. **[Building Pipelines](pipelines.md)** - Production-ready Dagster assets
