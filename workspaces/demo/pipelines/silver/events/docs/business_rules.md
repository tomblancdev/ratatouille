# Business Rules: Events

> 🐀 Auto-generated | Layer: `silver` | Last updated: 2026-02-05

## Summary

Total rules: **11**

| Source | Count |
|--------|-------|
| 🔍 Sql | 3 |
| ✅ Test | 8 |

## 🔍 SQL Filter Rules

These rules were extracted from SQL WHERE clauses:

### required_event_id

Event Id is required

```sql
event_id IS NOT NULL
```

### required_user_id

User Id is required

```sql
user_id IS NOT NULL
```

### max_timestamp

No future events

```sql
timestamp <= NOW()
```


## ✅ Test-Based Rules

These rules are enforced through column tests and custom data tests:

### required_event_id

event_id is required (cannot be NULL)

```sql
event_id IS NOT NULL
```

### unique_event_id

event_id must be unique

```sql
COUNT(DISTINCT event_id) = COUNT(event_id)
```

### required_user_id

user_id is required (cannot be NULL)

```sql
user_id IS NOT NULL
```

### required_event_type

event_type is required (cannot be NULL)

```sql
event_type IS NOT NULL
```

### valid_event_type

event_type must be one of: PAGEVIEW, CLICK, SCROLL, FORM_SUBMIT, PURCHASE

```sql
event_type IN ('PAGEVIEW', 'CLICK', 'SCROLL', 'FORM_SUBMIT', 'PURCHASE')
```

### valid_device

device must be one of: desktop, mobile, tablet

```sql
device IN ('desktop', 'mobile', 'tablet')
```

### required__date

_date is required (cannot be NULL)

```sql
_date IS NOT NULL
```

### no_future_events

Custom test: no_future_events

```sql
SELECT COUNT(*) FROM {{ this }}
WHERE event_timestamp > NOW()

```


## Quick Reference

| Rule | Source | SQL |
|------|--------|-----|
| required_event_id | sql | `event_id IS NOT NULL` |
| required_user_id | sql | `user_id IS NOT NULL` |
| max_timestamp | sql | `timestamp <= NOW()` |
| required_event_id | test | `event_id IS NOT NULL` |
| unique_event_id | test | `COUNT(DISTINCT event_id) = COUNT(event_i...` |
| required_user_id | test | `user_id IS NOT NULL` |
| required_event_type | test | `event_type IS NOT NULL` |
| valid_event_type | test | `event_type IN ('PAGEVIEW', 'CLICK', 'SCR...` |
| valid_device | test | `device IN ('desktop', 'mobile', 'tablet'...` |
| required__date | test | `_date IS NOT NULL` |
| no_future_events | test | `SELECT COUNT(*) FROM {{ this }}
WHERE ev...` |
