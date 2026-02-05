"""🧪 Integration tests for DuckDB Iceberg reads via iceberg_scan().

These tests verify that DuckDB can read Iceberg tables using
metadata paths resolved via NessieClient.

Required services: Nessie, MinIO
Run with: podman compose up -d
"""

import os
import uuid
from datetime import datetime

import pandas as pd
import pytest

from ratatouille.catalog.iceberg import IcebergCatalog
from ratatouille.catalog.nessie import NessieClient, TableNotFoundError
from ratatouille.engine.duckdb import DuckDBEngine

# Skip all tests if services not available
pytestmark = pytest.mark.skipif(
    not os.getenv("NESSIE_URI") or not os.getenv("S3_ENDPOINT"),
    reason="NESSIE_URI or S3_ENDPOINT not set - services not available",
)


@pytest.fixture
def nessie():
    """Get NessieClient instance."""
    uri = os.getenv("NESSIE_URI", "http://localhost:19120/api/v2")
    client = NessieClient(uri)
    yield client
    client.close()


@pytest.fixture
def test_branch(nessie):
    """Create a unique test branch."""
    branch_name = f"test/duckdb-{uuid.uuid4().hex[:8]}"
    nessie.create_branch(branch_name, from_branch="main")
    yield branch_name
    # Cleanup
    try:
        nessie.delete_branch(branch_name)
    except Exception:
        pass


@pytest.fixture
def engine(test_branch):
    """Get DuckDB engine configured for test branch."""
    return DuckDBEngine(
        s3_endpoint=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
        s3_access_key=os.getenv("S3_ACCESS_KEY", "ratatouille"),
        s3_secret_key=os.getenv("S3_SECRET_KEY", "ratatouille123"),
        nessie_uri=os.getenv("NESSIE_URI", "http://localhost:19120/api/v2"),
        nessie_branch=test_branch,
    )


@pytest.fixture
def catalog(test_branch):
    """Get IcebergCatalog for test branch."""
    return IcebergCatalog.from_env(branch=test_branch)


@pytest.fixture
def sample_df():
    """Create sample test data."""
    return pd.DataFrame(
        {
            "id": range(1, 101),
            "category": ["A", "B", "C", "D"] * 25,
            "amount": [i * 1.5 for i in range(1, 101)],
            "created_at": [datetime(2024, 1, (i % 28) + 1) for i in range(1, 101)],
        }
    )


class TestDuckDBIcebergReads:
    """Test DuckDB Iceberg read operations."""

    def test_read_iceberg_basic(self, engine, catalog, sample_df, test_branch):
        """Test basic Iceberg table read via DuckDB."""
        table_name = f"bronze.duckdb_test_{uuid.uuid4().hex[:8]}"

        # Create table via PyIceberg
        catalog.create_table(table_name, sample_df)

        # Read via DuckDB
        df = engine.read_iceberg(table_name, branch=test_branch)

        assert len(df) == 100
        assert set(df.columns) == {"id", "category", "amount", "created_at"}
        assert df["amount"].sum() == pytest.approx(sample_df["amount"].sum())

    def test_read_iceberg_arrow(self, engine, catalog, sample_df, test_branch):
        """Test reading Iceberg table as Arrow (memory efficient)."""
        table_name = f"bronze.arrow_test_{uuid.uuid4().hex[:8]}"

        catalog.create_table(table_name, sample_df)

        # Read as Arrow
        arrow_table = engine.read_iceberg_arrow(table_name, branch=test_branch)

        assert arrow_table.num_rows == 100
        assert set(arrow_table.column_names) == {"id", "category", "amount", "created_at"}

    def test_iceberg_sql_fragment(self, engine, catalog, sample_df, test_branch):
        """Test using iceberg_sql() in custom queries."""
        table_name = f"bronze.sql_frag_test_{uuid.uuid4().hex[:8]}"

        catalog.create_table(table_name, sample_df)

        # Get SQL fragment
        sql_frag = engine.iceberg_sql(table_name, branch=test_branch)

        assert "iceberg_scan(" in sql_frag
        assert "metadata.json" in sql_frag or "metadata/" in sql_frag

        # Use in custom query
        df = engine.query(f"""
            SELECT category, SUM(amount) as total
            FROM {sql_frag}
            GROUP BY category
            ORDER BY category
        """)

        assert len(df) == 4  # A, B, C, D
        assert df["total"].sum() == pytest.approx(sample_df["amount"].sum())

    def test_iceberg_with_filter(self, engine, catalog, sample_df, test_branch):
        """Test Iceberg reads with WHERE clause."""
        table_name = f"bronze.filter_test_{uuid.uuid4().hex[:8]}"

        catalog.create_table(table_name, sample_df)

        sql_frag = engine.iceberg_sql(table_name, branch=test_branch)

        # Read with filter
        df = engine.query(f"""
            SELECT * FROM {sql_frag}
            WHERE category = 'A' AND amount > 50
        """)

        assert len(df) > 0
        assert all(df["category"] == "A")
        assert all(df["amount"] > 50)

    def test_iceberg_aggregation(self, engine, catalog, sample_df, test_branch):
        """Test aggregation queries on Iceberg tables."""
        table_name = f"bronze.agg_test_{uuid.uuid4().hex[:8]}"

        catalog.create_table(table_name, sample_df)

        sql_frag = engine.iceberg_sql(table_name, branch=test_branch)

        df = engine.query(f"""
            SELECT
                category,
                COUNT(*) as count,
                SUM(amount) as total,
                AVG(amount) as avg_amount
            FROM {sql_frag}
            GROUP BY category
            ORDER BY category
        """)

        assert len(df) == 4
        assert df["count"].sum() == 100
        assert df.iloc[0]["category"] == "A"


