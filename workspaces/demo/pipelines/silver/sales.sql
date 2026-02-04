-- 🐀 Silver: Cleaned Sales
-- Validates and enriches raw POS transactions
--
-- @name: silver_sales
-- @materialized: incremental
-- @unique_key: txn_id
-- @partition_by: _date
-- @owner: data-team

SELECT
    txn_id,
    store_id,
    product_id,
    UPPER(product_name) AS product_name,
    UPPER(category) AS category,
    quantity,
    unit_price,
    ROUND(quantity * unit_price, 2) AS total_amount,
    UPPER(payment_method) AS payment_method,
    customer_id,
    transaction_time,
    CAST(transaction_time AS DATE) AS _date,
    _ingested_at,
    NOW() AS _processed_at
FROM {{ ref('bronze.raw_sales') }}
WHERE quantity > 0
  AND unit_price > 0
  AND txn_id IS NOT NULL
{% if is_incremental() %}
  AND _ingested_at > '{{ watermark("_ingested_at") }}'
{% endif %}
