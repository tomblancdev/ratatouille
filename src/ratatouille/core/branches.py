"""🏷️ Layer management for medallion architecture.

Unity Catalog uses catalog.schema.table structure.
We map our medallion layers to schemas:
- bronze: Raw data
- silver: Cleaned/validated
- gold: Business-ready

Note: Unlike Nessie, Unity Catalog doesn't have git-like branching.
For isolation during development, use separate schemas or catalogs.
"""

import os

# Current working layer
_current_layer = "bronze"


def get_current_layer() -> str:
    """Get current working layer (default: bronze)."""
    return os.getenv("RATATOUILLE_LAYER", _current_layer)


def set_layer(layer: str) -> None:
    """Set the current working layer.

    Args:
        layer: One of "bronze", "silver", "gold", or custom schema name
    """
    global _current_layer
    valid_layers = {"bronze", "silver", "gold"}
    if layer not in valid_layers:
        print(f"⚠️ Non-standard layer: {layer} (standard: {valid_layers})")
    _current_layer = layer
    os.environ["RATATOUILLE_LAYER"] = layer
    print(f"🏷️ Now using layer: {layer}")


def use_bronze() -> None:
    """Switch to bronze layer (raw data)."""
    set_layer("bronze")


def use_silver() -> None:
    """Switch to silver layer (cleaned data)."""
    set_layer("silver")


def use_gold() -> None:
    """Switch to gold layer (business-ready)."""
    set_layer("gold")


def get_table_name(table: str, layer: str | None = None) -> str:
    """Get fully qualified table name with layer.

    Args:
        table: Table name (e.g., "transactions")
        layer: Optional layer override (uses current layer if not specified)

    Returns:
        Full table name (e.g., "bronze.transactions")

    Example:
        >>> get_table_name("transactions")
        "bronze.transactions"
        >>> get_table_name("sales", layer="gold")
        "gold.sales"
    """
    layer = layer or get_current_layer()
    if "." in table:
        return table  # Already qualified
    return f"{layer}.{table}"


# =============================================================================
# High-level workflow helpers
# =============================================================================


def workflow_ingest() -> str:
    """Start ingestion workflow (use bronze layer).

    Returns:
        Current layer name
    """
    use_bronze()
    print("📥 Starting ingestion workflow")
    return "bronze"


def workflow_transform() -> str:
    """Start transformation workflow (use silver layer).

    Returns:
        Current layer name
    """
    use_silver()
    print("🔄 Starting transformation workflow")
    return "silver"


def workflow_publish() -> str:
    """Start publish workflow (use gold layer).

    Returns:
        Current layer name
    """
    use_gold()
    print("🚀 Starting publish workflow")
    return "gold"


def list_layers() -> list[dict]:
    """List all medallion layers with descriptions."""
    current = get_current_layer()
    return [
        {
            "name": "bronze",
            "description": "Raw, immutable data as-is from source",
            "current": current == "bronze",
        },
        {
            "name": "silver",
            "description": "Cleaned, validated, deduplicated data",
            "current": current == "silver",
        },
        {
            "name": "gold",
            "description": "Business-ready, aggregated data",
            "current": current == "gold",
        },
    ]
