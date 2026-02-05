# Sales Data Dictionary

## Columns

| Column | Type | Description | Example | Tests |
|--------|------|-------------|---------|-------|
| `txn_id` | string | Unique transaction identifier | "TXN-2024-001" | not_null, unique |
| `store_id` | string | Store identifier | "S1" | not_null |
| `product_id` | string | Product identifier | "P001" | not_null |
| `product_name` | string | Product name (UPPERCASE) | "WIDGET PRO" | - |
| `category` | string | Product category (UPPERCASE) | "ELECTRONICS" | - |
| `quantity` | int | Quantity sold | 3 | not_null, positive |
| `unit_price` | decimal(10,2) | Price per unit | 25.50 | not_null, positive |
| `total_amount` | decimal(12,2) | Total (quantity * unit_price) | 76.50 | not_null, positive |
| `payment_method` | string | Payment method (UPPERCASE) | "CARD" | - |
| `customer_id` | string | Customer identifier | "C001" | - |
| `transaction_time` | timestamp | Original transaction timestamp | 2024-01-15 14:30:00 | - |
| `_date` | date | Transaction date (partition) | 2024-01-15 | not_null |
| `_ingested_at` | timestamp | When raw data was ingested | 2024-01-15 15:00:00 | - |
| `_processed_at` | timestamp | When this record was processed | 2024-01-15 15:05:00 | - |

## Partitioning

- **Partition column**: `_date`
- **Format**: Daily partitions

## Source Lineage

```
bronze.raw_sales (POS System)
        │
        ▼
    silver.sales (This table)
        │
        ▼
gold.daily_sales (KPI aggregations)
```

## Sample Query

```sql
-- Count by store and date
SELECT
    _date,
    store_id,
    COUNT(*) as transactions,
    SUM(total_amount) as revenue
FROM silver.sales
GROUP BY _date, store_id
ORDER BY _date DESC, revenue DESC
```
