"""🧪 Integration tests for Iceberg + Nessie REST Catalog.

These tests require Nessie and MinIO to be running.
Run with: podman compose up -d

Set environment variables:
- NESSIE_URI
- S3_ENDPOINT
- S3_ACCESS_KEY
- S3_SECRET_KEY
"""

import os
import uuid
from datetime import datetime

import pandas as pd
import pytest

from ratatouille.catalog.iceberg import IcebergCatalog
from ratatouille.catalog.nessie import NessieClient
from ratatouille.core import iceberg

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
    branch_name = f"test/iceberg-{uuid.uuid4().hex[:8]}"
    nessie.create_branch(branch_name, from_branch="main")
    yield branch_name
    # Cleanup
    try:
        nessie.delete_branch(branch_name)
    except Exception:
        pass


@pytest.fixture
def catalog(test_branch):
    """Get IcebergCatalog for test branch."""
    return IcebergCatalog.from_env(branch=test_branch)


@pytest.fixture
def sample_df():
    """Create sample test data."""
    return pd.DataFrame(
        {
            "id": range(1, 11),
            "name": [f"item_{i}" for i in range(1, 11)],
            "value": [i * 10.5 for i in range(1, 11)],
            "created_at": [datetime(2024, 1, i) for i in range(1, 11)],
        }
    )


class TestIcebergCatalogBasics:
    """Test basic Iceberg catalog operations."""

    def test_create_and_read_table(self, catalog, sample_df, test_branch):
        """Test creating and reading an Iceberg table."""
        table_name = f"bronze.test_table_{uuid.uuid4().hex[:8]}"

        # Create table
        result = catalog.create_table(table_name, sample_df)
        assert result == table_name

        # Read back
        df = catalog.read_table(table_name)
        assert len(df) == len(sample_df)
        assert df["id"].sum() == sample_df["id"].sum()

    def test_append_data(self, catalog, sample_df, test_branch):
        """Test appending data to a table."""
        table_name = f"bronze.append_test_{uuid.uuid4().hex[:8]}"

        # Create initial table
        catalog.create_table(table_name, sample_df)

        # Append more data
        new_df = pd.DataFrame(
            {
                "id": range(11, 21),
                "name": [f"item_{i}" for i in range(11, 21)],
                "value": [i * 10.5 for i in range(11, 21)],
                "created_at": [datetime(2024, 1, 15)] * 10,
            }
        )
        rows_appended = catalog.append(table_name, new_df)

        assert rows_appended == 10

        # Verify total
        df = catalog.read_table(table_name)
        assert len(df) == 20

    def test_overwrite_data(self, catalog, sample_df, test_branch):
        """Test overwriting table data."""
        table_name = f"bronze.overwrite_test_{uuid.uuid4().hex[:8]}"

        # Create initial table
        catalog.create_table(table_name, sample_df)

        # Overwrite with new data
        new_df = pd.DataFrame(
            {
                "id": [100, 200],
                "name": ["new_1", "new_2"],
                "value": [1000.0, 2000.0],
                "created_at": [datetime(2024, 6, 1)] * 2,
            }
        )
        rows = catalog.overwrite(table_name, new_df)

        assert rows == 2

        # Verify
        df = catalog.read_table(table_name)
        assert len(df) == 2
        assert df["id"].sum() == 300

    def test_merge_upsert(self, catalog, sample_df, test_branch):
        """Test merge (upsert) operation."""
        table_name = f"bronze.merge_test_{uuid.uuid4().hex[:8]}"

        # Create initial table
        catalog.create_table(table_name, sample_df)

        # Merge with updates and new records
        merge_df = pd.DataFrame(
            {
                "id": [1, 2, 100],  # 1,2 = updates, 100 = new
                "name": ["updated_1", "updated_2", "new_100"],
                "value": [999.0, 888.0, 777.0],
                "created_at": [datetime(2024, 6, 1)] * 3,
            }
        )
        stats = catalog.merge(table_name, merge_df, merge_keys=["id"])

        assert stats["inserted"] == 1  # id=100
        assert stats["updated"] == 2  # id=1,2

        # Verify final state
        df = catalog.read_table(table_name)
        assert len(df) == 11  # 10 original + 1 new - 0 (updates replace)


