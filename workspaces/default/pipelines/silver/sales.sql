-- 🐀 Silver Sales Pipeline
-- Cleans and validates raw sales data from bronze layer
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
    product_name,
    category,
    quantity,
    unit_price,
    quantity * unit_price AS total_amount,
    payment_method,
    customer_id,
    transaction_time,
    CAST(transaction_time AS DATE) AS _date,
    NOW() AS _processed_at
FROM {{ ref('bronze.raw_sales') }}
WHERE quantity > 0
  AND unit_price > 0
{% if is_incremental() %}
  AND transaction_time > '{{ watermark("transaction_time") }}'
{% endif %}
