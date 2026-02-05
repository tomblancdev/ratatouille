"""📥 Product Consumption - Consume data products in workspace pipelines.

Handles:
- Resolving product versions from constraints
- Verifying access permissions
- Creating views/references to product data
- Schema validation against subscriptions
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from ratatouille.engine.duckdb import DuckDBEngine
    from ratatouille.workspace.manager import Workspace

from .registry import ProductRegistry, ProductVersion


@dataclass
class ConsumeResult:
    """Result of consuming a product."""

    product_name: str
    version: str
    s3_location: str
    row_count: int
    schema: dict[str, Any]
    local_alias: str | None = None
    view_created: bool = False

    @property
    def success(self) -> bool:
        return self.row_count >= 0


def consume_product(
    workspace: "Workspace",
    product_name: str,
    version_constraint: str = "latest",
    local_alias: str | None = None,
    create_view: bool = True,
    registry: ProductRegistry | None = None,
) -> ConsumeResult:
    """Consume a data product in a workspace.

    This is the main entry point for consuming data products.
    It will:
    1. Verify workspace has access to the product
    2. Resolve version from constraint
    3. Optionally create a view in the workspace for easy querying
    4. Register the subscription

    Args:
        workspace: Consumer workspace
        product_name: Product to consume
        version_constraint: Version constraint ("latest", "1.2.3", "^1.0.0", etc.)
        local_alias: Optional local name for the product view
        create_view: Whether to create a view in DuckDB
        registry: Optional registry instance

    Returns:
        ConsumeResult with product details

    Example:
        from ratatouille.workspace import Workspace
        from ratatouille.products import consume_product

        workspace = Workspace.load("reporting")
        result = consume_product(
            workspace=workspace,
            product_name="sales_kpis",
            version_constraint="^1.0.0",
            local_alias="kpis",
        )

        # Now query the product
        engine = workspace.get_engine()
        df = engine.query("SELECT * FROM products.kpis")
    """
    if registry is None:
        registry = ProductRegistry()

    # 1. Check access
    if not registry.check_access(product_name, workspace.name, "read"):
        raise PermissionError(
            f"Workspace '{workspace.name}' does not have read access to product '{product_name}'. "
            f"Contact the product owner to request access."
        )

    # 2. Resolve version
    version = registry.resolve_version(product_name, version_constraint)
    if version is None:
        raise ValueError(
            f"No version matching '{version_constraint}' found for product '{product_name}'"
        )

    print(f"📦 Resolved {product_name} {version_constraint} → v{version.version}")

    # 3. Register subscription
    effective_alias = local_alias or product_name.replace("/", "_").replace("-", "_")
    registry.subscribe(
        product_name=product_name,
        consumer_workspace=workspace.name,
        version_constraint=version_constraint,
        local_alias=effective_alias,
    )

    # 4. Create view if requested
    view_created = False
    if create_view:
        view_created = _create_product_view(
            workspace=workspace,
            version=version,
            alias=effective_alias,
        )

    return ConsumeResult(
        product_name=product_name,
        version=version.version,
        s3_location=version.s3_location,
        row_count=version.row_count,
        schema=version.schema_snapshot,
        local_alias=effective_alias,
        view_created=view_created,
    )


def consume_from_config(
    workspace: "Workspace",
    registry: ProductRegistry | None = None,
) -> list[ConsumeResult]:
    """Consume all products defined in workspace config subscriptions.

    Reads subscription definitions from workspace.yaml and consumes each one.

    Args:
        workspace: Workspace with subscription definitions
        registry: Optional registry instance

    Returns:
        List of ConsumeResult for each consumed product
    """
    if registry is None:
        registry = ProductRegistry()

    results = []

    for subscription in workspace.config.subscriptions:
        try:
            result = consume_product(
                workspace=workspace,
                product_name=subscription.product,
                version_constraint=subscription.version_constraint,
                local_alias=subscription.alias,
                registry=registry,
            )
            results.append(result)

        except Exception as e:
            print(f"❌ Failed to consume {subscription.product}: {e}")

    return results


def query_product(
    workspace: "Workspace",
    product_name: str,
    query: str | None = None,
    version_constraint: str = "latest",
    registry: ProductRegistry | None = None,
) -> pd.DataFrame:
    """Query a data product directly.

    Provides a simple way to query product data without creating views.

    Args:
        workspace: Workspace making the query
        product_name: Product to query
        query: SQL query (uses SELECT * if not provided)
        version_constraint: Version constraint
        registry: Optional registry instance

    Returns:
        DataFrame with query results

    Example:
        df = query_product(
            workspace,
            "sales_kpis",
            query="SELECT sale_date, SUM(revenue) FROM product GROUP BY sale_date"
        )
    """
    if registry is None:
        registry = ProductRegistry()

    # Check access
    if not registry.check_access(product_name, workspace.name, "read"):
        raise PermissionError(
            f"Workspace '{workspace.name}' does not have access to product '{product_name}'"
        )

    # Resolve version
    version = registry.resolve_version(product_name, version_constraint)
    if version is None:
        raise ValueError(f"No version found for '{product_name}' matching '{version_constraint}'")

    engine = workspace.get_engine()

    # Build query
    parquet_path = f"{version.s3_location}data.parquet"

    if query is None:
        full_query = f"SELECT * FROM read_parquet('{parquet_path}')"
    else:
        # Replace 'product' placeholder with actual path
        full_query = query.replace(
            "product",
            f"read_parquet('{parquet_path}')"
        )

    return engine.query(full_query)


def list_available_products(
    workspace: "Workspace",
    registry: ProductRegistry | None = None,
) -> list[dict[str, Any]]:
    """List all products available to a workspace.

    Returns products the workspace has access to, along with access level.

    Args:
        workspace: Workspace to check access for
        registry: Optional registry instance

    Returns:
        List of product info dicts
    """
    if registry is None:
        registry = ProductRegistry()

    products = registry.list_products()
    available = []

    for product in products:
        # Check access levels
        has_read = registry.check_access(product.name, workspace.name, "read")
        has_write = registry.check_access(product.name, workspace.name, "write")
        has_admin = registry.check_access(product.name, workspace.name, "admin")

        if has_read or has_write or has_admin:
            # Get latest version info
            latest = registry.get_latest_version(product.name)

            access_level = "admin" if has_admin else ("write" if has_write else "read")

            available.append({
                "name": product.name,
                "owner": product.owner_workspace,
                "description": product.description,
                "tags": product.tags,
                "latest_version": latest.version if latest else None,
                "row_count": latest.row_count if latest else 0,
                "access_level": access_level,
                "sla_freshness_hours": product.sla_freshness_hours,
                "is_deprecated": product.is_deprecated,
            })

    return available


def get_product_schema(
    product_name: str,
    version: str = "latest",
    registry: ProductRegistry | None = None,
) -> dict[str, Any]:
    """Get schema for a product version.

    Args:
        product_name: Product name
        version: Version string or "latest"
        registry: Optional registry instance

    Returns:
        Schema dict mapping column names to type info
    """
    if registry is None:
        registry = ProductRegistry()

    resolved = registry.resolve_version(product_name, version)
    if resolved is None:
        raise ValueError(f"Version '{version}' not found for product '{product_name}'")

    return resolved.schema_snapshot


def validate_subscription_schema(
    workspace: "Workspace",
    product_name: str,
    expected_columns: list[str],
    registry: ProductRegistry | None = None,
) -> tuple[bool, list[str]]:
    """Validate that a product has expected columns.

    Useful for ensuring schema compatibility before using a product.

    Args:
        workspace: Workspace checking the schema
        product_name: Product to validate
        expected_columns: List of column names that must exist
        registry: Optional registry instance

    Returns:
        Tuple of (is_valid, missing_columns)
    """
    if registry is None:
        registry = ProductRegistry()

    # Get subscription version constraint
    subs = registry.get_subscriptions(workspace.name)
    sub = next((s for s in subs if s["product_name"] == product_name), None)

    constraint = sub["version_constraint"] if sub else "latest"
    version = registry.resolve_version(product_name, constraint)

    if version is None:
        return False, expected_columns

    schema_columns = set(version.schema_snapshot.keys())
    missing = [col for col in expected_columns if col not in schema_columns]

    return len(missing) == 0, missing


def _create_product_view(
    workspace: "Workspace",
    version: ProductVersion,
    alias: str,
) -> bool:
    """Create a view in DuckDB for a product.

    Creates the view in a 'products' schema for namespacing.
    """
    engine = workspace.get_engine()
    parquet_path = f"{version.s3_location}data.parquet"

    try:
        # Ensure products schema exists
        engine.conn.execute("CREATE SCHEMA IF NOT EXISTS products")

        # Create or replace view
        engine.conn.execute(f"""
            CREATE OR REPLACE VIEW products.{alias} AS
            SELECT * FROM read_parquet('{parquet_path}')
        """)

        print(f"✅ Created view: products.{alias}")
        return True

    except Exception as e:
        print(f"⚠️ Could not create view: {e}")
        return False


def refresh_subscriptions(
    workspace: "Workspace",
    registry: ProductRegistry | None = None,
) -> list[ConsumeResult]:
    """Refresh all subscriptions to latest matching versions.

    Re-evaluates version constraints and updates views if needed.

    Args:
        workspace: Workspace to refresh
        registry: Optional registry instance

    Returns:
        List of ConsumeResult for refreshed products
    """
    if registry is None:
        registry = ProductRegistry()

    subs = registry.get_subscriptions(workspace.name)
    results = []

    for sub in subs:
        result = consume_product(
            workspace=workspace,
            product_name=sub["product_name"],
            version_constraint=sub["version_constraint"],
            local_alias=sub["local_alias"],
            create_view=True,
            registry=registry,
        )
        results.append(result)

    return results
