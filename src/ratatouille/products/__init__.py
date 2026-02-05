"""📦 Data Products - Cross-workspace data sharing.

Data Products allow workspaces to:
- Publish versioned datasets with schemas
- Subscribe to products from other workspaces
- Control access with permissions
- Track SLAs and freshness

Example - Publishing:
    from ratatouille.workspace import Workspace
    from ratatouille.products import publish_product

    workspace = Workspace.load("analytics")
    result = publish_product(
        workspace=workspace,
        product_name="sales_kpis",
        source_table="gold.daily_sales",
        version="1.0.0",
        description="Daily sales KPIs by store",
        tags=["sales", "kpi", "gold"],
    )

Example - Consuming:
    from ratatouille.workspace import Workspace
    from ratatouille.products import consume_product, query_product

    workspace = Workspace.load("reporting")

    # Option 1: Create a view
    consume_product(workspace, "sales_kpis", version_constraint="^1.0.0")
    df = workspace.get_engine().query("SELECT * FROM products.sales_kpis")

    # Option 2: Query directly
    df = query_product(workspace, "sales_kpis", "SELECT * FROM product LIMIT 100")

Example - Permissions:
    from ratatouille.products import PermissionManager

    pm = PermissionManager()
    pm.grant("sales_kpis", "analytics-*", "read")
    pm.grant("sales_kpis", "finance", "write")

    if pm.can_read("analytics-bi", "sales_kpis"):
        print("Access granted!")
"""

from .registry import (
    ProductRegistry,
    Product,
    ProductVersion,
    AccessRule,
)
from .publish import (
    publish_product,
    publish_from_config,
    bump_version,
    PublishResult,
)
from .consume import (
    consume_product,
    consume_from_config,
    query_product,
    list_available_products,
    get_product_schema,
    validate_subscription_schema,
    refresh_subscriptions,
    ConsumeResult,
)
from .permissions import (
    PermissionManager,
    PermissionCheck,
    require_permission,
    grant_read_all,
    grant_team_access,
)

__all__ = [
    # Registry
    "ProductRegistry",
    "Product",
    "ProductVersion",
    "AccessRule",
    # Publish
    "publish_product",
    "publish_from_config",
    "bump_version",
    "PublishResult",
    # Consume
    "consume_product",
    "consume_from_config",
    "query_product",
    "list_available_products",
    "get_product_schema",
    "validate_subscription_schema",
    "refresh_subscriptions",
    "ConsumeResult",
    # Permissions
    "PermissionManager",
    "PermissionCheck",
    "require_permission",
    "grant_read_all",
    "grant_team_access",
]