class TestDuckDBIcebergBranchIsolation:
    """Test that DuckDB reads respect branch isolation."""

    def test_reads_respect_branch(self, nessie, sample_df):
        """Test that DuckDB reads only see data from correct branch."""
        branch_a = f"test/duck-a-{uuid.uuid4().hex[:8]}"
        branch_b = f"test/duck-b-{uuid.uuid4().hex[:8]}"

        try:
            nessie.create_branch(branch_a, from_branch="main")
            nessie.create_branch(branch_b, from_branch="main")

            catalog_a = IcebergCatalog.from_env(branch=branch_a)

            table_name = f"bronze.branch_iso_{uuid.uuid4().hex[:8]}"

            # Write only to branch A
            catalog_a.create_table(table_name, sample_df)

            # Engine for branch A
            engine_a = DuckDBEngine(
                s3_endpoint=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
                s3_access_key=os.getenv("S3_ACCESS_KEY", "ratatouille"),
                s3_secret_key=os.getenv("S3_SECRET_KEY", "ratatouille123"),
                nessie_uri=os.getenv("NESSIE_URI", "http://localhost:19120/api/v2"),
                nessie_branch=branch_a,
            )

            # Engine for branch B
            engine_b = DuckDBEngine(
                s3_endpoint=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
                s3_access_key=os.getenv("S3_ACCESS_KEY", "ratatouille"),
                s3_secret_key=os.getenv("S3_SECRET_KEY", "ratatouille123"),
                nessie_uri=os.getenv("NESSIE_URI", "http://localhost:19120/api/v2"),
                nessie_branch=branch_b,
            )

            # Should succeed on branch A
            df = engine_a.read_iceberg(table_name)
            assert len(df) == 100

            # Should fail on branch B (table doesn't exist there)
            with pytest.raises(TableNotFoundError):
                engine_b.read_iceberg(table_name)

        finally:
            for branch in [branch_a, branch_b]:
                try:
                    nessie.delete_branch(branch)
                except Exception:
                    pass


class TestDuckDBIcebergErrors:
    """Test error handling for Iceberg operations."""

    def test_read_nonexistent_table(self, engine, test_branch):
        """Test reading a table that doesn't exist."""
        with pytest.raises(TableNotFoundError):
            engine.read_iceberg("bronze.nonexistent_table_12345")

    def test_engine_without_nessie_uri(self):
        """Test that engine without Nessie URI raises helpful error."""
        engine = DuckDBEngine(
            s3_endpoint=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
            s3_access_key=os.getenv("S3_ACCESS_KEY", "ratatouille"),
            s3_secret_key=os.getenv("S3_SECRET_KEY", "ratatouille123"),
            nessie_uri=None,  # No Nessie!
        )

        with pytest.raises(ValueError, match="Nessie URI not configured"):
            engine.read_iceberg("bronze.some_table")
