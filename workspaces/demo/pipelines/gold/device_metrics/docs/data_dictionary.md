# Data Dictionary: Device Metrics

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
| `device` | string | ? | ✓ | ✓ |
| `total_events` | int | ? | ✓ |  |
| `unique_users` | int | ? | ✓ |  |
| `unique_sessions` | int | ? |  |  |
| `purchases` | int | ? |  |  |
| `conversion_rate` | decimal(5,2) | ? |  |  |
| `avg_session_duration` | decimal(10,1) | ? |  |  |
| `countries_reached` | int | ? |  |  |
| `top_browser` | string | ? |  |  |

## Column Definitions

### `device`

Device type (desktop, mobile, tablet)

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null`, `unique`, `accepted_values(desktop, mobile, tablet)` |

### `total_events`

Total events from this device

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

### `purchases`

Purchase events

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |

### `conversion_rate`

Purchase rate as percentage

| Property | Value |
|----------|-------|
| **Type** | `decimal(5,2)` |
| **PII** | ❓ Not marked |

### `avg_session_duration`

Average session duration in seconds

| Property | Value |
|----------|-------|
| **Type** | `decimal(10,1)` |
| **PII** | ❓ Not marked |

### `countries_reached`

Number of distinct countries

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |

### `top_browser`

Most common browser

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ❓ Not marked |
