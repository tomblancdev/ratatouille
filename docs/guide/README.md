# 📊 Data Engineer's Guide

> For **Data Engineers** - Building and managing data pipelines

---

## Quick Links

| I want to... | Go to... |
|--------------|----------|
| Build my first pipeline | [Getting Started](getting-started.md) |
| Set up workspaces | [Workspaces](workspaces.md) |
| Write SQL pipelines | [SQL Pipelines (dbt-style)](pipelines-sql.md) |
| Write Python pipelines | [Python Pipelines (Dagster)](pipelines-python.md) |
| Schedule pipelines | [Triggers](triggers.md) |
| Test pipelines | [Testing](testing.md) |
| Generate docs | [Documentation](documentation.md) |
| Share data across teams | [Data Products](data-products.md) |
| Fix issues | [Troubleshooting](troubleshooting.md) |

---

## Quick Start

```python
from ratatouille import run, workspace, query, tools

# Load workspace
workspace("demo")

# Run a pipeline (defined as SQL/Python files)
run("silver.sales")

# Query results
df = query("SELECT * FROM silver.sales LIMIT 10")

# Explore
tools.tables()                    # List all tables
tools.schema("silver.sales")      # Get schema
tools.preview("gold.metrics")     # Preview data
```

See [Getting Started](getting-started.md) for the full tutorial.

---

## Documentation Index

### Getting Started

- **[Getting Started](getting-started.md)** - Build your first pipeline
- **[Workspaces](workspaces.md)** - Organize projects and teams

### Building Pipelines

- **[SQL Pipelines](pipelines-sql.md)** - dbt-style YAML/SQL pipelines
- **[Python Pipelines](pipelines-python.md)** - Dagster asset pipelines

### Running & Monitoring

- **[Triggers](triggers.md)** - Sensors, schedules, webhooks
- **[Testing](testing.md)** - Quality tests and unit tests
- **[Troubleshooting](troubleshooting.md)** - Common issues and fixes

### Documentation & Sharing

- **[Documentation](documentation.md)** - Auto-generate pipeline docs
- **[Data Products](data-products.md)** - Cross-workspace data sharing

---

## File-First Architecture

Ratatouille follows a **file-first** approach like dbt:

```
workspaces/
└── my-workspace/
    ├── workspace.yaml           # Workspace config
    ├── pipelines/
    │   ├── bronze/              # Raw data ingestion
    │   │   └── sales.sql
    │   ├── silver/              # Cleaned/transformed
    │   │   └── sales.sql
    │   └── gold/                # Business-ready
    │       └── daily_kpis.sql
    └── tests/
        └── quality/             # Data quality tests
```

**Pipeline files** = SQL or Python + YAML config
**SDK** = Run pipelines, explore data
**CLI** = Same operations from terminal

---

## Medallion Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   BRONZE    │───▶│   SILVER    │───▶│    GOLD     │
│  (Raw Data) │    │  (Cleaned)  │    │ (Business)  │
└─────────────┘    └─────────────┘    └─────────────┘
```

| Layer | Purpose | Example |
|-------|---------|---------|
| **Bronze** | Raw, immutable, as-is | `pipelines/bronze/ingest.sql` |
| **Silver** | Cleaned, validated, typed | `pipelines/silver/sales.sql` |
| **Gold** | Business aggregations, KPIs | `pipelines/gold/daily_kpis.sql` |

---

## Development Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. EXPLORE               2. DEVELOP              3. DEPLOY     │
│  ─────────────────────    ──────────────────      ───────────   │
│  Jupyter notebook         Edit pipeline files     Commit & push │
│  tools.tables()           Write SQL/Python        Dagster runs  │
│  query("SELECT ...")      rat test                Monitoring    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### Pipeline Files

Define pipelines as SQL or Python files with YAML config:

```sql
-- pipelines/silver/sales.sql
SELECT
    date,
    product,
    quantity * price AS total
FROM {{ ref('bronze.sales') }}
WHERE quantity > 0
```

```yaml
# pipelines/silver/sales.yaml
name: sales
layer: silver
materialization: incremental
unique_key: [date, product]
```

### Running Pipelines

```python
from ratatouille import run

# Run a single pipeline
run("silver.sales")

# Full refresh (rebuild from scratch)
run("silver.sales", full_refresh=True)
```

Or via CLI:

```bash
rat run silver.sales
rat run silver.sales -f  # Full refresh
```

---

## Next Steps

1. **[Getting Started](getting-started.md)** - Build your first pipeline
2. **[SDK Reference](../reference/sdk.md)** - Full API documentation
3. **[Testing](testing.md)** - Add quality checks
