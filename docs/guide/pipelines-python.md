# 🐍 Python Pipelines

How to create production-ready data pipelines with Dagster and Ratatouille.

---

## Overview

Pipelines in Ratatouille are built with **Dagster assets**. Each asset represents a data artifact (table, file, model) in your lakehouse.

```python
from dagster import asset
from ratatouille import run

@asset
def my_silver_data():
    result = run("silver.my_data")
    return result
```

---

## Pipeline Locations

Pipelines can live in two places:

| Location | Use Case | Auto-discovered |
|----------|----------|-----------------|
| `pipelines/` | Production pipelines | ✅ via `pipelines/__init__.py` |
| `workspaces/*/pipelines/` | User/dev pipelines | ✅ Automatic |

### Project Pipelines (`pipelines/`)

```
pipelines/
├── __init__.py           # Exports all_assets, all_sensors, etc.
├── example/
│   ├── __init__.py
│   ├── assets.py
│   └── checks.py
└── sales/
    └── __init__.py
```

### Workspace Pipelines (`workspaces/*/pipelines/`)

Just drop `.py` files here - they're auto-discovered!

```
workspaces/
└── default/
    └── pipelines/
        ├── my_pipeline.py      # Auto-loaded!
        └── another_pipeline.py
```

---

## Asset Anatomy

### Basic Asset

```python
from dagster import asset, AssetExecutionContext, MaterializeResult, MetadataValue
from ratatouille import run

@asset(
    # Grouping in Dagster UI
    group_name="my_pipeline",

    # Rich description (supports markdown)
    description="""
    ## Silver: Cleaned Sales Data

    Transforms bronze sales data with cleaning and calculations.

    ### Output
    | Column | Type |
    |--------|------|
    | date | date |
    | product | string |
    | total | decimal |
    """,

    # Shows icon in UI
    compute_kind="sql",

    # For Dagster caching
    code_version="1.0.0",
)
def my_silver(context: AssetExecutionContext) -> MaterializeResult:
    """Transform bronze to silver."""

    result = run("silver.sales")

    context.log.info(f"Pipeline completed: {result}")

    return MaterializeResult(
        metadata={
            "status": MetadataValue.text(result.get("status", "completed")),
        }
    )
```

### Asset with Dependencies

```python
@asset(
    group_name="my_pipeline",
    deps=[my_bronze],  # Depends on my_bronze
    compute_kind="sql",
)
def my_silver(context: AssetExecutionContext) -> MaterializeResult:
    """Clean and transform to silver."""

    result = run("silver.sales")

    return MaterializeResult(
        metadata={
            "status": MetadataValue.text("completed"),
        }
    )
```

### Cross-module Dependencies

```python
from dagster import AssetKey

@asset(
    deps=[AssetKey("my_bronze")],  # Reference by name
    ...
)
def my_silver():
    ...
```

---

## Asset Metadata

Rich metadata appears in Dagster UI:

```python
from dagster import MetadataValue
from ratatouille import query

@asset
def my_asset():
    result = run("silver.sales")

    # Get row count for metadata
    df = query("SELECT COUNT(*) as cnt FROM silver.sales")
    row_count = df['cnt'][0]

    return MaterializeResult(
        metadata={
            # Numbers
            "row_count": MetadataValue.int(row_count),

            # Text
            "status": MetadataValue.text("completed"),

            # JSON
            "result": MetadataValue.json(result),

            # Markdown (great for previews!)
            "preview": MetadataValue.md("| col1 | col2 |\n|---|---|"),
        }
    )
```

---

## Asset Checks (Data Quality)

Validate data after materialization.

```python
from dagster import asset_check, AssetCheckResult, AssetCheckSeverity, AssetKey
from ratatouille import query

@asset_check(
    asset=AssetKey("my_silver"),
    description="Table must have data"
)
def check_not_empty() -> AssetCheckResult:
    df = query("SELECT COUNT(*) as cnt FROM silver.sales")
    row_count = df['cnt'][0]

    return AssetCheckResult(
        passed=row_count > 0,
        metadata={"row_count": row_count},
        description=f"Found {row_count} rows"
    )


@asset_check(
    asset=AssetKey("my_silver"),
    description="No nulls in key columns"
)
def check_no_nulls() -> AssetCheckResult:
    df = query("""
        SELECT
            SUM(CASE WHEN date IS NULL THEN 1 ELSE 0 END) as null_date,
            SUM(CASE WHEN product IS NULL THEN 1 ELSE 0 END) as null_product
        FROM silver.sales
    """)

    total_nulls = df['null_date'][0] + df['null_product'][0]

    return AssetCheckResult(
        passed=total_nulls == 0,
        metadata={"null_counts": {"date": df['null_date'][0], "product": df['null_product'][0]}},
        severity=AssetCheckSeverity.ERROR if total_nulls > 0 else AssetCheckSeverity.WARN
    )
```

---

## Sensors (Event-Driven)

Trigger pipelines when new files arrive.

