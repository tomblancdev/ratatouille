# Data Dictionary: Page Metrics

> 🐀 Auto-generated | Layer: `gold` | Last updated: 2026-02-05

## Summary

- **Total columns:** 9
- **Required (not_null):** 3
- **Unique keys:** 1
- **PII columns:** 0
- **⚠️ Missing PII marking:** 9

## Quick Reference

| Column | Type | PII | Required | Unique |
|--------|------|-----|----------|--------|
| `page_url` | string | ? | ✓ | ✓ |
| `total_events` | int | ? | ✓ |  |
| `unique_users` | int | ? | ✓ |  |
| `unique_sessions` | int | ? |  |  |
| `pageviews` | int | ? |  |  |
| `clicks` | int | ? |  |  |
| `purchases` | int | ? |  |  |
| `avg_session_duration` | decimal(10,1) | ? |  |  |
| `conversion_rate` | decimal(5,2) | ? |  |  |

## Column Definitions

### `page_url`

Page URL

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null`, `unique` |

### `total_events`

Total number of events

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null`, `positive` |

### `unique_users`

Distinct users

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null` |

### `unique_sessions`

Distinct sessions

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |

### `pageviews`

Pageview events

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |

### `clicks`

Click events

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |

### `purchases`

Purchase events

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |

### `avg_session_duration`

Average session duration in seconds

| Property | Value |
|----------|-------|
| **Type** | `decimal(10,1)` |
| **PII** | ❓ Not marked |

### `conversion_rate`

Purchase rate as percentage of pageviews

| Property | Value |
|----------|-------|
| **Type** | `decimal(5,2)` |
| **PII** | ❓ Not marked |
