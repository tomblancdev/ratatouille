"""Execute unit SQL tests with mock data.

Unit tests run the pipeline's SQL transformation against mock data
injected into an in-memory DuckDB instance.

Example unit test:
```sql
-- @name: test_basic_transformation
-- @description: Verify total calculation
-- @mocks: mocks/bronze_sales.yaml

-- @expect:
--   - txn_id: "T001"
--     total_amount: 20.00
-- @expect_columns: [txn_id, total_amount]
```
"""

import re
from pathlib import Path

import duckdb
import pandas as pd

from ..models import (
    DiscoveredPipeline,
    DiscoveredTest,
    ExpectedResult,
    TestOutput,
    TestStatus,
)
from ..mocks.loader import MockLoader
from .base import BaseTestExecutor


class UnitSQLTestExecutor(BaseTestExecutor):
    """Execute unit SQL tests with mock data."""

    def __init__(self, workspace_path: Path) -> None:
        super().__init__(workspace_path)
        self.mock_loader = MockLoader()

    def execute(
        self,
        pipeline: DiscoveredPipeline,
        test: DiscoveredTest,
    ) -> TestOutput:
        """Execute a unit SQL test with mock data."""
        if test.sql is None:
            return TestOutput(
                name=test.config.name,
                description=test.config.description,
                test_type="unit_sql",
                status=TestStatus.ERROR,
                severity=test.config.severity,
                message="No SQL content found in test file",
            )

        with self._time_execution() as timer:
            try:
                # Create in-memory DuckDB connection
                conn = self.mock_loader.create_connection()

                # Load mock data
                mocks_used = self._load_mocks(conn, pipeline, test)

                # Get and compile the pipeline SQL
                pipeline_sql = self._get_pipeline_sql(pipeline)
                if pipeline_sql is None:
                    return TestOutput(
                        name=test.config.name,
                        description=test.config.description,
                        test_type="unit_sql",
                        status=TestStatus.ERROR,
                        severity=test.config.severity,
                        message="Pipeline SQL not found",
                        duration_ms=timer.duration_ms,
                    )

                # Compile with mock table references
                compiled_sql = self._compile_sql(
                    pipeline_sql,
                    pipeline,
                    test,
                    list(self.mock_loader.get_loaded_tables().keys()),
                )

                # Execute the transformation
                result_df = conn.execute(compiled_sql).fetchdf()

                conn.close()

                # Compare with expected results
                if test.config.expect:
                    passed, message, data = self._compare_results(
                        result_df,
                        test.config.expect,
                    )
                else:
                    # No expected result - just check it ran successfully
                    passed = True
                    message = f"Executed successfully, {len(result_df)} rows"
                    data = result_df.head(5) if len(result_df) > 0 else None

                return TestOutput(
                    name=test.config.name,
                    description=test.config.description,
                    test_type="unit_sql",
                    status=TestStatus.PASSED if passed else TestStatus.FAILED,
                    severity=test.config.severity,
                    data=data,
                    row_count=len(result_df),
                    mocks_used=mocks_used,
                    sql=compiled_sql,
                    duration_ms=timer.duration_ms,
                    message=message,
                )

            except Exception as e:
                return TestOutput(
                    name=test.config.name,
                    description=test.config.description,
                    test_type="unit_sql",
                    status=TestStatus.ERROR,
                    severity=test.config.severity,
                    message=str(e),
                    duration_ms=timer.duration_ms,
                )

    def _load_mocks(
        self,
        conn: duckdb.DuckDBPyConnection,
        pipeline: DiscoveredPipeline,
        test: DiscoveredTest,
    ) -> list[str]:
        """Load mock data files into DuckDB."""
        mocks_used = []

        # Get the mocks directory
        mocks_dir = pipeline.mocks_path
        if not mocks_dir:
            mocks_dir = pipeline.path / "tests" / "mocks"

        for mock_path_str in test.config.mocks:
            # Resolve path relative to test file or mocks directory
            if mock_path_str.startswith("mocks/"):
                mock_path = pipeline.path / "tests" / mock_path_str
            else:
                mock_path = mocks_dir / mock_path_str

            if not mock_path.exists():
                # Try relative to test file
                mock_path = test.path.parent.parent / mock_path_str

            if mock_path.exists():
                tables = self.mock_loader.load_file(conn, mock_path)
                mocks_used.extend(tables)

        return mocks_used

    def _get_pipeline_sql(self, pipeline: DiscoveredPipeline) -> str | None:
        """Read the pipeline's SQL content."""
        if pipeline.pipeline_file and pipeline.pipeline_file.suffix == ".sql":
            return pipeline.pipeline_file.read_text()
        return None

    def _compile_sql(
        self,
        sql: str,
        pipeline: DiscoveredPipeline,
        test: DiscoveredTest,
        available_tables: list[str],
    ) -> str:
        """Compile pipeline SQL for unit testing.

        - Replace {{ ref(...) }} with mock table names
        - Handle {{ is_incremental() }} based on test mode
        - Replace {{ watermark(...) }} with test values
        """
        is_incremental = test.config.mode == "incremental"
        watermarks = test.config.watermarks

        # Replace {{ ref('layer.name') }} with mock table name
        def replace_ref(match: re.Match[str]) -> str:
            ref_str = match.group(1)
            # Convert to table name format
            table_name = ref_str.replace(".", "_")
            # Find matching table in available tables
            for avail in available_tables:
                if avail == table_name or avail.endswith(f"_{table_name}"):
                    return avail
            # Return as-is if not found (will error at runtime)
            return table_name

        sql = re.sub(r"\{\{\s*ref\(['\"]([^'\"]+)['\"]\)\s*\}\}", replace_ref, sql)

        # Handle {{ is_incremental() }}
        if is_incremental:
            sql = re.sub(r"\{\{\s*is_incremental\(\)\s*\}\}", "true", sql)
        else:
            # Remove incremental blocks entirely
            sql = re.sub(
                r"\{%\s*if\s+is_incremental\(\)\s*%\}.*?\{%\s*endif\s*%\}",
                "",
                sql,
                flags=re.DOTALL,
            )
            sql = re.sub(r"\{\{\s*is_incremental\(\)\s*\}\}", "false", sql)

        # Replace {{ watermark('column') }}
        def replace_watermark(match: re.Match[str]) -> str:
            column = match.group(1)
            return watermarks.get(column, "1970-01-01 00:00:00")

        sql = re.sub(r"\{\{\s*watermark\(['\"]([^'\"]+)['\"]\)\s*\}\}", replace_watermark, sql)

        # Replace {{ this }} with pipeline name
        sql = re.sub(r"\{\{\s*this\s*\}\}", pipeline.name, sql)

        # Remove metadata comments
        sql = re.sub(r"^--\s*@\w+:.*$", "", sql, flags=re.MULTILINE)

        return sql.strip()

    def _compare_results(
        self,
        actual: pd.DataFrame,
        expected: ExpectedResult,
    ) -> tuple[bool, str, pd.DataFrame | None]:
        """Compare actual results with expected.

        Returns:
            Tuple of (passed, message, data_to_show)
        """
        # Check row count
        if expected.row_count is not None:
            if len(actual) != expected.row_count:
                return (
                    False,
                    f"Row count mismatch: expected {expected.row_count}, got {len(actual)}",
                    actual.head(10),
                )

        # Check specific rows
        if expected.rows is not None:
            expected_df = pd.DataFrame(expected.rows)

            # Select columns to compare
            cols = expected.columns or list(expected_df.columns)

            # Filter actual to only expected columns
            try:
                actual_subset = actual[cols].reset_index(drop=True)
            except KeyError as e:
                missing = set(cols) - set(actual.columns)
                return (
                    False,
                    f"Missing columns in output: {missing}",
                    actual.head(5),
                )

            expected_subset = expected_df[cols].reset_index(drop=True)

            # Sort for comparison
            order_by = expected.order_by or cols
            actual_sorted = actual_subset.sort_values(by=order_by).reset_index(drop=True)
            expected_sorted = expected_subset.sort_values(by=order_by).reset_index(drop=True)

            # Compare
            try:
                pd.testing.assert_frame_equal(
                    actual_sorted,
                    expected_sorted,
                    check_dtype=False,
                    atol=expected.tolerance,
                )
                return (True, "All assertions passed", actual_sorted.head(5))
            except AssertionError as e:
                # Find differences
                diff_msg = str(e)[:200]
                return (
                    False,
                    f"Data mismatch: {diff_msg}",
                    actual_sorted,
                )

        return (True, f"Executed successfully, {len(actual)} rows", actual.head(5))
