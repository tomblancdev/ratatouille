# Data Dictionary: Daily Sales

> 🐀 Auto-generated | Layer: `gold` | Last updated: 2026-02-05

## Summary

- **Total columns:** 9
- **Required (not_null):** 5
- **Unique keys:** 0
- **PII columns:** 0
- **⚠️ Missing PII marking:** 9

## Quick Reference

| Column | Type | PII | Required | Unique |
|--------|------|-----|----------|--------|
| `sale_date` | date | ? | ✓ |  |
| `store_id` | string | ? | ✓ |  |
| `total_transactions` | int | ? | ✓ |  |
| `total_items_sold` | int | ? | ✓ |  |
| `total_revenue` | decimal(14,2) | ? | ✓ |  |
| `avg_transaction_value` | decimal(10,2) | ? |  |  |
| `unique_customers` | int | ? |  |  |
| `unique_products` | int | ? |  |  |
| `top_category` | string | ? |  |  |

## Column Definitions

### `sale_date`

Date of sales

| Property | Value |
|----------|-------|
| **Type** | `date` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null` |

### `store_id`

Store identifier

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null` |

### `total_transactions`

Number of transactions

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null`, `positive` |

### `total_items_sold`

Total quantity of items sold

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null` |

### `total_revenue`

Total revenue for the day

| Property | Value |
|----------|-------|
| **Type** | `decimal(14,2)` |
| **PII** | ❓ Not marked |
| **Constraints** | `not_null` |

### `avg_transaction_value`

Average transaction value

| Property | Value |
|----------|-------|
| **Type** | `decimal(10,2)` |
| **PII** | ❓ Not marked |

### `unique_customers`

Distinct customers who made purchases

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |

### `unique_products`

Distinct products sold

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | ❓ Not marked |

### `top_category`

Most popular product category

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ❓ Not marked |
