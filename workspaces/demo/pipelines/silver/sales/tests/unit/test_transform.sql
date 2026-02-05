-- @name: test_basic_transformation
-- @description: Verify quantity * price = total_amount and text is uppercased
-- @mocks: mocks/bronze_sales.yaml
-- @expect_count: 2

-- Expected: Only valid records (T001, T002), with uppercase text and calculated totals
-- T001: 2 * 10.00 = 20.00
-- T002: 3 * 25.50 = 76.50
-- Invalid records (T003, T004, T005) should be filtered out
