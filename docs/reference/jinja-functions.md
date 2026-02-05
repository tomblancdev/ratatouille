# 🔧 Jinja Functions Reference

Template functions available in SQL pipelines.

---

## Overview

SQL pipelines support Jinja templating for:
- Referencing other tables
- Incremental processing
- Watermark tracking

```sql
SELECT * FROM {{ ref('bronze.raw_sales') }}
{% if is_incremental() %}
  WHERE updated_at > '{{ watermark("updated_at") }}'
{% endif %}
```

---

## Functions

### {{ ref('layer.table') }}

Reference another table in the pipeline.

```sql
-- Reference a single table
SELECT * FROM {{ ref('bronze.raw_sales') }}

-- Join multiple tables
SELECT s.*, p.category
FROM {{ ref('silver.sales') }} s
JOIN {{ ref('silver.products') }} p
  ON s.product_id = p.id
```

**Benefits:**
- Creates dependency in DAG
- Enables lineage tracking
- Auto-resolves table location

---

### {{ this }}

Reference the current table (for tests and freshness checks).

```sql
-- In a test
SELECT COUNT(*)
FROM {{ this }}
WHERE invalid_condition

-- In a quality check
SELECT *
FROM {{ this }}
WHERE updated_at < NOW() - INTERVAL 24 HOUR
```

---

### {% if is_incremental() %}

Conditional logic for incremental processing.

```sql
SELECT * FROM {{ ref('bronze.raw_sales') }}
{% if is_incremental() %}
  WHERE transaction_time > '{{ watermark("transaction_time") }}'
{% endif %}
```

**How it works:**
- First run: Full table load (condition is false)
- Subsequent runs: Only new data (condition is true)

---

### {{ watermark('column') }}

Get the last processed value for a column.

```sql
-- Filter to new records only
WHERE updated_at > '{{ watermark("updated_at") }}'

-- Can use with any column type
WHERE id > {{ watermark("id") }}
WHERE date >= '{{ watermark("date") }}'
```

**Watermark tracking:**
- Automatically stored per-pipeline
- Updated after successful runs
- Enables efficient incremental loads

---

## Incremental Patterns

### Time-Based Incremental

```sql
-- @materialized: incremental
-- @unique_key: txn_id

SELECT *
FROM {{ ref('bronze.raw_sales') }}
{% if is_incremental() %}
  WHERE transaction_time > '{{ watermark("transaction_time") }}'
{% endif %}
```

### ID-Based Incremental

```sql
-- @materialized: incremental
-- @unique_key: id

SELECT *
FROM {{ ref('bronze.events') }}
{% if is_incremental() %}
  WHERE id > {{ watermark("id") }}
{% endif %}
```

### Multiple Conditions

```sql
-- @materialized: incremental
-- @unique_key: [date, store_id, product_id]

SELECT *
FROM {{ ref('bronze.inventory') }}
{% if is_incremental() %}
  WHERE (
    date > '{{ watermark("date") }}'
    OR (date = '{{ watermark("date") }}' AND updated_at > '{{ watermark("updated_at") }}')
  )
{% endif %}
```

---

## Pipeline Annotations

Use SQL comments for metadata:

```sql
-- @name: silver_sales
-- @materialized: incremental
-- @unique_key: txn_id
-- @partition_by: _date
-- @owner: data-team

SELECT ...
```

### Available Annotations

| Annotation | Description | Values |
|------------|-------------|--------|
| `@name` | Pipeline identifier | `layer_tablename` |
| `@materialized` | Persistence mode | `view`, `table`, `incremental` |
| `@unique_key` | Deduplication key | Column name or `[col1, col2]` |
| `@partition_by` | Partition column | Column name |
| `@owner` | Owner/team | Email or team name |

---

## Examples

### Basic Transform

```sql
-- @name: silver_orders
-- @materialized: table

SELECT
    order_id,
    customer_id,
    order_date,
    total_amount
FROM {{ ref('bronze.raw_orders') }}
WHERE total_amount > 0
```

### Incremental with Dedup

```sql
-- @name: silver_events
-- @materialized: incremental
-- @unique_key: event_id

SELECT
    event_id,
    user_id,
    event_type,
    created_at
FROM {{ ref('bronze.raw_events') }}
{% if is_incremental() %}
  WHERE created_at > '{{ watermark("created_at") }}'
{% endif %}
```

### Join with Lookup

```sql
-- @name: silver_sales_enriched
-- @materialized: incremental
-- @unique_key: txn_id

SELECT
    s.*,
    p.product_name,
    p.category,
    c.customer_name
FROM {{ ref('bronze.raw_sales') }} s
LEFT JOIN {{ ref('silver.products') }} p
  ON s.product_id = p.product_id
LEFT JOIN {{ ref('silver.customers') }} c
  ON s.customer_id = c.customer_id
{% if is_incremental() %}
  WHERE s.transaction_time > '{{ watermark("transaction_time") }}'
{% endif %}
```

### Gold Aggregation

```sql
-- @name: gold_daily_sales
-- @materialized: table

SELECT
    DATE(transaction_time) AS date,
    product_id,
    COUNT(*) AS num_transactions,
    SUM(quantity) AS total_quantity,
    SUM(total_amount) AS revenue
FROM {{ ref('silver.sales') }}
GROUP BY DATE(transaction_time), product_id
```

---

## Testing with Jinja

### Quality Test

```sql
-- tests/quality/unique_orders.sql
-- @name: unique_order_ids
-- @mocks: mocks/orders.yaml

SELECT order_id, COUNT(*) as count
FROM {{ this }}
GROUP BY order_id
HAVING COUNT(*) > 1
```

### Unit Test

```sql
-- tests/unit/test_total_calc.sql
-- @name: test_total_calculation
-- @mocks: mocks/orders.yaml
-- @expect_count: 3

-- Just runs the pipeline with mock data
-- and checks row count
```

---

## Watermark Access in Python

```python
from ratatouille.pipeline import WatermarkTracker

tracker = WatermarkTracker()

# Get current watermark
last_value = tracker.get("silver_sales", "transaction_time")

# Set watermark manually (rare)
tracker.set("silver_sales", "transaction_time", "2024-01-15 00:00:00")
```
