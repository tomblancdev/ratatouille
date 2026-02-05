# Events Pipeline

> 🐀 Auto-generated documentation | Last updated: 2026-02-05

## Overview

Cleaned and validated web analytics events.

Transformations:
- Filters invalid records (null IDs, future timestamps)
- Standardizes event_type and country to uppercase
- Standardizes device to lowercase
- Partitioned by date

## Owner

- **Email:** data-team@acme.com

## Dependencies

### Upstream
- `bronze.raw_events`

### Downstream
- `gold.page_metrics`
- `gold.device_metrics`

## Freshness SLA

- **Warning:** 2 hour(s)
- **Error:** 12 hour(s)

## Documentation

- [Data Dictionary](docs/data_dictionary.md) - Column definitions and types
- [Business Rules](docs/business_rules.md) - Data validation logic
- [Lineage](docs/lineage.md) - Dependency diagram

## Schema Summary

| Column | Type | Required | Unique |
|--------|------|----------|--------|
| `event_id` | string | ✓ | ✓ |
| `user_id` | string | ✓ |  |
| `session_id` | string |  |  |
| `event_type` | string | ✓ |  |
| `page_url` | string |  |  |
| `device` | string |  |  |
| `_date` | date | ✓ |  |

See [Data Dictionary](docs/data_dictionary.md) for full schema.

<!-- MANUAL CONTENT START -->
## Additional Notes

*Add your manual notes here. This section is preserved on regeneration.*
<!-- MANUAL CONTENT END -->
