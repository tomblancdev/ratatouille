# Business Rules: Sales

> 🐀 Auto-generated | Layer: `silver` | Last updated: 2026-02-05

## Summary

Total rules: **20**

| Source | Count |
|--------|-------|
| 📝 Documented | 4 |
| 🔍 Sql | 3 |
| ✅ Test | 13 |

## 📝 Documented Rules

These rules are explicitly documented in config.yaml:

### positive_quantities

Quantities must be greater than zero

```sql
quantity > 0
```

### positive_prices

Prices must be greater than zero

```sql
unit_price > 0
```

### valid_total

Total must equal quantity × unit_price

```sql
ABS(total_amount - quantity * unit_price) <= 0.01
```

### required_txn_id

Every transaction must have an ID

```sql
txn_id IS NOT NULL
```


## 🔍 SQL Filter Rules

These rules were extracted from SQL WHERE clauses:

### positive_quantity

Quantity must be greater than

```sql
quantity > 0
```

### positive_unit_price

Unit Price must be greater than

```sql
unit_price > 0
```

### required_txn_id

Txn Id is required

```sql
txn_id IS NOT NULL
```


## ✅ Test-Based Rules

These rules are enforced through column tests and custom data tests:

### required_txn_id

txn_id is required (cannot be NULL)

```sql
txn_id IS NOT NULL
```

### unique_txn_id

txn_id must be unique

```sql
COUNT(DISTINCT txn_id) = COUNT(txn_id)
```

### required_store_id

store_id is required (cannot be NULL)

```sql
store_id IS NOT NULL
```

### required_product_id

product_id is required (cannot be NULL)

```sql
product_id IS NOT NULL
```

### required_quantity

quantity is required (cannot be NULL)

```sql
quantity IS NOT NULL
```

### positive_quantity

quantity must be greater than zero

```sql
quantity > 0
```

### required_unit_price

unit_price is required (cannot be NULL)

```sql
unit_price IS NOT NULL
```

### positive_unit_price

unit_price must be greater than zero

```sql
unit_price > 0
```

### required_total_amount

total_amount is required (cannot be NULL)

```sql
total_amount IS NOT NULL
```

### positive_total_amount

total_amount must be greater than zero

```sql
total_amount > 0
```

### valid_payment_method

payment_method must be one of: CASH, CREDIT, DEBIT

```sql
payment_method IN ('CASH', 'CREDIT', 'DEBIT')
```

### required__date

_date is required (cannot be NULL)

```sql
_date IS NOT NULL
```

### total_equals_qty_times_price

Custom test: total_equals_qty_times_price

```sql
SELECT COUNT(*) FROM {{ this }}
WHERE ABS(total_amount - quantity * unit_price) > 0.01

```


## Quick Reference

| Rule | Source | SQL |
|------|--------|-----|
| positive_quantities | documented | `quantity > 0` |
| positive_prices | documented | `unit_price > 0` |
| valid_total | documented | `ABS(total_amount - quantity * unit_price...` |
| required_txn_id | documented | `txn_id IS NOT NULL` |
| positive_quantity | sql | `quantity > 0` |
| positive_unit_price | sql | `unit_price > 0` |
| required_txn_id | sql | `txn_id IS NOT NULL` |
| required_txn_id | test | `txn_id IS NOT NULL` |
| unique_txn_id | test | `COUNT(DISTINCT txn_id) = COUNT(txn_id)` |
| required_store_id | test | `store_id IS NOT NULL` |
| required_product_id | test | `product_id IS NOT NULL` |
| required_quantity | test | `quantity IS NOT NULL` |
| positive_quantity | test | `quantity > 0` |
| required_unit_price | test | `unit_price IS NOT NULL` |
| positive_unit_price | test | `unit_price > 0` |
| required_total_amount | test | `total_amount IS NOT NULL` |
| positive_total_amount | test | `total_amount > 0` |
| valid_payment_method | test | `payment_method IN ('CASH', 'CREDIT', 'DE...` |
| required__date | test | `_date IS NOT NULL` |
| total_equals_qty_times_price | test | `SELECT COUNT(*) FROM {{ this }}
WHERE AB...` |
