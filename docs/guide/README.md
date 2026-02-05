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
| Use Iceberg branches | [Dev Mode](dev-mode.md) |
| Schedule pipelines | [Triggers](triggers.md) |
| Test pipelines | [Testing](testing.md) |
| Generate docs | [Documentation](documentation.md) |
| Share data across teams | [Data Products](data-products.md) |
| Fix issues | [Troubleshooting](troubleshooting.md) |

---

## Quick Start

```python
from ratatouille import rat

# Ingest raw data
df, rows = rat.ice_ingest("landing/sales.xlsx", "bronze.sales")

# Transform with SQL
rat.transform(
    sql="SELECT *, qty * price AS total FROM {bronze.sales}",
    target="silver.sales",
    merge_keys=["id"]
)

# Read results
df = rat.df("{silver.sales}")
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
- **[Dev Mode](dev-mode.md)** - Isolated development with Iceberg branches

### Running & Monitoring

- **[Triggers](triggers.md)** - Sensors, schedules, webhooks
- **[Testing](testing.md)** - Quality tests and unit tests
- **[Troubleshooting](troubleshooting.md)** - Common issues and fixes

### Documentation & Sharing

- **[Documentation](documentation.md)** - Auto-generate pipeline docs
- **[Data Products](data-products.md)** - Cross-workspace data sharing

---

## Pipeline Approaches

### SQL-First (dbt-style)

```
pipelines/
└── silver/
    ├── sales.sql       # SQL transformation
    └── sales.yaml      # Schema & tests
```

```sql
-- @materialized: incremental
-- @unique_key: txn_id

SELECT * FROM {{ ref('bronze.raw_sales') }}
WHERE quantity > 0
{% if is_incremental() %}
  AND updated_at > '{{ watermark("updated_at") }}'
{% endif %}
```

See [SQL Pipelines](pipelines-sql.md).

### Python-First (Dagster)

```python
from dagster import asset
from ratatouille import rat

@asset(group_name="sales", deps=[bronze_sales])
def silver_sales(context):
    result = rat.transform(
        sql="SELECT * FROM {bronze.sales} WHERE qty > 0",
        target="silver.sales",
        merge_keys=["id"]
    )
    return result
```

See [Python Pipelines](pipelines-python.md).

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
| **Bronze** | Raw, immutable, as-is | `rat.ice_ingest(...)` |
| **Silver** | Cleaned, validated, typed | `rat.transform(...)` |
| **Gold** | Business aggregations, KPIs | `rat.transform(...)` |

---

## Development Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. EXPLORE               2. DEVELOP              3. DEPLOY     │
│  ─────────────────────    ──────────────────      ───────────   │
│  Jupyter notebook         Dev branch              Merge to main │
│  rat.query()              rat.dev_start()         rat.dev_merge()│
│  rat.df()                 rat.transform()         Dagster runs   │
│                           rat.test()              Monitoring     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### Iceberg Tables

All data stored in Apache Iceberg tables:
- ✅ ACID transactions
- ✅ Time travel
- ✅ Schema evolution
- ✅ Branching (dev mode)

### Merge Keys

Use merge keys for idempotent pipelines:

```python
rat.transform(
    sql="SELECT * FROM {bronze.sales}",
    target="silver.sales",
    merge_keys=["date", "product_id"]  # Upsert on these columns
)
```

### Placeholder Syntax

Reference tables with `{namespace.table}`:

```python
rat.query("SELECT * FROM {silver.sales} WHERE total > 100")
```

---

## Next Steps

1. **[Getting Started](getting-started.md)** - Build your first pipeline
2. **[SDK Reference](../reference/sdk.md)** - Full API documentation
3. **[Testing](testing.md)** - Add quality checks
