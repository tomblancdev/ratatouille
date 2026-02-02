# 🔧 Building Pipelines

How to create production-ready data pipelines with Dagster and Ratatouille.

---

## Overview

Pipelines in Ratatouille are built with **Dagster assets**. Each asset represents a data artifact (table, file, model) in your lakehouse.

```python
from dagster import asset
from ratatouille import rat

@asset
def my_bronze_data():
    df, rows = rat.ice_ingest("landing/data.xlsx", "bronze.my_data")
    return rows
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
├── bk/
│   └── __init__.py
└── demo/
    └── __init__.py
```

**`pipelines/__init__.py`:**
```python
from .example import all_assets as example_assets, all_checks as example_checks
from .bk import all_assets as bk_assets

all_assets = [*example_assets, *bk_assets]
all_sensors = []
all_asset_checks = [*example_checks]
all_jobs = []
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
from ratatouille import rat

@asset(
    # Grouping in Dagster UI
    group_name="my_pipeline",

    # Rich description (supports markdown)
    description="""
    ## Bronze: Raw Sales Data

    Ingests Excel files from landing zone.

    ### Schema
    | Column | Type |
    |--------|------|
    | date | datetime |
    | product | string |
    """,

    # Shows icon in UI
    compute_kind="python",

    # For Dagster caching
    code_version="1.0.0",
)
def my_bronze(context: AssetExecutionContext) -> MaterializeResult:
    """Ingest raw data to bronze layer."""

    df, stats = rat.ice_ingest_batch(
        "landing/sales/",
        "bronze.sales",
        skip_existing=True,
    )

    context.log.info(f"Ingested {stats['rows']} rows")

    return MaterializeResult(
        metadata={
            "rows": MetadataValue.int(stats["rows"]),
            "files": MetadataValue.int(stats["files"]),
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

    result = rat.transform(
        sql="""
            SELECT
                toDate(date) AS date,
                product,
                toDecimal64(price, 2) AS price,
                toInt32(quantity) AS quantity,
                price * quantity AS total
            FROM {bronze.sales}
            WHERE quantity > 0
        """,
        target="silver.sales",
        merge_keys=["date", "product"]
    )

    return MaterializeResult(
        metadata={
            "inserted": MetadataValue.int(result.get("inserted", 0)),
            "updated": MetadataValue.int(result.get("updated", 0)),
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

return MaterializeResult(
    metadata={
        # Numbers
        "row_count": MetadataValue.int(1000),
        "success_rate": MetadataValue.float(0.95),

        # Text
        "status": MetadataValue.text("completed"),

        # Paths
        "output_path": MetadataValue.path("s3://gold/output.parquet"),

        # JSON
        "stats": MetadataValue.json({"a": 1, "b": 2}),

        # Markdown (great for previews!)
        "preview": MetadataValue.md(df.head().to_markdown()),

        # URLs
        "dashboard": MetadataValue.url("http://grafana/d/123"),
    }
)
```

---

## Asset Checks (Data Quality)

Validate data after materialization.

```python
from dagster import asset_check, AssetCheckResult, AssetCheckSeverity, AssetKey

@asset_check(
    asset=AssetKey("my_silver"),
    description="Table must have data"
)
def check_not_empty() -> AssetCheckResult:
    df = rat.ice_read("silver.sales")

    return AssetCheckResult(
        passed=len(df) > 0,
        metadata={"row_count": len(df)},
        description=f"Found {len(df)} rows"
    )


@asset_check(
    asset=AssetKey("my_silver"),
    description="No nulls in key columns"
)
def check_no_nulls() -> AssetCheckResult:
    df = rat.ice_read("silver.sales")

    required = ["date", "product"]
    nulls = {col: int(df[col].isna().sum()) for col in required}
    total_nulls = sum(nulls.values())

    return AssetCheckResult(
        passed=total_nulls == 0,
        metadata={"null_counts": nulls},
        severity=AssetCheckSeverity.ERROR if total_nulls > 0 else AssetCheckSeverity.WARN
    )


@asset_check(
    asset=AssetKey("my_silver"),
    description="Values must be positive"
)
def check_positive_values() -> AssetCheckResult:
    df = rat.ice_read("silver.sales")

    issues = []
    if (df["quantity"] < 0).any():
        issues.append("negative quantities")
    if (df["price"] < 0).any():
        issues.append("negative prices")

    return AssetCheckResult(
        passed=len(issues) == 0,
        metadata={"issues": issues}
    )
```

