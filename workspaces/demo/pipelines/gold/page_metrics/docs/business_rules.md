# Business Rules: Page Metrics

> 🐀 Auto-generated | Layer: `gold` | Last updated: 2026-02-05

## Summary

Total rules: **5**

| Source | Count |
|--------|-------|
| ✅ Test | 5 |

## ✅ Test-Based Rules

These rules are enforced through column tests and custom data tests:

### required_page_url

page_url is required (cannot be NULL)

```sql
page_url IS NOT NULL
```

### unique_page_url

page_url must be unique

```sql
COUNT(DISTINCT page_url) = COUNT(page_url)
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
| required_page_url | test | `page_url IS NOT NULL` |
| unique_page_url | test | `COUNT(DISTINCT page_url) = COUNT(page_ur...` |
| required_total_events | test | `total_events IS NOT NULL` |
| positive_total_events | test | `total_events > 0` |
| required_unique_users | test | `unique_users IS NOT NULL` |
