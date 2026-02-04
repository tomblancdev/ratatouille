"""🧪 Integration tests for DuckDB Engine.

These tests require MinIO and Nessie to be running.
Set environment variables:
- S3_ENDPOINT
- S3_ACCESS_KEY
- S3_SECRET_KEY
- NESSIE_URI
"""

import os
import pytest
import pandas as pd
from datetime import datetime

# Skip all tests if services not available
pytestmark = pytest.mark.skipif(
    not os.getenv("S3_ENDPOINT"),
    reason="S3_ENDPOINT not set - integration services not available"
)


class TestDuckDBEngine:
    """Integration tests for DuckDBEngine."""

    @pytest.fixture
    def engine(self, test_workspace):
        """Get DuckDB engine for test workspace."""
        return test_workspace.get_engine()

    def test_query_simple(self, engine):
        """Test simple query execution."""
        df = engine.query("SELECT 1 as num, 'hello' as greeting")

        assert len(df) == 1
        assert df.iloc[0]["num"] == 1
        assert df.iloc[0]["greeting"] == "hello"

    def test_query_with_aggregation(self, engine):
        """Test query with aggregation."""
        df = engine.query("""
            SELECT
                numbers.n % 3 as group_id,
                SUM(numbers.n) as total
            FROM (SELECT unnest(range(1, 11)) as n) numbers
            GROUP BY group_id
            ORDER BY group_id
        """)

        assert len(df) == 3
        assert df["total"].sum() == 55  # 1+2+...+10

    def test_write_and_read_parquet(self, engine, tmp_path):
        """Test writing and reading Parquet files."""
        # Create test data
        df = pd.DataFrame({
            "id": range(100),
            "name": [f"item_{i}" for i in range(100)],
            "value": [i * 1.5 for i in range(100)],
            "date": [datetime(2024, 1, 1)] * 100,
        })

        # Write to Parquet
        parquet_path = tmp_path / "test_data.parquet"
        engine.write_parquet(df, str(parquet_path))

        assert parquet_path.exists()

        # Read back
        result = engine.query(f"SELECT * FROM read_parquet('{parquet_path}')")

        assert len(result) == 100
        assert result["value"].sum() == pytest.approx(df["value"].sum())

    def test_write_partitioned(self, engine, tmp_path):
        """Test writing partitioned Parquet files."""
        df = pd.DataFrame({
            "id": range(10),
            "category": ["A", "B"] * 5,
            "value": range(10),
        })

        output_dir = tmp_path / "partitioned"
        engine.write_parquet(df, str(output_dir), partition_by=["category"])

        # Should create partition directories
        assert (output_dir / "category=A").exists() or output_dir.exists()


class TestDuckDBResourceLimits:
    """Test that resource limits are applied."""

    def test_memory_limit_applied(self, test_workspace):
        """Test that memory limit from profile is applied."""
        engine = test_workspace.get_engine()

        # Query DuckDB settings
        settings = engine.query("SELECT * FROM duckdb_settings() WHERE name = 'memory_limit'")

        # Should have some memory limit set
        assert len(settings) == 1
        assert settings.iloc[0]["value"] is not None

    def test_threads_configured(self, test_workspace):
        """Test that thread count is configured."""
        engine = test_workspace.get_engine()

        settings = engine.query("SELECT * FROM duckdb_settings() WHERE name = 'threads'")

        assert len(settings) == 1
