# 📋 Pipeline Config YAML Schema

Complete reference for pipeline `config.yaml` files.

---

## Basic Structure

```yaml
# config.yaml
description: |
  Brief description of what this pipeline does.

owner:
  team: data-platform
  email: team@company.com
  slack: "#data-alerts"

columns:
  - name: column_name
    type: string
    description: Column description
    pii: false
    tests: [not_null]

freshness:
  warn_after:
    hours: 6
  error_after:
    hours: 24

triggers:
  - type: schedule
    cron: daily

documentation:
  tags: [sales, daily]
  rules:
    - name: rule_name
      description: Rule description
      sql: "expression > 0"

tests:
  - name: custom_test
    sql: |
      SELECT COUNT(*) FROM {{ this }}
      WHERE invalid_condition
    expect: 0
```

---

## Root Fields

### description

Required. Minimum 50 characters for documentation validation.

```yaml
description: |
  Transforms raw POS transactions into cleaned sales records.
  Filters invalid transactions and calculates totals.
```

### owner

Contact information for the pipeline owner.

```yaml
# Simple format
owner: team@company.com

# Extended format
owner:
  team: data-platform
  email: team@company.com
  slack: "#data-alerts"
```

---

## Columns

Define schema with validation:

```yaml
columns:
  - name: txn_id
    type: string
    description: Unique transaction identifier
    pii: false
    example: "T00123"
    tests:
      - not_null
      - unique

  - name: customer_id
    type: string
    description: Customer identifier
    pii: true
    pii_type: customer_id
```

### Column Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Column name |
| `type` | Yes | Data type |
| `description` | No | Human description |
| `pii` | Yes | `true` or `false` |
| `pii_type` | No | PII classification |
| `example` | No | Example value |
| `tests` | No | List of tests |

### Column Types

```yaml
type: string
type: int
type: bigint
type: float
type: double
type: decimal(12,2)
type: boolean
type: date
type: timestamp
type: array<string>
type: map<string, int>
```

### Column Tests

| Test | Description |
|------|-------------|
| `not_null` | Value cannot be NULL |
| `unique` | Value must be unique |
| `positive` | Value > 0 |
| `accepted_values` | Value in allowed list |

```yaml
tests:
  - not_null
  - unique
  - positive
  - accepted_values: [A, B, C]
```

---

## Freshness

Define data freshness SLAs:

```yaml
freshness:
  warn_after:
    hours: 6
    # or: minutes: 30
    # or: days: 1
  error_after:
    hours: 24
```

---

## Triggers

Pipeline execution triggers:

### Schedule

```yaml
triggers:
  - type: schedule
    cron: daily        # Preset
    timezone: UTC

  - type: schedule
    cron: "0 6 * * *"  # Custom cron
```

### S3 Sensor

```yaml
triggers:
  - type: s3_sensor
    path: bronze/sales/
    interval: 60
    pattern: "*.parquet"
```

### Freshness-Based

```yaml
triggers:
  - type: freshness
    # Uses freshness config above
```

---

## Documentation

### Tags

```yaml
documentation:
  tags: [sales, finance, daily, critical]
```

### Business Rules

```yaml
documentation:
  rules:
    - name: positive_quantities
      description: Quantities must be greater than zero
      sql: "quantity > 0"

    - name: valid_total
      description: Total must equal quantity × unit_price
      sql: "ABS(total_amount - quantity * unit_price) <= 0.01"
```

---

## Custom Tests

SQL-based tests:

```yaml
tests:
  - name: total_equals_qty_times_price
    sql: |
      SELECT COUNT(*)
      FROM {{ this }}
      WHERE ABS(total_amount - quantity * unit_price) > 0.01
    expect: 0
    severity: error  # or: warn
```

---

## Full Example

```yaml
# config.yaml - Silver Sales Pipeline

description: |
  Transforms raw POS transactions into cleaned sales records.

  Key transformations:
  - Filters invalid records (quantity <= 0)
  - Standardizes text fields
  - Calculates total_amount

owner:
  team: data-platform
  email: data-team@acme.com
  slack: "#data-alerts"

columns:
  - name: txn_id
    type: string
    description: Unique transaction identifier
    pii: false
    example: "T00123"
    tests: [not_null, unique]

  - name: customer_id
    type: string
    description: Customer identifier
    pii: true
    pii_type: customer_id
    example: "C98765"

  - name: quantity
    type: int
    description: Quantity sold
    pii: false
    example: "2"
    tests: [not_null, positive]

  - name: total_amount
    type: decimal(12,2)
    description: Total transaction amount
    pii: false
    tests: [not_null]

freshness:
  warn_after:
    hours: 6
  error_after:
    hours: 24

triggers:
  - type: s3_sensor
    path: bronze/sales/
    interval: 60
  - type: freshness

documentation:
  tags: [sales, finance, daily]
  rules:
    - name: positive_quantities
      description: Quantities must be greater than zero
      sql: "quantity > 0"

tests:
  - name: total_equals_qty_times_price
    sql: |
      SELECT COUNT(*) FROM {{ this }}
      WHERE ABS(total_amount - quantity * unit_price) > 0.01
    expect: 0
```
