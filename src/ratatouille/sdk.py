"""🐀 Ratatouille SDK - Simple interface for data operations.

This is the main entry point for using Ratatouille. It provides a simple,
unified interface to workspaces, pipelines, and data products.

Example:
    from ratatouille import rat

    # Load workspace and query data
    ws = rat.workspace("analytics")
    df = rat.query("SELECT * FROM bronze.sales LIMIT 100")

    # Run a pipeline
    rat.run("silver.sales")

    # Publish a data product
    rat.publish("daily_kpis", "gold.daily_sales", version="1.0.0")
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from ratatouille.workspace.manager import Workspace
    from ratatouille.engine.duckdb import DuckDBEngine


class RatatouilleSDK:
    """Main SDK class for Ratatouille operations.

    Provides a simple interface to:
    - Workspace management
    - DuckDB queries
    - Pipeline execution
    - Data products

    Example:
        rat = RatatouilleSDK()
        rat.workspace("analytics")
        df = rat.query("SELECT * FROM bronze.sales")
    """

    def __init__(self):
        self._workspace: "Workspace | None" = None
        self._engine: "DuckDBEngine | None" = None

    # =========================================================================
    # Workspace Operations
    # =========================================================================

    def workspace(self, name: str | None = None) -> "Workspace":
        """Load or get current workspace.

        Args:
            name: Workspace name (default: from $WORKSPACE env or "default")

        Returns:
            Loaded Workspace instance

        Example:
            ws = rat.workspace("analytics")
            print(ws.name, ws.nessie_branch)
        """
        from ratatouille.workspace.manager import Workspace

        if name is None:
            name = os.getenv("WORKSPACE", "default")

        if self._workspace is None or self._workspace.name != name:
            self._workspace = Workspace.load(name)
            self._engine = None  # Reset engine for new workspace

        return self._workspace

    @property
    def ws(self) -> "Workspace":
        """Get current workspace (shorthand)."""
        if self._workspace is None:
            return self.workspace()
        return self._workspace

    def create_workspace(
        self,
        name: str,
        description: str = "",
        base_dir: str | None = None,
    ) -> "Workspace":
        """Create a new workspace.

        Args:
            name: Workspace name
            description: Optional description
            base_dir: Parent directory (default: ./workspaces)

        Returns:
            Created Workspace instance
        """
        from ratatouille.workspace.manager import Workspace

        ws = Workspace.create(name=name, base_dir=base_dir, description=description)
        self._workspace = ws
        self._engine = None
        return ws

    def list_workspaces(self) -> list[str]:
        """List all available workspaces."""
        from ratatouille.workspace.manager import list_workspaces

        return list_workspaces()

    # =========================================================================
    # Query Operations (DuckDB)
    # =========================================================================

    def engine(self) -> "DuckDBEngine":
        """Get DuckDB engine for current workspace."""
        if self._engine is None:
            self._engine = self.ws.get_engine()
        return self._engine

    def query(self, sql: str) -> pd.DataFrame:
        """Execute SQL query using DuckDB.

        Args:
            sql: SQL query string

        Returns:
            DataFrame with results

        Example:
            df = rat.query("SELECT * FROM bronze.sales LIMIT 100")
            df = rat.query("SELECT COUNT(*) FROM read_parquet('s3://warehouse/data.parquet')")
        """
        return self.engine().query(sql)

    def read(self, path: str) -> pd.DataFrame:
        """Read a Parquet file from S3.

        Args:
            path: S3 path (s3://bucket/key.parquet)

        Returns:
            DataFrame with file contents

        Example:
            df = rat.read("s3://warehouse/bronze/sales/*.parquet")
        """
        return self.query(f"SELECT * FROM read_parquet('{path}')")

    def write(self, df: pd.DataFrame, path: str, partition_by: list[str] | None = None) -> str:
        """Write DataFrame to S3 as Parquet.

        Args:
            df: DataFrame to write
            path: S3 destination path
            partition_by: Optional partition columns

        Returns:
            Path written to
        """
        return self.engine().write_parquet(df, path, partition_by=partition_by)

    # =========================================================================
    # Pipeline Operations
    # =========================================================================

    def run(
        self,
        pipeline_name: str,
        full_refresh: bool = False,
    ) -> dict[str, Any]:
        """Run a pipeline.

        Args:
            pipeline_name: Pipeline name (e.g., "silver.sales")
            full_refresh: Force full refresh instead of incremental

        Returns:
            Execution result dict

        Example:
            result = rat.run("silver.sales")
            result = rat.run("gold.daily_kpis", full_refresh=True)
        """
        from ratatouille.pipeline import PipelineExecutor

        executor = PipelineExecutor(self.ws)
        return executor.run_pipeline(pipeline_name, full_refresh=full_refresh)

    def list_pipelines(self) -> dict[str, list[str]]:
        """List all pipelines in current workspace by layer.

        Returns:
            Dict mapping layer to list of pipeline files
        """
        return self.ws.list_pipelines()

    # =========================================================================
    # Data Products
    # =========================================================================

    def publish(
        self,
        product_name: str,
        source_table: str,
        version: str,
        description: str = "",
        tags: list[str] | None = None,
        changelog: str = "",
    ) -> dict[str, Any]:
        """Publish a data product.

        Args:
            product_name: Product name
            source_table: Source table (e.g., "gold.daily_sales")
            version: Semver version (e.g., "1.0.0")
            description: Product description
            tags: Searchable tags
            changelog: What changed in this version

        Returns:
            Publish result dict

        Example:
            rat.publish("sales_kpis", "gold.daily_sales", "1.0.0")
        """
        from ratatouille.products import publish_product

        result = publish_product(
            workspace=self.ws,
            product_name=product_name,
            source_table=source_table,
            version=version,
            description=description,
            tags=tags,
            changelog=changelog,
        )
        return {
            "product_name": result.product_name,
            "version": result.version,
            "s3_location": result.s3_location,
            "row_count": result.row_count,
        }

    def consume(
        self,
        product_name: str,
        version_constraint: str = "latest",
        alias: str | None = None,
    ) -> dict[str, Any]:
        """Consume a data product.

        Creates a view in the 'products' schema for easy querying.

        Args:
            product_name: Product to consume
            version_constraint: Version constraint (e.g., "^1.0.0", "latest")
            alias: Local name for the product

        Returns:
            Consume result dict

        Example:
            rat.consume("sales_kpis", "^1.0.0", alias="sales")
            df = rat.query("SELECT * FROM products.sales")
        """
        from ratatouille.products import consume_product

        result = consume_product(
            workspace=self.ws,
            product_name=product_name,
            version_constraint=version_constraint,
            local_alias=alias,
        )
        return {
            "product_name": result.product_name,
            "version": result.version,
            "local_alias": result.local_alias,
            "row_count": result.row_count,
        }

    def list_products(self) -> list[dict[str, Any]]:
        """List all products available to current workspace.

        Returns:
            List of product info dicts
        """
        from ratatouille.products import list_available_products

        return list_available_products(self.ws)

    # =========================================================================
    # Utilities
    # =========================================================================

    def s3_path(self, layer: str, table: str) -> str:
        """Get S3 path for a table in current workspace.

        Args:
            layer: Medallion layer (bronze, silver, gold)
            table: Table name

        Returns:
            Full S3 path
        """
        return self.ws.s3_path(layer, table)

    def info(self) -> dict[str, Any]:
        """Get info about current workspace and environment."""
        return {
            "workspace": self.ws.name,
            "nessie_branch": self.ws.nessie_branch,
            "s3_prefix": self.ws.s3_prefix,
            "s3_endpoint": self.ws.s3_endpoint,
            "nessie_uri": self.ws.nessie_uri,
            "resource_profile": self.ws.config.resources.profile,
        }


# Global SDK instance
rat = RatatouilleSDK()

# Convenience exports
workspace = rat.workspace
query = rat.query
read = rat.read
write = rat.write
run = rat.run
publish = rat.publish
consume = rat.consume
