# Data Dictionary: Sales

> 🐀 Auto-generated | Layer: `silver` | Last updated: 2026-02-05

## Summary

- **Total columns:** 14
- **Required (not_null):** 7
- **Unique keys:** 1
- **PII columns:** 1

## Quick Reference

| Column | Type | PII | Required | Unique |
|--------|------|-----|----------|--------|
| `txn_id` | string | ✓ | ✓ | ✓ |
| `store_id` | string | ✓ | ✓ |  |
| `product_id` | string | ✓ | ✓ |  |
| `product_name` | string | ✓ |  |  |
| `category` | string | ✓ |  |  |
| `quantity` | int | ✓ | ✓ |  |
| `unit_price` | decimal(10,2) | ✓ | ✓ |  |
| `total_amount` | decimal(12,2) | ✓ | ✓ |  |
| `payment_method` | string | ✓ |  |  |
| `customer_id` | string | ⚠️ |  |  |
| `transaction_time` | timestamp | ✓ |  |  |
| `_date` | date | ✓ | ✓ |  |
| `_ingested_at` | timestamp | ✓ |  |  |
| `_processed_at` | timestamp | ✓ |  |  |

## Column Definitions

### `txn_id`

Unique transaction identifier

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | No |
| **Example** | `T00123` |
| **Constraints** | `not_null`, `unique` |

### `store_id`

Store identifier

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | No |
| **Example** | `S001` |
| **Constraints** | `not_null` |

### `product_id`

Product identifier

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | No |
| **Example** | `P00456` |
| **Constraints** | `not_null` |

### `product_name`

Product name (uppercased)

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | No |
| **Example** | `WIDGET PRO` |

### `category`

Product category (uppercased)

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | No |
| **Example** | `ELECTRONICS` |

### `quantity`

Quantity sold

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **PII** | No |
| **Example** | `2` |
| **Constraints** | `not_null`, `positive` |

### `unit_price`

Price per unit

| Property | Value |
|----------|-------|
| **Type** | `decimal(10,2)` |
| **PII** | No |
| **Example** | `29.99` |
| **Constraints** | `not_null`, `positive` |

### `total_amount`

Total transaction amount (quantity × unit_price)

| Property | Value |
|----------|-------|
| **Type** | `decimal(12,2)` |
| **PII** | No |
| **Example** | `59.98` |
| **Constraints** | `not_null`, `positive` |

### `payment_method`

Payment method (CASH, CREDIT, DEBIT)

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | No |
| **Example** | `CREDIT` |
| **Constraints** | `accepted_values(CASH, CREDIT, DEBIT)` |

### `customer_id`

Customer identifier (linked to customer records)

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **PII** | ⚠️ Yes (customer_id) |
| **Example** | `C98765` |

### `transaction_time`

When the transaction occurred

| Property | Value |
|----------|-------|
| **Type** | `timestamp` |
| **PII** | No |

### `_date`

Transaction date (partition column)

| Property | Value |
|----------|-------|
| **Type** | `date` |
| **PII** | No |
| **Example** | `2024-01-15` |
| **Constraints** | `not_null` |

### `_ingested_at`

When record was ingested to bronze

| Property | Value |
|----------|-------|
| **Type** | `timestamp` |
| **PII** | No |

### `_processed_at`

When record was processed to silver

| Property | Value |
|----------|-------|
| **Type** | `timestamp` |
| **PII** | No |