---

## Sensors (Event-Driven)

Trigger pipelines when new files arrive.

```python
from dagster import sensor, RunRequest, SensorEvaluationContext, DefaultSensorStatus

@sensor(
    job=my_pipeline_job,
    minimum_interval_seconds=60,
    default_status=DefaultSensorStatus.RUNNING,
)
def new_files_sensor(context: SensorEvaluationContext):
    """Watch for new files in landing zone."""

    files = rat.ls("landing/sales/")

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
bronze_only_job = define_asset_job(
    name="bronze_only",
    selection=AssetSelection.assets(my_bronze)
)

# Assets and downstream
with_downstream = define_asset_job(
    name="full_pipeline",
    selection=AssetSelection.assets(my_bronze).downstream()
)
```

---

## Complete Pipeline Example

Here's a full production pipeline structure:

### `pipelines/sales/__init__.py`

```python
"""📊 Sales Pipeline - Landing → Bronze → Silver → Gold"""

from .assets import (
    sales_bronze,
    sales_silver,
    sales_gold_by_product,
    sales_gold_by_region,
)
from .checks import all_checks
from .sensors import landing_sensor
from .jobs import sales_pipeline_job

all_assets = [
    sales_bronze,
    sales_silver,
    sales_gold_by_product,
    sales_gold_by_region,
]
all_sensors = [landing_sensor]
all_asset_checks = all_checks
all_jobs = [sales_pipeline_job]
```

### `pipelines/sales/assets.py`

```python
from dagster import asset, AssetExecutionContext, MaterializeResult, MetadataValue
from ratatouille import rat


@asset(
    group_name="sales",
    description="Raw sales data from Excel exports",
    compute_kind="python",
    code_version="1.0.0",
)
def sales_bronze(context: AssetExecutionContext) -> MaterializeResult:
    """Ingest sales files to bronze layer."""

    df, stats = rat.ice_ingest_batch(
        "landing/sales/",
        "bronze.sales",
        parser="sales_excel",
        skip_existing=True,
    )

    context.log.info(f"Files: {stats['files']}, Rows: {stats['rows']}")

    return MaterializeResult(
        metadata={
            "files": MetadataValue.int(stats["files"]),
            "rows": MetadataValue.int(stats["rows"]),
            "skipped": MetadataValue.int(stats["already_ingested"]),
        }
    )


@asset(
    group_name="sales",
    deps=[sales_bronze],
    description="Cleaned sales with calculations",
    compute_kind="sql",
)
def sales_silver(context: AssetExecutionContext) -> MaterializeResult:
    """Transform bronze → silver with cleaning and enrichment."""

    result = rat.transform(
        sql="""
            SELECT
                toDate(sale_date) AS date,
                toString(region) AS region,
                toString(product_id) AS product_id,
                toInt32(quantity) AS quantity,
                toDecimal64(unit_price, 2) AS unit_price,
                toDecimal64(quantity * unit_price, 2) AS total,
                toDecimal64(discount, 2) AS discount,
                toDecimal64((quantity * unit_price) - discount, 2) AS net_total
            FROM {bronze.sales}
            WHERE quantity > 0
              AND unit_price > 0
        """,
        target="silver.sales",
        merge_keys=["date", "region", "product_id"],
    )

    return MaterializeResult(
        metadata={
            "inserted": MetadataValue.int(result.get("inserted", 0)),
            "updated": MetadataValue.int(result.get("updated", 0)),
        }
    )


@asset(
    group_name="sales",
    deps=[sales_silver],
    description="Daily revenue by product",
    compute_kind="sql",
)
def sales_gold_by_product(context: AssetExecutionContext) -> MaterializeResult:
    """Aggregate sales by product."""

    result = rat.transform(
        sql="""
            SELECT
                date,
                product_id,
                SUM(quantity) AS total_quantity,
                SUM(net_total) AS revenue,
                COUNT(*) AS transaction_count
            FROM {silver.sales}
            GROUP BY date, product_id
        """,
        target="gold.sales_by_product",
        merge_keys=["date", "product_id"],
    )

    # Also materialize in ClickHouse for BI
    rat.materialize(
        "gold_sales_by_product",
        "warehouse/gold/sales_by_product/data/*.parquet",
        order_by="date, product_id"
    )

    return MaterializeResult(
        metadata={"rows": MetadataValue.int(result.get("rows", 0))}
    )


@asset(
    group_name="sales",
    deps=[sales_silver],
    description="Daily revenue by region",
    compute_kind="sql",
)
def sales_gold_by_region(context: AssetExecutionContext) -> MaterializeResult:
    """Aggregate sales by region."""

    result = rat.transform(
        sql="""
            SELECT
                date,
                region,
                SUM(quantity) AS total_quantity,
                SUM(net_total) AS revenue,
                SUM(discount) AS total_discount
            FROM {silver.sales}
            GROUP BY date, region
        """,
        target="gold.sales_by_region",
        merge_keys=["date", "region"],
    )

    return MaterializeResult(
        metadata={"rows": MetadataValue.int(result.get("rows", 0))}
    )
```

