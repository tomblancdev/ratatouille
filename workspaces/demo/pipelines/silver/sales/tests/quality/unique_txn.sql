-- @name: unique_transaction_ids
-- @description: Transaction IDs must be unique
-- @severity: error
-- @mocks: mocks/bronze_sales.yaml

SELECT
    txn_id,
    COUNT(*) as occurrences
FROM {{ this }}
GROUP BY txn_id
HAVING COUNT(*) > 1
