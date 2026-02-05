# Pipeline Testing Guide

Ratatouille includes a comprehensive testing framework for validating data pipelines. Tests can run locally with mock data or against real data in production.

## Overview

```
pipelines/silver/sales/
├── pipeline.sql          # Your transformation
├── config.yaml
└── tests/
    ├── mocks/            # Test data
    │   └── bronze_sales.yaml
    ├── quality/          # Data quality checks
    │   ├── unique_txn.sql
    │   └── positive_amounts.sql
    └── unit/             # Unit tests
        └── test_transform.sql
```

## Test Types

| Type | Purpose | Runs Against |
|------|---------|--------------|
| **Quality** | Validate data quality rules | Mocks or real S3 data |
| **Unit SQL** | Test SQL transformations | Mock data only |
| **Unit Python** | Test Python ingestion logic | Mock data + API emulators |

## Quick Start

```bash
# Run all tests
rat test --workspace demo

# Run tests for a specific pipeline
rat test --pipeline silver/sales

# Run only quality tests
rat test --type quality

# Verbose output with data
rat test --verbose

# JSON output for CI/CD
rat test --output json
```

---

## Quality Tests

Quality tests validate data integrity rules. A test **passes if the query returns zero rows** (no violations found).

### Basic Quality Test

```sql
-- tests/quality/unique_txn.sql
-- @name: unique_transaction_ids
-- @description: Transaction IDs must be unique
-- @severity: error
-- @mocks: mocks/bronze_sales.yaml

SELECT
    txn_id,
    COUNT(*) as occurrences
FROM {{ this }}
GROUP BY txn_id
HAVING COUNT(*) > 1
```

### Metadata Options

| Option | Description | Example |
|--------|-------------|---------|
| `@name` | Test identifier | `unique_transaction_ids` |
| `@description` | Human-readable description | `Transaction IDs must be unique` |
| `@severity` | `error` (blocking) or `warn` (non-blocking) | `error` |
| `@mocks` | Mock data files to load | `mocks/bronze_sales.yaml` |

### Severity Levels

- **`error`** - Test failure blocks downstream pipelines (in Dagster)
- **`warn`** - Test failure is reported but doesn't block execution

### Running Modes

**With mocks** (local development):
```sql
-- @mocks: mocks/bronze_sales.yaml
```
Runs the pipeline SQL against mock data, then validates the result.

**Without mocks** (production):
```sql
-- No @mocks specified
```
Runs directly against real S3 data. Returns `SKIPPED` if no data exists.

---

## Unit Tests (SQL)

Unit tests validate that transformations produce expected output.

### Basic Unit Test

```sql
-- tests/unit/test_transform.sql
-- @name: test_basic_transformation
-- @description: Verify total calculation
-- @mocks: mocks/bronze_sales.yaml
-- @expect_count: 2

-- The pipeline SQL runs automatically, this is just for assertions
```

### Expected Results

**Count assertion:**
```sql
-- @expect_count: 5
```
Verifies the transformation produces exactly 5 rows.

**Row assertions (inline YAML):**
```sql
-- @expect: [{txn_id: "T001", total_amount: 20.00}, {txn_id: "T002", total_amount: 76.50}]
-- @expect_columns: [txn_id, total_amount]
```

### Incremental Mode Testing

Test incremental pipelines with watermarks:

```sql
-- @name: test_incremental_load
-- @mode: incremental
-- @watermarks: {updated_at: "2024-01-15 00:00:00"}
-- @mocks: mocks/bronze_sales.yaml
```

---

## Mock Data Formats

### YAML (Recommended)

```yaml
# mocks/bronze_sales.yaml
table: bronze_raw_sales
rows:
  - txn_id: "T001"
    store_id: "S1"
    quantity: 2
    unit_price: 10.00
    transaction_time: "2024-01-15 10:30:00"

  - txn_id: "T002"
    store_id: "S2"
    quantity: 3
    unit_price: 25.50
    transaction_time: "2024-01-15 14:00:00"
```

### Multiple Tables

```yaml
# mocks/all_sources.yaml
tables:
  - table: bronze_raw_sales
    rows:
      - txn_id: "T001"
        quantity: 2

  - table: bronze_stores
    rows:
      - store_id: "S1"
        store_name: "Downtown"
```

### CSV

```csv
txn_id,store_id,quantity,unit_price
T001,S1,2,10.00
T002,S2,3,25.50
```

Table name derived from filename: `bronze_sales.csv` → `bronze_sales`

### JSON

```json
{
  "table": "bronze_raw_sales",
  "rows": [
    {"txn_id": "T001", "quantity": 2},
    {"txn_id": "T002", "quantity": 3}
  ]
}
```

### Parquet

Use for large datasets or complex types. Table name derived from filename.

### Excel

Each sheet becomes a table. Sheet name = table name.

### Python Generator