class TestIcebergBranchIsolation:
    """Test that branches provide proper isolation."""

    def test_branch_isolation(self, nessie, sample_df):
        """Test that writes on one branch don't affect another."""
        branch_a = f"test/isolation-a-{uuid.uuid4().hex[:8]}"
        branch_b = f"test/isolation-b-{uuid.uuid4().hex[:8]}"

        try:
            # Create two branches
            nessie.create_branch(branch_a, from_branch="main")
            nessie.create_branch(branch_b, from_branch="main")

            catalog_a = IcebergCatalog.from_env(branch=branch_a)
            catalog_b = IcebergCatalog.from_env(branch=branch_b)

            table_name = f"bronze.isolation_test_{uuid.uuid4().hex[:8]}"

            # Write to branch A
            catalog_a.create_table(table_name, sample_df)

            # Table should exist on A
            assert catalog_a.table_exists(table_name)

            # Table should NOT exist on B (isolation)
            assert not catalog_b.table_exists(table_name)

        finally:
            # Cleanup
            for branch in [branch_a, branch_b]:
                try:
                    nessie.delete_branch(branch)
                except Exception:
                    pass


class TestIcebergTimeTravel:
    """Test time travel capabilities."""

    def test_snapshot_history(self, catalog, sample_df, test_branch):
        """Test reading snapshot history."""
        table_name = f"bronze.history_test_{uuid.uuid4().hex[:8]}"

        # Create table (snapshot 1)
        catalog.create_table(table_name, sample_df)

        # Append data (snapshot 2)
        catalog.append(
            table_name,
            pd.DataFrame(
                {
                    "id": [11],
                    "name": ["item_11"],
                    "value": [110.0],
                    "created_at": [datetime(2024, 1, 15)],
                }
            ),
        )

        # Get history
        history = catalog.table_history(table_name)

        # Should have at least 2 snapshots
        assert len(history) >= 2
        assert "snapshot_id" in history.columns
        assert "timestamp" in history.columns

    def test_read_at_snapshot(self, catalog, sample_df, test_branch):
        """Test reading table at specific snapshot."""
        table_name = f"bronze.timetravel_test_{uuid.uuid4().hex[:8]}"

        # Create table with initial data
        catalog.create_table(table_name, sample_df)

        # Get first snapshot
        history = catalog.table_history(table_name)
        first_snapshot = history.iloc[0]["snapshot_id"]

        # Append more data
        catalog.append(
            table_name,
            pd.DataFrame(
                {
                    "id": [11, 12],
                    "name": ["new_1", "new_2"],
                    "value": [1.0, 2.0],
                    "created_at": [datetime(2024, 1, 15)] * 2,
                }
            ),
        )

        # Current state should have more rows
        current_df = catalog.read_table(table_name)
        assert len(current_df) == 12

        # Reading at first snapshot should have original count
        old_df = catalog.read_snapshot(table_name, first_snapshot)
        assert len(old_df) == 10


class TestCoreIcebergModule:
    """Test the core iceberg module functions."""

    def test_core_create_and_read(self, test_branch, sample_df):
        """Test core iceberg functions with branch parameter."""
        # Clear cache to ensure fresh catalog
        iceberg.clear_catalog_cache()

        table_name = f"bronze.core_test_{uuid.uuid4().hex[:8]}"

        # Create table using core module
        result = iceberg.create_table(table_name, sample_df, branch=test_branch)
        assert result == table_name

        # Read back
        df = iceberg.read_table(table_name, branch=test_branch)
        assert len(df) == 10

    def test_core_list_tables(self, test_branch, sample_df):
        """Test listing tables."""
        iceberg.clear_catalog_cache()

        table_name = f"bronze.list_test_{uuid.uuid4().hex[:8]}"
        iceberg.create_table(table_name, sample_df, branch=test_branch)

        tables = iceberg.list_tables("bronze", branch=test_branch)
        assert table_name.split(".")[1] in tables
