# Daily Sales Pipeline

> 🐀 Auto-generated documentation | Last updated: 2026-02-05

## Overview

Daily sales KPIs aggregated by store.

Use Cases:
- Executive dashboards
- Store performance comparison
- Revenue trend analysis
- Customer behavior insights

## Owner

- **Email:** analytics-team@acme.com

## Dependencies

### Upstream
- `silver.sales`

## Freshness SLA

- **Warning:** 12 hour(s)
- **Error:** 36 hour(s)

## Documentation

- [Data Dictionary](docs/data_dictionary.md) - Column definitions and types
- [Business Rules](docs/business_rules.md) - Data validation logic
- [Lineage](docs/lineage.md) - Dependency diagram

## Schema Summary

| Column | Type | Required | Unique |
|--------|------|----------|--------|
| `sale_date` | date | ✓ |  |
| `store_id` | string | ✓ |  |
| `total_transactions` | int | ✓ |  |
| `total_items_sold` | int | ✓ |  |
| `total_revenue` | decimal(14,2) | ✓ |  |
| `avg_transaction_value` | decimal(10,2) |  |  |
| `unique_customers` | int |  |  |
| `unique_products` | int |  |  |
| `top_category` | string |  |  |

See [Data Dictionary](docs/data_dictionary.md) for full schema.

<!-- MANUAL CONTENT START -->
## Additional Notes

*Add your manual notes here. This section is preserved on regeneration.*
<!-- MANUAL CONTENT END -->
