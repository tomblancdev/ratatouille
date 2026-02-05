# 🔄 Pipeline Development Guide

Ratatouille uses a **dbt-like** approach to data pipelines: SQL files with Jinja templating, YAML configuration, and Python for complex ingestion.

## Quick Start

Create a pipeline in your workspace:

```
workspaces/
└── my-workspace/
    └── pipelines/
        ├── bronze/
        │   └── ingest_sales.py      # Python for ingestion
        ├── silver/
        │   ├── sales.sql            # SQL transformation
        │   └── sales.yaml           # Schema & tests
        └── gold/
            ├── daily_kpis.sql
            └── daily_kpis.yaml
```

## SQL Pipelines

### Basic Structure

```sql
-- pipelines/silver/sales.sql

-- @name: silver_sales
-- @materialized: incremental
-- @unique_key: txn_id
-- @partition_by: _date
-- @owner: data-team

SELECT
    txn_id,
    store_id,
    quantity * unit_price AS total_amount,
    CAST(transaction_time AS DATE) AS _date
FROM {{ ref('bronze.raw_sales') }}
WHERE quantity > 0
{% if is_incremental() %}
  AND transaction_time > '{{ watermark("transaction_time") }}'
{% endif %}
```

### Metadata Annotations

| Annotation | Description | Values |
|------------|-------------|--------|
| `@name` | Pipeline identifier | `layer_tablename` |
| `@materialized` | How to persist | `view`, `table`, `incremental` |
| `@unique_key` | Deduplication key | Column name |
| `@partition_by` | Partition column | Column name |
| `@owner` | Owner/team | String |

### Jinja Functions

#### `{{ ref('layer.table') }}`

Reference another table in the pipeline:

```sql
SELECT * FROM {{ ref('bronze.raw_sales') }}
JOIN {{ ref('silver.products') }} ON ...
```

This creates a dependency and enables DAG building.

#### `{% if is_incremental() %}`

Conditional logic for incremental processing:

```sql
SELECT * FROM source
{% if is_incremental() %}
  WHERE updated_at > '{{ watermark("updated_at") }}'
{% endif %}
```

When run incrementally, only processes new data.

#### `{{ watermark('column') }}`

Get the last processed value for a column:

```sql
WHERE transaction_time > '{{ watermark("transaction_time") }}'
```

Watermarks are automatically tracked and updated.

## YAML Configuration

Pair each SQL file with a YAML config:

```yaml
# pipelines/silver/sales.yaml

description: |
  Cleaned and validated sales transactions.

owner: data-team@acme.com

columns:
  - name: txn_id
    type: string
    description: Unique transaction identifier
    tests:
      - not_null
      - unique

  - name: total_amount
    type: decimal(12,2)
    description: Total transaction amount
    tests:
      - not_null
      - positive

freshness:
  warn_after:
    hours: 6
  error_after:
    hours: 24

tests:
  - name: total_equals_qty_times_price
    sql: |
      SELECT COUNT(*)
      FROM {{ this }}
      WHERE ABS(total_amount - quantity * unit_price) > 0.01
    expect: 0
    severity: error
```

### Column Tests

| Test | Description |
|------|-------------|
| `not_null` | Value cannot be NULL |
| `unique` | Value must be unique |
| `positive` | Value must be > 0 |
| `accepted_values` | Value in allowed list |

### Custom Tests

Write custom SQL tests:

```yaml
tests:
  - name: no_future_dates
    sql: |
      SELECT COUNT(*) FROM {{ this }}
      WHERE sale_date > CURRENT_DATE
    expect: 0
```

## Python Pipelines

For complex ingestion or transformations:

```python
# pipelines/bronze/ingest_api.py

from ratatouille.pipeline import bronze_pipeline
import httpx

@bronze_pipeline(
    name="ingest_api_data",
    schedule="@hourly",
)
def ingest_api_data(context):
    """Ingest data from external API."""
    response = httpx.get("https://api.example.com/data")
    data = response.json()

    df = pd.DataFrame(data)
    df["_ingested_at"] = datetime.utcnow()

    context.write("bronze.api_data", df)
    context.log.info(f"Ingested {len(df)} records")
```

### Decorators

| Decorator | Use Case |
|-----------|----------|
| `@bronze_pipeline` | Raw data ingestion |
| `@silver_pipeline` | Cleaning & validation |
| `@gold_pipeline` | Business aggregations |
| `@pipeline` | Generic pipeline |

## Incremental Processing

### How It Works

1. First run: Full table load
2. Subsequent runs: Only process new data based on watermark

### Example

```sql
-- @materialized: incremental
-- @unique_key: id

SELECT * FROM source
{% if is_incremental() %}
  WHERE updated_at > '{{ watermark("updated_at") }}'
{% endif %}
```

### Watermark Tracking

Watermarks are stored per-pipeline and automatically updated after each successful run.

```python
# Manual watermark access
from ratatouille.pipeline import WatermarkTracker

tracker = WatermarkTracker()
last_value = tracker.get("silver_sales", "transaction_time")
```

## DAG & Dependencies

Ratatouille automatically builds a DAG from `{{ ref() }}` calls:

```
bronze.raw_sales
       ↓
silver.sales
       ↓
gold.daily_kpis
```

### Running Pipelines

```bash
# Run specific pipeline
rat run silver.sales

# Run with all upstream dependencies
rat run gold.daily_kpis --upstream

# Dry run (show plan without executing)
rat run gold.daily_kpis --dry-run
```

## Best Practices

### 1. Follow Medallion Architecture

- **Bronze**: Raw, immutable, append-only
- **Silver**: Cleaned, validated, deduplicated
- **Gold**: Business aggregations, KPIs

### 2. Use Incremental When Possible

For large tables, incremental processing is much more efficient:

```sql
-- Good: Incremental
-- @materialized: incremental
-- @unique_key: id

SELECT * FROM source
{% if is_incremental() %}
  WHERE updated_at > '{{ watermark("updated_at") }}'
{% endif %}
```

### 3. Document Your Pipelines

Always include:
- Clear description
- Column documentation
- Owner information
- Freshness SLAs

### 4. Add Tests

At minimum:
- `not_null` on required columns
- `unique` on primary keys
- Business logic tests

### 5. Use Consistent Naming

```
layer_domain_entity
```

Examples:
- `bronze_pos_sales`
- `silver_cleaned_orders`
- `gold_daily_revenue`
