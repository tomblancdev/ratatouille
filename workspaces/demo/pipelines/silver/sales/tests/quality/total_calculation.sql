-- @name: total_calculation
-- @description: total_amount must equal quantity * unit_price
-- @severity: error

SELECT
    txn_id,
    quantity,
    unit_price,
    total_amount,
    ROUND(quantity * unit_price, 2) as expected_total,
    ABS(total_amount - quantity * unit_price) as difference
FROM {{ this }}
WHERE ABS(total_amount - quantity * unit_price) > 0.01
