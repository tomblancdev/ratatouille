# Business Rules: Daily Sales

> 🐀 Auto-generated | Layer: `gold` | Last updated: 2026-02-05

## Summary

Total rules: **6**

| Source | Count |
|--------|-------|
| ✅ Test | 6 |

## ✅ Test-Based Rules

These rules are enforced through column tests and custom data tests:

### required_sale_date

sale_date is required (cannot be NULL)

```sql
sale_date IS NOT NULL
```

### required_store_id

store_id is required (cannot be NULL)

```sql
store_id IS NOT NULL
```

### required_total_transactions

total_transactions is required (cannot be NULL)

```sql
total_transactions IS NOT NULL
```

### positive_total_transactions

total_transactions must be greater than zero

```sql
total_transactions > 0
```

### required_total_items_sold

total_items_sold is required (cannot be NULL)

```sql
total_items_sold IS NOT NULL
```

### required_total_revenue

total_revenue is required (cannot be NULL)

```sql
total_revenue IS NOT NULL
```


## Quick Reference

| Rule | Source | SQL |
|------|--------|-----|
| required_sale_date | test | `sale_date IS NOT NULL` |
| required_store_id | test | `store_id IS NOT NULL` |
| required_total_transactions | test | `total_transactions IS NOT NULL` |
| positive_total_transactions | test | `total_transactions > 0` |
| required_total_items_sold | test | `total_items_sold IS NOT NULL` |
| required_total_revenue | test | `total_revenue IS NOT NULL` |
