-- @name: positive_amounts
-- @description: All quantities and prices must be positive
-- @severity: error

SELECT
    txn_id,
    quantity,
    unit_price,
    total_amount,
    CASE
        WHEN quantity <= 0 THEN 'quantity <= 0'
        WHEN unit_price <= 0 THEN 'unit_price <= 0'
        WHEN total_amount <= 0 THEN 'total_amount <= 0'
    END as reason
FROM {{ this }}
WHERE quantity <= 0
   OR unit_price <= 0
   OR total_amount <= 0