```python
from dagster import sensor, RunRequest, SensorEvaluationContext, DefaultSensorStatus
from ratatouille import tools

@sensor(
    job=my_pipeline_job,
    minimum_interval_seconds=60,
    default_status=DefaultSensorStatus.RUNNING,
)
def new_files_sensor(context: SensorEvaluationContext):
    """Watch for new files in landing zone."""

    files = tools.ls("landing/sales/")

    # Track which files we've seen
    last_seen = context.cursor or ""
    new_files = [f for f in files if f > last_seen]

    if new_files:
        context.update_cursor(max(new_files))
        yield RunRequest(
            run_key=f"ingest-{max(new_files)}",
            run_config={}
        )
```

---

## Jobs (Grouped Execution)

Define which assets run together.

```python
from dagster import define_asset_job, AssetSelection

# All assets in a group
my_pipeline_job = define_asset_job(
    name="my_pipeline_job",
    selection=AssetSelection.groups("my_pipeline")
)

# Specific assets
silver_only_job = define_asset_job(
    name="silver_only",
    selection=AssetSelection.assets(my_silver)
)

# Assets and downstream
with_downstream = define_asset_job(
    name="full_pipeline",
    selection=AssetSelection.assets(my_bronze).downstream()
)
```

---

## Complete Pipeline Example

### `pipelines/sales/__init__.py`

```python
"""📊 Sales Pipeline - Bronze → Silver → Gold"""

from .assets import (
    sales_bronze,
    sales_silver,
    sales_gold,
)
from .checks import all_checks
from .jobs import sales_pipeline_job

all_assets = [
    sales_bronze,
    sales_silver,
    sales_gold,
]
all_asset_checks = all_checks
all_jobs = [sales_pipeline_job]
```

### `pipelines/sales/assets.py`

```python
from dagster import asset, AssetExecutionContext, MaterializeResult, MetadataValue
from ratatouille import run, query


@asset(
    group_name="sales",
    description="Raw sales data ingestion",
    compute_kind="python",
)
def sales_bronze(context: AssetExecutionContext) -> MaterializeResult:
    """Ingest sales files to bronze layer."""

    result = run("bronze.sales")
    context.log.info(f"Bronze pipeline completed: {result}")

    return MaterializeResult(
        metadata={"status": MetadataValue.text("completed")}
    )


@asset(
    group_name="sales",
    deps=[sales_bronze],
    description="Cleaned sales with calculations",
    compute_kind="sql",
)
def sales_silver(context: AssetExecutionContext) -> MaterializeResult:
    """Transform bronze → silver with cleaning."""

    result = run("silver.sales")

    # Get row count
    df = query("SELECT COUNT(*) as cnt FROM silver.sales")

    return MaterializeResult(
        metadata={
            "row_count": MetadataValue.int(df['cnt'][0]),
        }
    )


@asset(
    group_name="sales",
    deps=[sales_silver],
    description="Daily revenue aggregations",
    compute_kind="sql",
)
def sales_gold(context: AssetExecutionContext) -> MaterializeResult:
    """Aggregate to gold layer."""

    result = run("gold.sales_summary")

    return MaterializeResult(
        metadata={"status": MetadataValue.text("completed")}
    )
```

### `pipelines/sales/checks.py`

```python
from dagster import asset_check, AssetCheckResult, AssetKey
from ratatouille import query


@asset_check(asset=AssetKey("sales_silver"))
def silver_not_empty() -> AssetCheckResult:
    df = query("SELECT COUNT(*) as cnt FROM silver.sales")
    return AssetCheckResult(
        passed=df['cnt'][0] > 0,
        metadata={"row_count": df['cnt'][0]}
    )


all_checks = [silver_not_empty]
```

### `pipelines/sales/jobs.py`

```python
from dagster import define_asset_job, AssetSelection

sales_pipeline_job = define_asset_job(
    name="sales_pipeline",
    selection=AssetSelection.groups("sales"),
    description="Run full sales pipeline: Bronze → Silver → Gold"
)
```

---

## Best Practices

### 1. Use File-First for Transforms

```python
# ✅ Good - use pipeline files for SQL logic
result = run("silver.sales")

# ❌ Avoid - embedding SQL in Python
df = query("SELECT * FROM bronze.sales WHERE ...")
```

### 2. Log Meaningfully

```python
context.log.info(f"Pipeline completed: {result}")
context.log.warning(f"Skipped {errors} files with errors")
```

### 3. Return Rich Metadata

```python
return MaterializeResult(
    metadata={
        "rows": MetadataValue.int(row_count),
        "status": MetadataValue.text("completed"),
    }
)
```

### 4. Group Related Assets

```python
@asset(group_name="sales", ...)  # All sales assets together
def sales_bronze(): ...

@asset(group_name="sales", ...)
def sales_silver(): ...
```

### 5. Version Your Code

```python
@asset(code_version="1.2.0", ...)  # Bump when logic changes
def my_asset(): ...
```

---

## Running Pipelines

### Dagster UI

1. Open http://localhost:3030
2. Go to **Assets**
3. Select assets → **Materialize**

### CLI

```bash
# Run specific pipeline
rat run silver.sales

# Run with full refresh
rat run silver.sales -f
```

### Programmatically

```python
from dagster import materialize
from my_pipeline import sales_bronze, sales_silver

result = materialize([sales_bronze, sales_silver])
```
