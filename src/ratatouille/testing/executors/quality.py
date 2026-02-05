"""Execute quality tests against real data or mocks.

Quality tests run SQL queries that check data quality.
A test passes if the query returns zero rows (no violations found).

When mocks are specified, tests run against mock data first to verify
the test logic works correctly. Then in production, the same test
runs against real data.

Example quality test:
```sql
-- @name: unique_transaction_ids
-- @description: Transaction IDs must be unique
-- @mocks: mocks/bronze_sales.yaml

SELECT txn_id, COUNT(*) as occurrences
FROM {{ this }}
GROUP BY txn_id
HAVING COUNT(*) > 1
```
"""

import os
import re
from pathlib import Path

import duckdb

from ..models import DiscoveredPipeline, DiscoveredTest, TestOutput, TestStatus
from ..mocks.loader import MockLoader
from .base import BaseTestExecutor


class QualityTestExecutor(BaseTestExecutor):
    """Execute quality tests - against mocks or real S3 data."""

    def __init__(
        self,
        workspace_path: Path,
        workspace_name: str | None = None,
    ) -> None:
        super().__init__(workspace_path)
        self.workspace_name = workspace_name or os.getenv("RATATOUILLE_WORKSPACE", "default")
        self.mock_loader = MockLoader()

    def execute(
        self,
        pipeline: DiscoveredPipeline,
        test: DiscoveredTest,
    ) -> TestOutput:
        """Execute a quality test.

        If mocks are specified, runs against mock data.
        Otherwise, runs against real S3 data.
        """
        if test.sql is None:
            return TestOutput(
                name=test.config.name,
                description=test.config.description,
                test_type="quality",
                status=TestStatus.ERROR,
                severity=test.config.severity,
                message="No SQL content found in test file",
            )

        # Determine if we should use mocks
        use_mocks = bool(test.config.mocks)

        with self._time_execution() as timer:
            try:
                if use_mocks:
                    return self._execute_with_mocks(pipeline, test, timer)
                else:
                    return self._execute_against_s3(pipeline, test, timer)

            except Exception as e:
                error_msg = str(e)

                # Handle "no files found" gracefully
                if "No files found" in error_msg or "does not exist" in error_msg:
                    return TestOutput(
                        name=test.config.name,
                        description=test.config.description,
                        test_type="quality",
                        status=TestStatus.SKIPPED,
                        severity=test.config.severity,
                        message="No data available - run pipeline first or add mocks",
                        duration_ms=timer.duration_ms,
                    )

                return TestOutput(
                    name=test.config.name,
                    description=test.config.description,
                    test_type="quality",
                    status=TestStatus.ERROR,
                    severity=test.config.severity,
                    message=error_msg,
                    duration_ms=timer.duration_ms,
                )

    def _execute_with_mocks(
        self,
        pipeline: DiscoveredPipeline,
        test: DiscoveredTest,
        timer: "ExecutionTimer",
    ) -> TestOutput:
        """Execute quality test against mock data."""
        conn = self.mock_loader.create_connection()

        # Load mocks
        mocks_used = self._load_mocks(conn, pipeline, test)

        # Create the "this" table from the pipeline transformation
        # by running the pipeline SQL against mock data
        pipeline_sql = self._get_pipeline_sql(pipeline)
        if pipeline_sql:
            compiled_pipeline = self._compile_pipeline_sql(
                pipeline_sql, pipeline, mocks_used
            )
            try:
                conn.execute(f"CREATE TABLE _this AS {compiled_pipeline}")
            except Exception as e:
                conn.close()
                return TestOutput(
                    name=test.config.name,
                    description=test.config.description,
                    test_type="quality",
                    status=TestStatus.ERROR,
                    severity=test.config.severity,
                    message=f"Pipeline SQL error: {e}",
                    duration_ms=timer.duration_ms,
                    mocks_used=mocks_used,
                )
        else:
            # No pipeline SQL - use the first mock as "this"
            if mocks_used:
                conn.execute(f"CREATE TABLE _this AS SELECT * FROM {mocks_used[0]}")

        # Compile and execute the quality test SQL
        test_sql = self._compile_test_sql(test.sql, "_this")
        result = conn.execute(test_sql)

        # Get results - DuckDB native, no pandas
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description] if result.description else []
        row_count = len(rows)

        conn.close()

        # Quality tests pass if no rows returned (no violations)
        passed = row_count == 0

        # Format data for output (only if failures)
        data = None
        if row_count > 0:
            import pandas as pd  # Only for display
            data = pd.DataFrame(rows, columns=columns)

        return TestOutput(
            name=test.config.name,
            description=test.config.description,
            test_type="quality",
            status=TestStatus.PASSED if passed else TestStatus.FAILED,
            severity=test.config.severity,
            data=data,
            row_count=row_count,
            columns_checked=columns,
            sql=test_sql,
            mocks_used=mocks_used,
            duration_ms=timer.duration_ms,
            message=f"{row_count} violations found" if row_count > 0 else "No violations",
        )

    def _execute_against_s3(
        self,
        pipeline: DiscoveredPipeline,
        test: DiscoveredTest,
        timer: "ExecutionTimer",
    ) -> TestOutput:
        """Execute quality test against real S3 data."""
        conn = self._create_s3_connection()

        # Compile SQL with S3 path
        sql = self._compile_test_sql_for_s3(test.sql, pipeline)

        # Execute
        result = conn.execute(sql)
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description] if result.description else []
        row_count = len(rows)

        conn.close()

        passed = row_count == 0

        # Format data for output
        data = None
        if row_count > 0:
            import pandas as pd
            data = pd.DataFrame(rows, columns=columns)

        return TestOutput(
            name=test.config.name,
            description=test.config.description,
            test_type="quality",
            status=TestStatus.PASSED if passed else TestStatus.FAILED,
            severity=test.config.severity,
            data=data,
            row_count=row_count,
            columns_checked=columns,
            sql=sql,
            duration_ms=timer.duration_ms,
            message=f"{row_count} violations found" if row_count > 0 else "No violations",
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
        """Get the pipeline's SQL content."""
        if pipeline.pipeline_file and pipeline.pipeline_file.suffix == ".sql":
            return pipeline.pipeline_file.read_text()
        return None

    def _compile_pipeline_sql(
        self,
        sql: str,
        pipeline: DiscoveredPipeline,
        available_tables: list[str],
    ) -> str:
        """Compile pipeline SQL with mock table references."""
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

        # Remove incremental blocks for testing (always full refresh)
        sql = re.sub(
            r"\{%\s*if\s+is_incremental\(\)\s*%\}.*?\{%\s*endif\s*%\}",
            "",
            sql,
            flags=re.DOTALL,
        )

        # Replace other template vars
        sql = re.sub(r"\{\{\s*this\s*\}\}", pipeline.name, sql)
        sql = re.sub(r"\{\{\s*is_incremental\(\)\s*\}\}", "false", sql)

        return sql.strip()

    def _compile_test_sql(self, sql: str, this_table: str) -> str:
        """Compile test SQL replacing {{ this }} with the table name."""
        return re.sub(r"\{\{\s*this\s*\}\}", this_table, sql)

    def _compile_test_sql_for_s3(self, sql: str, pipeline: DiscoveredPipeline) -> str:
        """Compile test SQL with S3 paths."""
        bucket = f"ratatouille-{self.workspace_name}"
        this_path = f"s3://{bucket}/{pipeline.layer}/{pipeline.name}/*.parquet"

        sql = re.sub(r"\{\{\s*this\s*\}\}", f"'{this_path}'", sql)

        def replace_ref(match: re.Match[str]) -> str:
            ref_str = match.group(1)
            if "." in ref_str:
                layer, name = ref_str.split(".", 1)
            else:
                layer = pipeline.layer
                name = ref_str
            ref_path = f"s3://{bucket}/{layer}/{name}/*.parquet"
            return f"'{ref_path}'"

        sql = re.sub(r"\{\{\s*ref\(['\"]([^'\"]+)['\"]\)\s*\}\}", replace_ref, sql)

        return sql

    def _create_s3_connection(self) -> duckdb.DuckDBPyConnection:
        """Create a DuckDB connection with S3 configured."""
        conn = duckdb.connect(":memory:")

        endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "ratatouille")
        secret_key = os.getenv("MINIO_SECRET_KEY", "ratatouille123")

        endpoint_clean = endpoint.replace("http://", "").replace("https://", "")

        conn.execute(f"""
            SET s3_endpoint = '{endpoint_clean}';
            SET s3_access_key_id = '{access_key}';
            SET s3_secret_access_key = '{secret_key}';
            SET s3_use_ssl = false;
            SET s3_url_style = 'path';
        """)

        return conn


# Import for type hint
from .base import ExecutionTimer
