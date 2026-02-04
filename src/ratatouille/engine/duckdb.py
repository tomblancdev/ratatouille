"""🦆 DuckDB Query Engine - Embedded, memory-efficient data processing.

DuckDB is perfect for Ratatouille because:
- Embedded: No separate service to manage
- Low memory: Streams data, doesn't load everything into RAM
- Iceberg support: Native extension for lakehouse tables
- Fast: Columnar, vectorized execution
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb
import pandas as pd
import pyarrow as pa

if TYPE_CHECKING:
    from ratatouille.resources.config import ResourceConfig
    from ratatouille.workspace.manager import Workspace


class DuckDBEngine:
    """DuckDB engine with Iceberg and S3 support.

    Example:
        engine = DuckDBEngine.from_env()
        df = engine.query("SELECT * FROM iceberg.bronze.sales LIMIT 10")

        # With workspace isolation
        engine = DuckDBEngine.for_workspace(workspace)
        df = engine.query("SELECT * FROM bronze.sales")
    """

    def __init__(
        self,
        s3_endpoint: str,
        s3_access_key: str,
        s3_secret_key: str,
        nessie_uri: str | None = None,
        nessie_branch: str = "main",
        resources: "ResourceConfig | None" = None,
    ):
        self.s3_endpoint = s3_endpoint
        self.s3_access_key = s3_access_key
        self.s3_secret_key = s3_secret_key
        self.nessie_uri = nessie_uri
        self.nessie_branch = nessie_branch

        # Load resources config
        if resources is None:
            from ratatouille.resources.config import get_resource_config
            resources = get_resource_config()
        self.resources = resources

        # Create connection
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Get or create the DuckDB connection."""
        if self._conn is None:
            self._conn = self._create_connection()
        return self._conn

    def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create a new DuckDB connection with all extensions configured."""
        conn = duckdb.connect()

        # Apply resource limits
        for key, value in self.resources.to_duckdb_settings().items():
            conn.execute(f"SET {key} = {value}")

        # Install and load extensions
        self._setup_extensions(conn)

        # Configure S3
        self._setup_s3(conn)

        # Configure Iceberg catalog (if Nessie URI provided)
        if self.nessie_uri:
            self._setup_iceberg(conn)

        return conn

    def _setup_extensions(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Install and load required extensions."""
        extensions = ["httpfs", "iceberg"]

        for ext in extensions:
            try:
                conn.execute(f"INSTALL {ext}")
                conn.execute(f"LOAD {ext}")
            except Exception as e:
                # Extension might already be loaded
                print(f"⚠️ Extension {ext}: {e}")

    def _setup_s3(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Configure S3/MinIO access."""
        # Remove http:// or https:// prefix for DuckDB
        endpoint = self.s3_endpoint.replace("http://", "").replace("https://", "")

        conn.execute(f"SET s3_endpoint = '{endpoint}'")
        conn.execute(f"SET s3_access_key_id = '{self.s3_access_key}'")
        conn.execute(f"SET s3_secret_access_key = '{self.s3_secret_key}'")
        conn.execute("SET s3_url_style = 'path'")
        conn.execute("SET s3_use_ssl = false")

    def _setup_iceberg(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Configure Iceberg catalog via Nessie."""
        # Note: DuckDB's Iceberg extension has limited Nessie support as of 2024
        # We may need to use PyIceberg for full Nessie integration
        # For now, we'll use the REST catalog approach

        # This is a placeholder - actual Nessie integration requires
        # either duckdb-iceberg improvements or using PyIceberg
        pass

    @classmethod
    def from_env(cls) -> "DuckDBEngine":
        """Create engine from environment variables."""
        from ratatouille.resources.config import get_settings

        settings = get_settings()
        return cls(
            s3_endpoint=settings.s3_endpoint,
            s3_access_key=settings.s3_access_key,
            s3_secret_key=settings.s3_secret_key,
            nessie_uri=settings.nessie_uri,
            nessie_branch=settings.nessie_default_branch,
        )

    @classmethod
    def for_workspace(cls, workspace: "Workspace") -> "DuckDBEngine":
        """Create engine configured for a specific workspace."""
        return cls(
            s3_endpoint=workspace.s3_endpoint,
            s3_access_key=workspace.s3_access_key,
            s3_secret_key=workspace.s3_secret_key,
            nessie_uri=workspace.nessie_uri,
            nessie_branch=workspace.nessie_branch,
            resources=workspace.resources,
        )

    def query(self, sql: str) -> pd.DataFrame:
        """Execute a SQL query and return results as DataFrame.

        Args:
            sql: SQL query string

        Returns:
            pandas DataFrame with results

        Example:
            df = engine.query("SELECT * FROM 's3://warehouse/bronze/sales/*.parquet'")
        """
        return self.conn.execute(sql).df()

    def query_arrow(self, sql: str) -> pa.Table:
        """Execute a SQL query and return results as Arrow Table.

        More memory-efficient than DataFrame for large results.
        """
        return self.conn.execute(sql).arrow()

    def execute(self, sql: str) -> None:
        """Execute a SQL statement without returning results."""
        self.conn.execute(sql)

    def read_parquet(
        self,
        path: str,
        columns: list[str] | None = None,
        where: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Read Parquet file(s) from S3.

        Args:
            path: S3 path (e.g., "s3://warehouse/bronze/sales/*.parquet")
            columns: Optional list of columns to select
            where: Optional WHERE clause (without WHERE keyword)
            limit: Optional row limit

        Returns:
            DataFrame with file contents
        """
        cols = ", ".join(columns) if columns else "*"
        sql = f"SELECT {cols} FROM '{path}'"

        if where:
            sql += f" WHERE {where}"
        if limit:
            sql += f" LIMIT {limit}"

        return self.query(sql)

    def write_parquet(
        self,
        df: pd.DataFrame,
        path: str,
        partition_by: list[str] | None = None,
    ) -> str:
        """Write DataFrame to S3 as Parquet.

        Args:
            df: DataFrame to write
            path: S3 path (e.g., "s3://warehouse/silver/sales/")
            partition_by: Optional partition columns

        Returns:
            Path written to
        """
        # Register DataFrame as a view
        self.conn.register("_df_to_write", df)

        # Build COPY statement
        options = ["FORMAT PARQUET"]
        if partition_by:
            options.append(f"PARTITION_BY ({', '.join(partition_by)})")

        sql = f"COPY _df_to_write TO '{path}' ({', '.join(options)})"
        self.execute(sql)

        # Cleanup
        self.conn.unregister("_df_to_write")

        return path

    @contextmanager
    def transaction(self):
        """Context manager for transactional operations."""
        self.execute("BEGIN TRANSACTION")
        try:
            yield self
            self.execute("COMMIT")
        except Exception:
            self.execute("ROLLBACK")
            raise

    def close(self) -> None:
        """Close the connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "DuckDBEngine":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"DuckDBEngine("
            f"s3={self.s3_endpoint}, "
            f"nessie={self.nessie_uri}, "
            f"branch={self.nessie_branch})"
        )