```python
# mocks/generator.py
# @generates: bronze_raw_sales

def generate(num_records: int = 100) -> list[dict]:
    """Generate realistic sales data."""
    from faker import Faker
    fake = Faker()

    return [
        {
            "txn_id": f"T{i:05d}",
            "store_id": fake.random_element(["S1", "S2", "S3"]),
            "quantity": fake.random_int(1, 10),
            "unit_price": round(fake.random.uniform(5.0, 100.0), 2),
        }
        for i in range(num_records)
    ]
```

---

## Dagster Asset Checks

Quality tests automatically become Dagster asset checks:

| Test Severity | Dagster Behavior |
|---------------|------------------|
| `severity: error` | **Blocking** - downstream assets won't run if check fails |
| `severity: warn` | **Non-blocking** - warning only |

### Viewing in Dagster UI

1. Open Dagster UI (http://localhost:3000)
2. Navigate to Assets → your asset
3. Click "Checks" tab to see all quality checks
4. Failed checks show sample violations

### Blocking Behavior

```
silver/sales ──▶ [Asset Checks] ──▶ gold/daily_metrics
                     │
                     ├─ unique_txn ✅
                     ├─ positive_amounts ❌ (blocking)
                     └─ category_check ⚠️ (warning)

Result: gold/daily_metrics is BLOCKED until positive_amounts passes
```

---

## CLI Reference

```bash
# Basic usage
rat test [OPTIONS]

# Options
--workspace, -w    Workspace name or path (default: current directory)
--pipeline, -p     Filter by pipeline (e.g., "silver/sales")
--layer, -l        Filter by layer (bronze, silver, gold)
--type, -t         Filter by test type (quality, unit) - can repeat
--output, -o       Output format: console (default) or json
--verbose, -v      Show detailed output with data tables
```

### Examples

```bash
# Run all tests in demo workspace
rat test -w demo

# Run only quality tests for sales pipeline
rat test -p silver/sales -t quality

# Run silver layer tests with verbose output
rat test -l silver -v

# JSON output for CI/CD pipelines
rat test -w demo -o json | jq '.summary'
```

---

## Test Output

### Console Output

```
🐀 Running tests for workspace: demo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 silver/sales
  ✅ unique_transaction_ids           16ms
     → No violations
  ❌ positive_amounts                 15ms
     → 2 violations found

     ┏━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
     ┃ txn_id ┃ quantity ┃ reason          ┃
     ┡━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
     │ T003   │ 0        │ quantity <= 0   │
     │ T004   │ -1       │ quantity <= 0   │
     └────────┴──────────┴─────────────────┘
  ⚠️ category_check                   12ms
     → 1 violations found (warning)
  ✅ test_basic_transformation        25ms
     → All assertions passed (2 rows)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Summary: 4 tests | 2 passed ✅ | 1 failed ❌ | 1 warned ⚠️
```

### JSON Output

```json
{
  "workspace": "demo",
  "summary": {
    "total": 4,
    "passed": 2,
    "failed": 1,
    "warned": 1,
    "errored": 0,
    "skipped": 0,
    "duration_ms": 68
  },
  "pipelines": [
    {
      "name": "silver/sales",
      "tests": [
        {
          "name": "unique_transaction_ids",
          "status": "passed",
          "type": "quality",
          "duration_ms": 16,
          "message": "No violations"
        }
      ]
    }
  ]
}
```

---

## Best Practices

### 1. Always Use Mocks for Quality Tests

```sql
-- @mocks: mocks/bronze_sales.yaml
```

This allows tests to run locally without S3 access.

### 2. Use Severity Appropriately

- `error` for critical data quality rules (uniqueness, not null, referential integrity)
- `warn` for soft rules (data freshness, optional fields)

### 3. Include Edge Cases in Mocks

```yaml
rows:
  - txn_id: "T001"    # Normal case
    quantity: 2

  - txn_id: null      # Edge case: null ID
    quantity: 1

  - txn_id: "T003"    # Edge case: zero quantity
    quantity: 0
```

### 4. Name Tests Descriptively

```sql
-- @name: unique_transaction_ids_per_store_per_day
-- @description: Each store should have unique transaction IDs within a day
```

### 5. Test Incremental Logic

```sql
-- @name: test_incremental_deduplication
-- @mode: incremental
-- @watermarks: {updated_at: "2024-01-15 00:00:00"}
```

---

## Troubleshooting

### Tests Skipped

```
⏭️ unique_transaction_ids
   → No data available - run pipeline first or add mocks
```

**Solution:** Add `@mocks` to the test or run the pipeline first.

### Mock Table Not Found

```
Error: Table 'bronze_raw_sales' not found
```

**Solution:** Check the `table` name in your YAML matches the `{{ ref() }}` in your SQL.

### Blocking Check Failed

If a blocking check fails, downstream assets won't materialize in Dagster.

**Solution:** Fix the data quality issue or temporarily change severity to `warn`.
