# Data Dictionary: Events

> 🐀 Auto-generated | Layer: `silver` | Last updated: 2026-02-05

## Summary

- **Total columns:** 7
- **Required (not_null):** 4
- **Unique keys:** 1
- **PII columns:** 0
- **⚠️ Missing PII marking:** 7

## Quick Reference

| Column | Type | PII | Required | Unique |
|--------|------|-----|----------|--------|
| `event_id` | string | ? | ✓ | ✓ |
| `user_id` | string | ? | ✓ |  |
| `session_id` | string | ? |  |  |
| `event_type` | string | ? | ✓ |  |
| `page_url` | string | ? |  |  |
| `device` | string | ? |  |  |
| `_date` | date | ? | ✓ |  |

## Column Definitions

### `event_id`

Unique event identifier

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null`, `unique` |

### `user_id`

Anonymous user identifier

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null` |

### `session_id`

Session identifier

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ❓ Not marked |

### `event_type`

Type of event

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null`, `accepted_values(PAGEVIEW, CLICK, SCROLL...)` |

### `page_url`

Page URL where event occurred

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ❓ Not marked |

### `device`

Device type

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ❓ Not marked |
| **Constraints** | `accepted_values(desktop, mobile, tablet)` |

### `_date`

Event date (partition column)

| Property | Value |
|----------|-------|
| **Type** | `date` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null` |
