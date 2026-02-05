# Sales Pipeline

> 🐀 Auto-generated documentation | Last updated: 2026-02-05

**Tags:** `sales` `finance` `daily` `pos`

## Overview

Cleaned and validated POS sales transactions.

Transformations:
- Filters invalid records (quantity <= 0, price <= 0)
- Standardizes text to uppercase
- Calculates total_amount
- Partitioned by date

## Owner

- **Team:** data-platform
- **Email:** data-team@acme.com
- **Slack:** #data-alerts

## Dependencies

### Upstream
- `bronze.raw_sales`

### Downstream
- `gold.daily_sales`

## Freshness SLA

- **Warning:** 6 hour(s)
- **Error:** 24 hour(s)

## ⚠️ PII Notice

This pipeline contains personally identifiable information (PII):

- `customer_id` (customer_id): Customer identifier (linked to customer records)

## Documentation

- [Data Dictionary](docs/data_dictionary.md) - Column definitions and types
- [Business Rules](docs/business_rules.md) - Data validation logic
- [Lineage](docs/lineage.md) - Dependency diagram

## Schema Summary

| Column | Type | Required | Unique |
|--------|------|----------|--------|
| `txn_id` | string | ✓ | ✓ |
| `store_id` | string | ✓ |  |
| `product_id` | string | ✓ |  |
| `product_name` | string |  |  |
| `category` | string |  |  |
| `quantity` | int | ✓ |  |
| `unit_price` | decimal(10,2) | ✓ |  |
| `total_amount` | decimal(12,2) | ✓ |  |
| `payment_method` | string |  |  |
| `customer_id` | string |  |  |
| ... | *4 more columns* | | |

See [Data Dictionary](docs/data_dictionary.md) for full schema.

<!-- MANUAL CONTENT START -->
## Custom Notes by Tom

This section should be preserved when re-running `rat docs generate`.

### Important Contact
For urgent issues, contact the on-call team at #data-oncall.

### Historical Context
This pipeline was migrated from the legacy ETL system in Q1 2024.
<!-- MANUAL CONTENT END -->
