-- 🐀 Executive Metrics Pipeline
-- Combines data from multiple products for executive dashboards
--
-- @name: exec_metrics
-- @materialized: table
-- @partition_by: report_date
-- @owner: analytics-team

-- This pipeline consumes data products from the default workspace
-- - products.sales: Daily sales KPIs
-- - products.inventory: Store inventory levels

SELECT
    s.sale_date AS report_date,
    s.store_id,

    -- Sales metrics
    s.total_transactions,
    s.total_revenue,
    s.avg_transaction_value,
    s.unique_customers,

    -- Inventory metrics (if available)
    i.total_sku_count,
    i.low_stock_count,
    i.out_of_stock_count,

    -- Derived metrics
    ROUND(s.total_revenue / NULLIF(i.total_sku_count, 0), 2) AS revenue_per_sku,
    ROUND(s.total_revenue / NULLIF(s.unique_customers, 0), 2) AS revenue_per_customer,

    -- Health indicators
    CASE
        WHEN i.out_of_stock_count > 10 THEN 'critical'
        WHEN i.low_stock_count > 20 THEN 'warning'
        ELSE 'healthy'
    END AS inventory_health,

    NOW() AS _processed_at

FROM products.sales s
LEFT JOIN products.inventory i
    ON s.store_id = i.store_id
    AND s.sale_date = i.snapshot_date

WHERE s.sale_date >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY s.sale_date DESC, s.total_revenue DESC
