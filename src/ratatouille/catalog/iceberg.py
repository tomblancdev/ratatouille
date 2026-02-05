"""🧊 Iceberg Catalog - Branch-aware table operations via Nessie.

Provides a high-level interface for Iceberg table operations
with workspace/branch isolation via Nessie REST catalog.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import pyarrow as pa
from pyiceberg.catalog import load_catalog


def _fix_timestamp_precision(df: pd.DataFrame) -> pd.DataFrame:
    """Convert nanosecond timestamps to microseconds for Iceberg compatibility."""
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype("datetime64[us]")
    return df


class IcebergCatalog:
    """Branch-aware Iceberg catalog using Nessie REST.

    Each instance is bound to a specific branch, providing
    workspace isolation for data operations.

    Example:
        catalog = IcebergCatalog(
            nessie_uri="http://localhost:19120/api/v2",
            branch="workspace/acme",
            warehouse="s3://warehouse/",
            s3_config={
                "endpoint": "http://localhost:9000",
                "access_key": "ratatouille",
                "secret_key": "ratatouille123",
            }
        )

        # Create and write table
        catalog.create_table("bronze.sales", df, partition_by=["year"])
        catalog.append("bronze.sales", more_df)

        # Read table
        df = catalog.read_table("bronze.sales")
    """

    def __init__(
        self,
        nessie_uri: str,
        branch: str,
        warehouse: str,
        s3_config: dict[str, str],
    ):
        """Initialize Iceberg catalog.

        Args:
            nessie_uri: Nessie API v2 URI
            branch: Branch name for this catalog instance
            warehouse: S3 warehouse path (e.g., "s3://warehouse/")
            s3_config: S3 configuration dict with:
                - endpoint: S3 endpoint URL
                - access_key: S3 access key
                - secret_key: S3 secret key
        """
        self.nessie_uri = nessie_uri
        self.branch = branch
        self.warehouse = warehouse
        self.s3_config = s3_config
        self._catalog = None

    @property
    def catalog(self):
        """Get the PyIceberg catalog (lazy initialized)."""
        if self._catalog is None:
            self._catalog = self._create_catalog()
        return self._catalog

    def _create_catalog(self):
        """Create a PyIceberg RestCatalog pointing to Nessie."""
        # Build catalog config
        config = {
            "type": "rest",
            "uri": f"{self.nessie_uri.rstrip('/')}/iceberg",
            "ref": self.branch,
            "warehouse": self.warehouse,
            "s3.endpoint": self.s3_config["endpoint"],
            "s3.access-key-id": self.s3_config["access_key"],
            "s3.secret-access-key": self.s3_config["secret_key"],
            "s3.path-style-access": "true",
        }

        return load_catalog("nessie", **config)

    @classmethod
    def from_env(cls, branch: str = "main") -> IcebergCatalog:
        """Create catalog from environment variables.

        Args:
            branch: Branch name

        Returns:
            IcebergCatalog instance
        """
        return cls(
            nessie_uri=os.getenv("NESSIE_URI", "http://localhost:19120/api/v2"),
            branch=branch,
            warehouse=os.getenv("ICEBERG_WAREHOUSE", "s3://warehouse/"),
            s3_config={
                "endpoint": os.getenv("S3_ENDPOINT", "http://localhost:9000"),
                "access_key": os.getenv("S3_ACCESS_KEY", "ratatouille"),
                "secret_key": os.getenv("S3_SECRET_KEY", "ratatouille123"),
            },
        )

    @classmethod
    def for_workspace(cls, workspace) -> IcebergCatalog:
        """Create catalog for a workspace.

        Args:
            workspace: Workspace instance

        Returns:
            IcebergCatalog bound to workspace's branch
        """
        return cls(
            nessie_uri=workspace.nessie_uri,
            branch=workspace.nessie_branch,
            warehouse=os.getenv("ICEBERG_WAREHOUSE", "s3://warehouse/"),
            s3_config={
                "endpoint": workspace.s3_endpoint,
                "access_key": workspace.s3_access_key,
                "secret_key": workspace.s3_secret_key,
            },
        )

    # =========================================================================
    # Namespace Operations
    # =========================================================================

    def ensure_namespace(self, namespace: str) -> None:
        """Create namespace if it doesn't exist.

        Args:
            namespace: Namespace name (e.g., "bronze")
        """
        try:
            self.catalog.create_namespace(namespace)
        except Exception:
            pass  # Already exists

    def list_namespaces(self) -> list[str]:
        """List all namespaces.

        Returns:
            List of namespace names
        """
        try:
            return [ns[0] for ns in self.catalog.list_namespaces()]
        except Exception:
            return []

    # =========================================================================
    # Table Operations
    # =========================================================================

    def create_table(
        self,
        name: str,
        df: pd.DataFrame,
        partition_by: list[str] | None = None,
    ) -> str:
        """Create an Iceberg table from a DataFrame.

        Args:
            name: Table name (e.g., "bronze.sales")
            df: DataFrame to create table from
            partition_by: Optional partition columns

        Returns:
            Full table identifier

        Example:
            catalog.create_table("bronze.sales", df, partition_by=["year"])
        """
        # Ensure namespace exists
        namespace = name.split(".")[0] if "." in name else "default"
        self.ensure_namespace(namespace)

        # Fix timestamp precision
        df = _fix_timestamp_precision(df)

        # Convert to Arrow
        arrow_table = pa.Table.from_pandas(df)

        # Drop if exists
        try:
            self.catalog.drop_table(name)
        except Exception:
            pass

        # Create table
        table = self.catalog.create_table(name, schema=arrow_table.schema)
        table.append(arrow_table)

        return name

    def append(self, name: str, df: pd.DataFrame) -> int:
        """Append data to an existing Iceberg table.

        Args:
            name: Table name
            df: DataFrame to append

        Returns:
            Number of rows appended
        """
        table = self.catalog.load_table(name)

        df = _fix_timestamp_precision(df)
        arrow_table = pa.Table.from_pandas(df)
        table.append(arrow_table)

        return len(df)

    def overwrite(self, name: str, df: pd.DataFrame) -> int:
        """Overwrite table data.

        Args:
            name: Table name
            df: DataFrame to write

        Returns:
            Number of rows written
        """
        table = self.catalog.load_table(name)

        df = _fix_timestamp_precision(df)
        arrow_table = pa.Table.from_pandas(df)
        table.overwrite(arrow_table)

        return len(df)

    def merge(
        self,
        name: str,
        df: pd.DataFrame,
        merge_keys: list[str],
    ) -> dict[str, int]:
        """Merge (upsert) data into a table.

        Deduplicates by merge_keys, keeping the latest record.

        Args:
            name: Table name
            df: DataFrame with new/updated records
            merge_keys: Columns that form unique key

        Returns:
            Dict with stats: {"inserted": n, "updated": n}
        """
        df = _fix_timestamp_precision(df)

        try:
            table = self.catalog.load_table(name)
            existing_df = table.scan().to_pandas()

            # Combine and dedupe
            combined = pd.concat([existing_df, df], ignore_index=True)
            combined = combined.drop_duplicates(subset=merge_keys, keep="last")
            combined = _fix_timestamp_precision(combined)

            # Overwrite table
            arrow_table = pa.Table.from_pandas(combined)
            table.overwrite(arrow_table)

            inserted = len(combined) - len(existing_df)
            updated = len(df) - inserted

        except Exception:
            # Table doesn't exist, create it
            self.create_table(name, df)
            inserted = len(df)
            updated = 0

        return {"inserted": max(0, inserted), "updated": max(0, updated)}

    def read_table(self, name: str) -> pd.DataFrame:
        """Read a table into a DataFrame.

        Args:
            name: Table name

        Returns:
            DataFrame with table data
        """
        table = self.catalog.load_table(name)
        return table.scan().to_pandas()

    def list_tables(self, namespace: str = "bronze") -> list[str]:
        """List all tables in a namespace.

        Args:
            namespace: Namespace to list

        Returns:
            List of table names
        """
        try:
            self.ensure_namespace(namespace)
            return [t[1] for t in self.catalog.list_tables(namespace)]
        except Exception:
            return []

    def drop_table(self, name: str) -> None:
        """Drop a table.

        Args:
            name: Table name to drop
        """
        self.catalog.drop_table(name)

    def table_exists(self, name: str) -> bool:
        """Check if a table exists.

        Args:
            name: Table name

        Returns:
            True if table exists
        """
        try:
            self.catalog.load_table(name)
            return True
        except Exception:
            return False

    # =========================================================================
    # Time Travel
    # =========================================================================

    def table_history(self, name: str) -> pd.DataFrame:
        """Get table snapshot history.

        Args:
            name: Table name

        Returns:
            DataFrame with snapshot info
        """
        table = self.catalog.load_table(name)

        snapshots = []
        for snapshot in table.metadata.snapshots:
            snapshots.append(
                {
                    "snapshot_id": snapshot.snapshot_id,
                    "timestamp": snapshot.timestamp_ms,
                    "operation": snapshot.summary.operation if snapshot.summary else None,
                }
            )

        return pd.DataFrame(snapshots)

    def read_snapshot(self, name: str, snapshot_id: int) -> pd.DataFrame:
        """Read table at a specific snapshot.

        Args:
            name: Table name
            snapshot_id: Snapshot ID

        Returns:
            DataFrame at that point in time
        """
        table = self.catalog.load_table(name)
        return table.scan(snapshot_id=snapshot_id).to_pandas()

    def __repr__(self) -> str:
        return f"IcebergCatalog(branch={self.branch!r}, warehouse={self.warehouse!r})"
