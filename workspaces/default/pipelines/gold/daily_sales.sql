-- 🐀 Gold Daily Sales Pipeline
-- Aggregates silver sales data into daily KPIs
--
-- @name: gold_daily_sales
-- @materialized: table
-- @partition_by: sale_date
-- @owner: analytics-team

SELECT
    _date AS sale_date,
    store_id,
    COUNT(*) AS total_transactions,
    SUM(quantity) AS total_items_sold,
    ROUND(SUM(total_amount), 2) AS total_revenue,
    ROUND(AVG(total_amount), 2) AS avg_transaction_value,
    COUNT(DISTINCT customer_id) AS unique_customers,
    COUNT(DISTINCT product_id) AS unique_products
FROM {{ ref('silver.sales') }}
GROUP BY _date, store_id
ORDER BY _date DESC, total_revenue DESC
