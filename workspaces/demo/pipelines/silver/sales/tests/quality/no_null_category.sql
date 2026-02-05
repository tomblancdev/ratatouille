-- @name: no_null_category
-- @description: Category should never be null
-- @severity: warn
-- @mocks: mocks/bronze_sales_with_nulls.yaml

SELECT
    txn_id,
    category
FROM {{ this }}
WHERE category IS NULL
