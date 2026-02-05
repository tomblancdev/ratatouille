# Sales Pipeline

## Overview

Transforms raw POS transactions from `bronze.raw_sales` into cleaned, validated sales records.

## Dependencies

- `bronze.raw_sales` - Raw transaction data from POS system ingestion

## Transformations

1. **Validation**: Filters out invalid records
   - `quantity > 0` - No zero/negative quantities
   - `unit_price > 0` - No free items
   - `txn_id IS NOT NULL` - Must have transaction ID

2. **Enrichment**: Adds calculated fields
   - `total_amount = quantity * unit_price`
   - `_date = DATE(transaction_time)` - Partition column
   - `_processed_at = NOW()` - Processing timestamp

3. **Normalization**: Standardizes text
   - `product_name` - UPPERCASE
   - `category` - UPPERCASE
   - `payment_method` - UPPERCASE

## Schedule

- **Primary trigger**: S3 sensor on `bronze/sales/` (checks every 60 seconds)
- **Backup**: Hourly schedule
- **Materialization**: Incremental (by `_ingested_at`)

## Data Quality

| Check | Description | Severity |
|-------|-------------|----------|
| `unique_txn` | Transaction IDs must be unique | Error |
| `positive_amounts` | Quantities and prices must be positive | Error |
| `total_calculation` | total_amount = quantity * unit_price | Error |

## Freshness SLA

- **Warning**: 6 hours
- **Error**: 24 hours

## Owner

data-team@acme.com

## Schema

See [Data Dictionary](docs/data_dictionary.md)
