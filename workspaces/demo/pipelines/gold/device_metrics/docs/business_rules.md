# Business Rules: Device Metrics

> 🐀 Auto-generated | Layer: `gold` | Last updated: 2026-02-05

## Summary

Total rules: **6**

| Source | Count |
|--------|-------|
| ✅ Test | 6 |

## ✅ Test-Based Rules

These rules are enforced through column tests and custom data tests:

### required_device

device is required (cannot be NULL)

```sql
device IS NOT NULL
```

### unique_device

device must be unique

```sql
COUNT(DISTINCT device) = COUNT(device)
```

### valid_device

device must be one of: desktop, mobile, tablet

```sql
device IN ('desktop', 'mobile', 'tablet')
```

### required_total_events

total_events is required (cannot be NULL)

```sql
total_events IS NOT NULL
```

### positive_total_events

total_events must be greater than zero

```sql
total_events > 0
```

### required_unique_users

unique_users is required (cannot be NULL)

```sql
unique_users IS NOT NULL
```


## Quick Reference

| Rule | Source | SQL |
|------|--------|-----|
| required_device | test | `device IS NOT NULL` |
| unique_device | test | `COUNT(DISTINCT device) = COUNT(device)` |
| valid_device | test | `device IN ('desktop', 'mobile', 'tablet'...` |
| required_total_events | test | `total_events IS NOT NULL` |
| positive_total_events | test | `total_events > 0` |
| required_unique_users | test | `unique_users IS NOT NULL` |
