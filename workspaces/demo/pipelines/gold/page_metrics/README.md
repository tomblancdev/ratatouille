# Page Metrics Pipeline

> 🐀 Auto-generated documentation | Last updated: 2026-02-05

## Overview

Page-level traffic analysis and engagement metrics.

Use Cases:
- Identify most popular pages
- Track conversion funnels
- Analyze user engagement
- Optimize landing pages

## Owner

- **Email:** analytics-team@acme.com

## Dependencies

### Upstream
- `silver.events`

## Freshness SLA

- **Warning:** 6 hour(s)
- **Error:** 24 hour(s)

## Documentation

- [Data Dictionary](docs/data_dictionary.md) - Column definitions and types
- [Business Rules](docs/business_rules.md) - Data validation logic
- [Lineage](docs/lineage.md) - Dependency diagram

## Schema Summary

| Column | Type | Required | Unique |
|--------|------|----------|--------|
| `page_url` | string | ✓ | ✓ |
| `total_events` | int | ✓ |  |
| `unique_users` | int | ✓ |  |
| `unique_sessions` | int |  |  |
| `pageviews` | int |  |  |
| `clicks` | int |  |  |
| `purchases` | int |  |  |
| `avg_session_duration` | decimal(10,1) |  |  |
| `conversion_rate` | decimal(5,2) |  |  |

See [Data Dictionary](docs/data_dictionary.md) for full schema.

<!-- MANUAL CONTENT START -->
## Additional Notes

*Add your manual notes here. This section is preserved on regeneration.*
<!-- MANUAL CONTENT END -->
