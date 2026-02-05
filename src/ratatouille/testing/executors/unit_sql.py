"""Execute unit SQL tests with mock data.

Unit tests run the pipeline's SQL transformation against mock data
injected into an in-memory DuckDB instance.

Optimized for DuckDB-native operations - minimal pandas usage.
Pandas only used for final display of small result sets.

Example unit test:
```sql
-- @name: test_basic_transformation
-- @description: Verify total calculation
-- @mocks: mocks/bronze_sales.yaml
-- @expect_count: 2
```
"""

import json
import re
import tempfile
from pathlib import Path

import duckdb

from ..mocks.loader import MockLoader
from ..models import (
    DiscoveredPipeline,
    DiscoveredTest,
    ExpectedResult,
    TestOutput,
    TestStatus,
)
from .base import BaseTestExecutor


class UnitSQLTestExecutor(BaseTestExecutor):
    """Execute unit SQL tests with mock data - DuckDB-native."""

    def __init__(self, workspace_path: Path) -> None:
        super().__init__(workspace_path)
        self.mock_loader = MockLoader()

    def execute(
        self,
        pipeline: DiscoveredPipeline,
        test: DiscoveredTest,
    ) -> TestOutput:
        """Execute a unit SQL test with mock data."""
        with self._time_execution() as timer:
            try:
                # Create in-memory DuckDB connection
                conn = self.mock_loader.create_connection()

                # Load mock data
                mocks_used = self._load_mocks(conn, pipeline, test)

                if not mocks_used:
                    conn.close()
                    return TestOutput(
                        name=test.config.name,
                        description=test.config.description,
                        test_type="unit_sql",
                        status=TestStatus.SKIPPED,
                        severity=test.config.severity,
                        message="No mock data found - add mocks to tests/mocks/",
                        duration_ms=timer.duration_ms,
                    )

                # Get and compile the pipeline SQL
                pipeline_sql = self._get_pipeline_sql(pipeline)
                if pipeline_sql is None:
                    conn.close()
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
                    mocks_used,
                )

                # Execute the transformation
                result = conn.execute(compiled_sql)
                rows = result.fetchall()
                columns = (
                    [desc[0] for desc in result.description]
                    if result.description
                    else []
                )
                row_count = len(rows)

                # Compare with expected results (using SQL)
                if test.config.expect:
                    passed, message = self._compare_results_sql(
                        conn,
                        rows,
                        columns,
                        test.config.expect,
                    )
                else:
                    passed = True
                    message = f"Executed successfully, {row_count} rows"

                conn.close()

                # Convert to DataFrame only for display (small result set)
                data = None
                if not passed or row_count <= 10:
                    import pandas as pd

                    data = pd.DataFrame(rows[:10], columns=columns)

                return TestOutput(
                    name=test.config.name,
                    description=test.config.description,
                    test_type="unit_sql",
                    status=TestStatus.PASSED if passed else TestStatus.FAILED,
                    severity=test.config.severity,
                    data=data,
                    row_count=row_count,
                    columns_checked=columns,
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

        mocks_dir = pipeline.mocks_path
        if not mocks_dir:
            mocks_dir = pipeline.path / "tests" / "mocks"

        for mock_path_str in test.config.mocks:
            if mock_path_str.startswith("mocks/"):
                mock_path = pipeline.path / "tests" / mock_path_str
            else:
                mock_path = mocks_dir / mock_path_str

            if not mock_path.exists():
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
        """Compile pipeline SQL for unit testing."""
        is_incremental = test.config.mode == "incremental"
        watermarks = test.config.watermarks

        # Remove metadata comments
        sql = re.sub(r"^--\s*@\w+:.*$", "", sql, flags=re.MULTILINE)

        # Replace {{ ref('layer.name') }} with mock table name
        def replace_ref(match: re.Match[str]) -> str:
            ref_str = match.group(1)
            table_name = ref_str.replace(".", "_")
            for avail in available_tables:
                if avail == table_name or avail.endswith(f"_{table_name}"):
                    return avail
            return table_name

        sql = re.sub(r"\{\{\s*ref\(['\"]([^'\"]+)['\"]\)\s*\}\}", replace_ref, sql)

        # Handle {{ is_incremental() }}
        if is_incremental:
            sql = re.sub(r"\{\{\s*is_incremental\(\)\s*\}\}", "true", sql)
        else:
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

        sql = re.sub(
            r"\{\{\s*watermark\(['\"]([^'\"]+)['\"]\)\s*\}\}", replace_watermark, sql
        )

        # Replace {{ this }}
        sql = re.sub(r"\{\{\s*this\s*\}\}", pipeline.name, sql)

        return sql.strip()

    def _compare_results_sql(
        self,
        conn: duckdb.DuckDBPyConnection,
        actual_rows: list,
        columns: list[str],
        expected: ExpectedResult,
    ) -> tuple[bool, str]:
        """Compare results using SQL - no pandas.

        Returns:
            Tuple of (passed, message)
        """
        actual_count = len(actual_rows)

        # Check row count
        if expected.row_count is not None:
            if actual_count != expected.row_count:
                return (
                    False,
                    f"Row count mismatch: expected {expected.row_count}, got {actual_count}",
                )

        # Check specific rows if provided
        if expected.rows is not None:
            expected_count = len(expected.rows)

            # Quick count check
            if actual_count != expected_count:
                return (
                    False,
                    f"Row count mismatch: expected {expected_count}, got {actual_count}",
                )

            # Create actual table
            if actual_rows:
                # Build VALUES clause
                cols_str = ", ".join(columns)
                values = []
                for row in actual_rows:
                    vals = []
                    for v in row:
                        if v is None:
                            vals.append("NULL")
                        elif isinstance(v, str):
                            vals.append(f"'{v}'")
                        else:
                            vals.append(str(v))
                    values.append(f"({', '.join(vals)})")

                conn.execute(f"""
                    CREATE TABLE _actual ({cols_str}) AS
                    SELECT * FROM (VALUES {", ".join(values)}) AS t({cols_str})
                """)

            # Determine columns to compare
            compare_cols = expected.columns or list(expected.rows[0].keys())

            # Create expected table via temp file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(expected.rows, f)
                temp_path = f.name
            try:
                conn.execute(f"""
                    CREATE TABLE _expected AS
                    SELECT * FROM read_json_auto('{temp_path}')
                """)
            finally:
                Path(temp_path).unlink(missing_ok=True)

            # Compare using SQL
            cols_select = ", ".join(compare_cols)

            # Count differences
            try:
                diff_result = conn.execute(f"""
                    SELECT COUNT(*) as diff_count FROM (
                        (SELECT {cols_select} FROM _actual EXCEPT SELECT {cols_select} FROM _expected)
                        UNION ALL
                        (SELECT {cols_select} FROM _expected EXCEPT SELECT {cols_select} FROM _actual)
                    )
                """).fetchone()

                diff_count = diff_result[0] if diff_result else 0

                if diff_count > 0:
                    return (False, f"Data mismatch: {diff_count} different rows")

            except Exception as e:
                return (False, f"Comparison error: {e}")

        return (True, f"All assertions passed ({actual_count} rows)")