### `pipelines/sales/checks.py`

```python
from dagster import asset_check, AssetCheckResult, AssetKey
from ratatouille import rat


@asset_check(asset=AssetKey("sales_silver"))
def silver_not_empty() -> AssetCheckResult:
    df = rat.ice_read("silver.sales")
    return AssetCheckResult(
        passed=len(df) > 0,
        metadata={"row_count": len(df)}
    )


@asset_check(asset=AssetKey("sales_silver"))
def silver_no_negative_totals() -> AssetCheckResult:
    df = rat.ice_read("silver.sales")
    negatives = (df["net_total"] < 0).sum()
    return AssetCheckResult(
        passed=negatives == 0,
        metadata={"negative_count": int(negatives)}
    )


all_checks = [silver_not_empty, silver_no_negative_totals]
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

## Custom Parsers

For messy file formats, create parsers:

### `src/ratatouille/parsers/sales.py`

```python
from io import BytesIO
from datetime import datetime
import pandas as pd


def parse_sales_excel(data: BytesIO, filename: str) -> pd.DataFrame:
    """Parse messy sales Excel export.

    Input format:
    - Row 0-4: Header junk
    - Row 5: Column names
    - Row 6+: Data
    """
    df = pd.read_excel(data, skiprows=5)

    # Rename columns
    df = df.rename(columns={
        "Sale Date": "sale_date",
        "Region Code": "region",
        "Product SKU": "product_id",
        "Qty": "quantity",
        "Price": "unit_price",
        "Disc": "discount",
    })

    # Add metadata
    df["_source_file"] = filename
    df["_ingested_at"] = datetime.utcnow()

    return df
```

### Register in `src/ratatouille/parsers/__init__.py`

```python
from .example import parse_sales
from .sales import parse_sales_excel

PARSERS = {
    "my_parser": parse_sales,
    "sales_excel": parse_sales_excel,  # Add here
}
```

---

## Best Practices

### 1. Use Merge Keys for Idempotency

```python
# ✅ Good - idempotent, can re-run safely
rat.transform(sql, target="silver.x", merge_keys=["id", "date"])

# ❌ Bad - duplicates data on re-run
rat.transform(sql, target="silver.x", mode="append")
```

### 2. Track File Ingestion

```python
# ✅ Production - skip already processed files
rat.ice_ingest_batch(..., skip_existing=True)

# ❌ Dev only - re-processes everything
rat.ice_ingest_batch(..., skip_existing=False)
```

### 3. Log Meaningfully

```python
context.log.info(f"Ingested {rows} rows from {files} files")
context.log.warning(f"Skipped {errors} files with errors")
```

### 4. Return Rich Metadata

```python
return MaterializeResult(
    metadata={
        "rows": MetadataValue.int(len(df)),
        "preview": MetadataValue.md(df.head().to_markdown()),  # Shows in UI!
    }
)
```

### 5. Group Related Assets

```python
@asset(group_name="sales", ...)  # All sales assets together
def sales_bronze(): ...

@asset(group_name="sales", ...)
def sales_silver(): ...
```

### 6. Version Your Code

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
# All assets
make run

# Specific asset
docker compose exec dagster dagster asset materialize --select "sales_bronze"

# Asset and downstream
docker compose exec dagster dagster asset materialize --select "sales_bronze+"
```

### Programmatically

```python
from dagster import materialize
from my_pipeline import sales_bronze, sales_silver

result = materialize([sales_bronze, sales_silver])
```
