"""📤 Product Publishing - Publish data products from workspace tables.

Handles:
- Schema extraction from source tables
- Data copying to versioned S3 location
- Version registration in product registry
- Nessie commit tracking for reproducibility
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ratatouille.engine.duckdb import DuckDBEngine
    from ratatouille.workspace.manager import Workspace

from .registry import ProductRegistry


@dataclass
class PublishResult:
    """Result of a product publish operation."""

    product_name: str
    version: str
    s3_location: str
    row_count: int
    schema: dict[str, Any]
    published_at: datetime
    nessie_commit: str | None = None

    @property
    def success(self) -> bool:
        return self.row_count >= 0


def publish_product(
    workspace: Workspace,
    product_name: str,
    source_table: str,
    version: str,
    description: str = "",
    tags: list[str] | None = None,
    changelog: str = "",
    sla_freshness_hours: int | None = None,
    published_by: str = "system",
    registry: ProductRegistry | None = None,
) -> PublishResult:
    """Publish a data product from a workspace table.

    This is the main entry point for publishing data products.
    It will:
    1. Register the product if it doesn't exist
    2. Extract schema from the source table
    3. Copy data to versioned S3 location
    4. Register the version in the product registry

    Args:
        workspace: Source workspace
        product_name: Product name (must be unique)
        source_table: Source table in format "layer.table" (e.g., "gold.daily_sales")
        version: Semver version string (e.g., "1.0.0")
        description: Product description (only used if registering new product)
        tags: Product tags (only used if registering new product)
        changelog: What changed in this version
        sla_freshness_hours: Freshness SLA (only used if registering new product)
        published_by: User/system publishing
        registry: Optional registry instance (creates default if not provided)

    Returns:
        PublishResult with details of the published version

    Example:
        from ratatouille.workspace import Workspace
        from ratatouille.products import publish_product

        workspace = Workspace.load("analytics")
        result = publish_product(
            workspace=workspace,
            product_name="sales_kpis",
            source_table="gold.daily_sales",
            version="1.0.0",
            description="Daily sales KPIs by store",
            tags=["sales", "kpi"],
            changelog="Initial release",
        )
        print(f"Published {result.product_name} v{result.version}")
        print(f"Location: {result.s3_location}")
        print(f"Rows: {result.row_count}")
    """
    if registry is None:
        registry = ProductRegistry()

    engine = workspace.get_engine()

    # 1. Register product if it doesn't exist
    existing = registry.get_product(product_name)
    if existing is None:
        registry.register_product(
            name=product_name,
            owner_workspace=workspace.name,
            description=description,
            tags=tags,
            sla_freshness_hours=sla_freshness_hours,
        )
        print(f"📦 Registered new product: {product_name}")

        # Grant read access to all workspaces by default
        # Can be customized via workspace config
        registry.grant_access(product_name, workspace_pattern="*", level="read")
    else:
        if existing.owner_workspace != workspace.name:
            raise PermissionError(
                f"Product '{product_name}' is owned by workspace '{existing.owner_workspace}', "
                f"not '{workspace.name}'"
            )

    # 2. Extract schema from source table
    schema = _extract_schema(engine, source_table)
    print(f"📋 Extracted schema: {len(schema)} columns")

    # 3. Copy data to versioned S3 location
    s3_location = _get_product_s3_path(product_name, version)
    row_count = _copy_to_s3(engine, source_table, s3_location)
    print(f"📁 Copied {row_count:,} rows to {s3_location}")

    # 4. Get Nessie commit for reproducibility (if available)
    nessie_commit = _get_nessie_commit(workspace)

    # 5. Register version
    product_version = registry.publish_version(
        product_name=product_name,
        version=version,
        source_workspace=workspace.name,
        source_table=source_table,
        schema_snapshot=schema,
        s3_location=s3_location,
        row_count=row_count,
        nessie_commit=nessie_commit,
        published_by=published_by,
        changelog=changelog,
    )

    print(f"✅ Published {product_name} v{version}")

    return PublishResult(
        product_name=product_name,
        version=version,
        s3_location=s3_location,
        row_count=row_count,
        schema=schema,
        published_at=product_version.published_at,
        nessie_commit=nessie_commit,
    )


def publish_from_config(
    workspace: Workspace,
    registry: ProductRegistry | None = None,
) -> list[PublishResult]:
    """Publish all products defined in workspace config.

    Reads product definitions from workspace.yaml and publishes each one.
    Uses auto-versioning based on content hash if version not specified.

    Args:
        workspace: Workspace with product definitions
        registry: Optional registry instance

    Returns:
        List of PublishResult for each published product
    """
    if registry is None:
        registry = ProductRegistry()

    results = []

    for product_config in workspace.config.products:
        # Determine version (auto-version if not specified)
        existing = registry.get_latest_version(product_config.name)
        if existing:
            # Bump patch version
            major, minor, patch = existing.version.split(".")
            version = f"{major}.{minor}.{int(patch) + 1}"
        else:
            version = "1.0.0"

        try:
            result = publish_product(
                workspace=workspace,
                product_name=product_config.name,
                source_table=product_config.source,
                version=version,
                sla_freshness_hours=product_config.sla.get("freshness_hours"),
                registry=registry,
            )

            # Apply custom access rules from config
            for access in product_config.access:
                registry.grant_access(
                    product_name=product_config.name,
                    workspace_pattern=access.get("workspace", "*"),
                    level=access.get("level", "read"),
                )

            results.append(result)

        except Exception as e:
            print(f"❌ Failed to publish {product_config.name}: {e}")

    return results


def _extract_schema(engine: DuckDBEngine, table: str) -> dict[str, Any]:
    """Extract schema information from a table.

    Returns dict mapping column name to column info:
    {
        "column_name": {
            "type": "varchar",
            "nullable": True,
            "description": ""
        }
    }
    """
    # Parse table reference
    parts = table.split(".")
    if len(parts) == 2:
        schema_name, table_name = parts
    else:
        schema_name = "main"
        table_name = table

    # Get column info using DuckDB's DESCRIBE
    try:
        df = engine.query(f"DESCRIBE {schema_name}.{table_name}")
        schema = {}

        for _, row in df.iterrows():
            col_name = row.get("column_name", row.get("Field", "unknown"))
            col_type = row.get("column_type", row.get("Type", "unknown"))
            nullable = row.get("null", row.get("Null", "YES")) == "YES"

            schema[col_name] = {
                "type": col_type,
                "nullable": nullable,
                "description": "",
            }

        return schema

    except Exception:
        # Fallback: try to infer schema from SELECT
        df = engine.query(f"SELECT * FROM {table} LIMIT 0")
        schema = {}
        for col in df.columns:
            schema[col] = {
                "type": str(df[col].dtype),
                "nullable": True,
                "description": "",
            }
        return schema


def _get_product_s3_path(product_name: str, version: str) -> str:
    """Get S3 path for a product version."""
    warehouse = os.getenv("ICEBERG_WAREHOUSE", "s3://warehouse")
    warehouse = warehouse.rstrip("/")
    return f"{warehouse}/_products/{product_name}/v{version}/"


def _copy_to_s3(
    engine: DuckDBEngine,
    source_table: str,
    s3_location: str,
) -> int:
    """Copy table data to S3 as Parquet.

    Returns row count.
    """
    # Parse table reference
    parts = source_table.split(".")
    if len(parts) == 2:
        full_table = source_table
    else:
        full_table = f"main.{source_table}"

    # Get row count first
    count_df = engine.query(f"SELECT COUNT(*) as cnt FROM {full_table}")
    row_count = int(count_df.iloc[0]["cnt"])

    if row_count == 0:
        print("⚠️ Warning: Publishing empty product (0 rows)")
        return 0

    # Copy to S3 as Parquet
    # Use DuckDB's COPY command with Parquet output
    parquet_path = f"{s3_location}data.parquet"

    engine.conn.execute(f"""
        COPY (SELECT * FROM {full_table})
        TO '{parquet_path}'
        (FORMAT PARQUET, COMPRESSION 'ZSTD')
    """)

    return row_count


def _get_nessie_commit(workspace: Workspace) -> str | None:
    """Get current Nessie commit hash for the workspace branch."""
    try:
        import httpx

        response = httpx.get(
            f"{workspace.nessie_uri}/trees/{workspace.nessie_branch}",
            timeout=5.0,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("hash")
    except Exception:
        pass

    return None


def bump_version(
    current: str,
    bump_type: str = "patch",
) -> str:
    """Bump a semver version.

    Args:
        current: Current version (e.g., "1.2.3")
        bump_type: "major", "minor", or "patch"

    Returns:
        Bumped version string
    """
    parts = current.split(".")
    if len(parts) != 3:
        parts = ["1", "0", "0"]

    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"
