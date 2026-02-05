"""Execute quality tests against real data.

Quality tests run SQL queries against actual pipeline output data.
A test passes if the query returns zero rows (no violations found).

Example quality test:
```sql
-- @name: unique_transaction_ids
-- @description: Transaction IDs must be unique

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
import pandas as pd

from ..models import DiscoveredPipeline, DiscoveredTest, TestOutput, TestStatus
from .base import BaseTestExecutor


class QualityTestExecutor(BaseTestExecutor):
    """Execute quality tests against real data in S3/MinIO."""

    def __init__(
        self,
        workspace_path: Path,
        workspace_name: str | None = None,
    ) -> None:
        super().__init__(workspace_path)
        self.workspace_name = workspace_name or os.getenv("RATATOUILLE_WORKSPACE", "default")

    def execute(
        self,
        pipeline: DiscoveredPipeline,
        test: DiscoveredTest,
    ) -> TestOutput:
        """Execute a quality test against real data."""
        if test.sql is None:
            return TestOutput(
                name=test.config.name,
                description=test.config.description,
                test_type="quality",
                status=TestStatus.ERROR,
                severity=test.config.severity,
                message="No SQL content found in test file",
            )

        with self._time_execution() as timer:
            try:
                # Create DuckDB connection with S3 access
                conn = self._create_connection()

                # Compile SQL (replace {{ this }} with table path)
                sql = self._compile_sql(test.sql, pipeline)

                # Execute the query
                result_df = conn.execute(sql).fetchdf()
                row_count = len(result_df)

                conn.close()

                # Quality tests pass if no rows returned (no violations)
                passed = row_count == 0

                return TestOutput(
                    name=test.config.name,
                    description=test.config.description,
                    test_type="quality",
                    status=TestStatus.PASSED if passed else TestStatus.FAILED,
                    severity=test.config.severity,
                    data=result_df if row_count > 0 else None,
                    row_count=row_count,
                    sql=sql,
                    duration_ms=timer.duration_ms,
                    message=f"{row_count} violations found" if row_count > 0 else "No violations",
                )

            except Exception as e:
                return TestOutput(
                    name=test.config.name,
                    description=test.config.description,
                    test_type="quality",
                    status=TestStatus.ERROR,
                    severity=test.config.severity,
                    message=str(e),
                    duration_ms=timer.duration_ms,
                )

    def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create a DuckDB connection configured for S3/MinIO access."""
        conn = duckdb.connect(":memory:")

        # Configure S3 access
        endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "ratatouille")
        secret_key = os.getenv("MINIO_SECRET_KEY", "ratatouille123")

        # Extract host and port from endpoint
        endpoint_clean = endpoint.replace("http://", "").replace("https://", "")

        conn.execute(f"""
            SET s3_endpoint = '{endpoint_clean}';
            SET s3_access_key_id = '{access_key}';
            SET s3_secret_access_key = '{secret_key}';
            SET s3_use_ssl = false;
            SET s3_url_style = 'path';
        """)

        return conn

    def _compile_sql(self, sql: str, pipeline: DiscoveredPipeline) -> str:
        """Compile SQL by replacing template variables.

        Replaces:
        - {{ this }} - Path to the pipeline's output data
        - {{ ref('layer.name') }} - Path to another pipeline's data
        """
        # Get the S3 path for this pipeline
        bucket = f"ratatouille-{self.workspace_name}"
        this_path = f"s3://{bucket}/{pipeline.layer}/{pipeline.name}/*.parquet"

        # Replace {{ this }}
        sql = re.sub(r"\{\{\s*this\s*\}\}", f"'{this_path}'", sql)

        # Replace {{ ref('layer.name') }}
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
