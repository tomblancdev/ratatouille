"""🐀 Iceberg utilities - Lakehouse table format with Nessie REST catalog.

Uses PyIceberg with Nessie for git-like versioning and MinIO for data files.
Branch-aware operations enable workspace isolation.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import pyarrow as pa
from pyiceberg.catalog import load_catalog

# Branch-aware catalog cache: {branch: catalog_instance}
_catalog_cache: dict[str, Any] = {}


def _fix_timestamp_precision(df: pd.DataFrame) -> pd.DataFrame:
    """Convert nanosecond timestamps to microseconds for Iceberg compatibility."""
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype("datetime64[us]")
    return df


def _require_env(name: str) -> str:
    """Get required environment variable."""
    value = os.getenv(name)
    if not value:
        raise OSError(
            f"Missing required environment variable: {name}\n"
            f"Make sure you have a .env file. See .env.example for reference."
        )
    return value


def get_catalog(branch: str = "main"):
    """Get the Iceberg catalog for a specific branch (cached per branch).

    Uses Nessie REST catalog for git-like versioning.

    Args:
        branch: Nessie branch name (default: "main")

    Returns:
        PyIceberg RestCatalog instance

    Example:
        catalog = get_catalog("workspace/acme")
        tables = catalog.list_tables("bronze")
    """
    if branch in _catalog_cache:
        return _catalog_cache[branch]

    # Get configuration from environment
    nessie_uri = os.getenv("NESSIE_URI", "http://localhost:19120/api/v2")
    warehouse_path = os.getenv("ICEBERG_WAREHOUSE", "s3://warehouse/")
    s3_endpoint = _require_env("S3_ENDPOINT")
    s3_access_key = _require_env("S3_ACCESS_KEY")
    s3_secret_key = _require_env("S3_SECRET_KEY")

    # Create RestCatalog pointing to Nessie
    catalog = load_catalog(
        "nessie",
        **{
            "type": "rest",
            "uri": f"{nessie_uri.rstrip('/')}/iceberg",
            "ref": branch,
            "warehouse": warehouse_path,
            "s3.endpoint": s3_endpoint,
            "s3.access-key-id": s3_access_key,
            "s3.secret-access-key": s3_secret_key,
            "s3.path-style-access": "true",
        },
    )

    _catalog_cache[branch] = catalog
    return catalog


def clear_catalog_cache() -> None:
    """Clear the catalog cache (useful for testing)."""
    _catalog_cache.clear()


def ensure_namespace(namespace: str, branch: str = "main") -> None:
    """Create namespace if it doesn't exist.

    Args:
        namespace: Namespace name
        branch: Nessie branch
    """
    catalog = get_catalog(branch)
    try:
        catalog.create_namespace(namespace)
        print(f"📁 Created namespace: {namespace}")
    except Exception:
        pass  # Already exists


def create_table(
    name: str,
    df: pd.DataFrame,
    partition_by: list[str] | None = None,
    branch: str = "main",
) -> str:
    """Create an Iceberg table from a DataFrame.

    Args:
        name: Table name (e.g., "bronze.transactions")
        df: DataFrame to create table from
        partition_by: Optional partition columns
        branch: Nessie branch for the operation

    Returns:
        Full table identifier

    Example:
        create_table("bronze.sales", df, partition_by=["year", "month"])
    """
    catalog = get_catalog(branch)

    # Ensure namespace exists
    namespace = name.split(".")[0] if "." in name else "default"
    ensure_namespace(namespace, branch)

    # Fix timestamp precision (ns → us) for Iceberg compatibility
    df = _fix_timestamp_precision(df)

    # Convert to Arrow
    arrow_table = pa.Table.from_pandas(df)

    # Drop if exists
    try:
        catalog.drop_table(name)
    except Exception:
        pass

    # Create table
    table = catalog.create_table(name, schema=arrow_table.schema)
    table.append(arrow_table)

    print(f"✅ Created table: {name} ({len(df)} rows) on branch '{branch}'")
    return name


def append(name: str, df: pd.DataFrame, branch: str = "main") -> int:
    """Append data to an existing Iceberg table.

    Args:
        name: Table name (e.g., "bronze.transactions")
        df: DataFrame to append
        branch: Nessie branch

    Returns:
        Number of rows appended

    Example:
        append("bronze.transactions", new_df, branch="workspace/acme")
    """
    catalog = get_catalog(branch)
    table = catalog.load_table(name)

    # Fix timestamp precision (ns → us) for Iceberg compatibility
    df = _fix_timestamp_precision(df)

    arrow_table = pa.Table.from_pandas(df)
    table.append(arrow_table)

    return len(df)


def merge(
    name: str,
    df: pd.DataFrame,
    merge_keys: list[str],
    branch: str = "main",
) -> dict:
    """Merge (upsert) data into an Iceberg table.

    Deduplicates by merge_keys, keeping the latest record.

    Args:
        name: Table name
        df: DataFrame with new/updated records
        merge_keys: Columns that form unique key
        branch: Nessie branch

    Returns:
        Dict with stats: {"inserted": n, "updated": n}

    Example:
        merge("silver.transactions", df, merge_keys=["date", "store_id"], branch="main")
    """
    catalog = get_catalog(branch)

    # Fix timestamp precision (ns → us) for Iceberg compatibility
    df = _fix_timestamp_precision(df)

    try:
        table = catalog.load_table(name)
        existing_df = table.scan().to_pandas()

        # Combine and dedupe
        combined = pd.concat([existing_df, df], ignore_index=True)
        combined = combined.drop_duplicates(subset=merge_keys, keep="last")

        # Fix timestamps again after concat
        combined = _fix_timestamp_precision(combined)

        # Overwrite table
        arrow_table = pa.Table.from_pandas(combined)
        table.overwrite(arrow_table)

        inserted = len(combined) - len(existing_df)
        updated = len(df) - inserted

    except Exception:
        # Table doesn't exist, create it
        create_table(name, df, branch=branch)
        inserted = len(df)
        updated = 0

    return {"inserted": max(0, inserted), "updated": max(0, updated)}


def read_table(name: str, branch: str = "main") -> pd.DataFrame:
    """Read an Iceberg table into a DataFrame.

    Args:
        name: Table name
        branch: Nessie branch to read from

    Returns:
        DataFrame with table data

    Example:
        df = read_table("silver.transactions", branch="workspace/acme")
    """
    catalog = get_catalog(branch)
    table = catalog.load_table(name)

    scan = table.scan()
    return scan.to_pandas()


def list_tables(namespace: str = "bronze", branch: str = "main") -> list[str]:
    """List all tables in a namespace.

    Args:
        namespace: Namespace to list
        branch: Nessie branch

    Returns:
        List of table names
    """
    catalog = get_catalog(branch)
    try:
        ensure_namespace(namespace, branch)
        return [t[1] for t in catalog.list_tables(namespace)]
    except Exception:
        return []


def list_namespaces(branch: str = "main") -> list[str]:
    """List all namespaces (bronze, silver, gold, etc.).

    Args:
        branch: Nessie branch

    Returns:
        List of namespace names
    """
    catalog = get_catalog(branch)
    try:
        return [ns[0] for ns in catalog.list_namespaces()]
    except Exception:
        return []


def table_history(name: str, branch: str = "main") -> pd.DataFrame:
    """Get table snapshot history (time travel metadata).

    Args:
        name: Table name
        branch: Nessie branch

    Returns:
        DataFrame with snapshot info
    """
    catalog = get_catalog(branch)
    table = catalog.load_table(name)

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


def read_snapshot(name: str, snapshot_id: int, branch: str = "main") -> pd.DataFrame:
    """Read table at a specific snapshot (time travel).

    Args:
        name: Table name
        snapshot_id: Snapshot ID from table_history()
        branch: Nessie branch

    Returns:
        DataFrame at that point in time
    """
    catalog = get_catalog(branch)
    table = catalog.load_table(name)

    return table.scan(snapshot_id=snapshot_id).to_pandas()


def overwrite(name: str, df: pd.DataFrame, branch: str = "main") -> int:
    """Overwrite all data in a table.

    Args:
        name: Table name
        df: DataFrame to write
        branch: Nessie branch

    Returns:
        Number of rows written
    """
    catalog = get_catalog(branch)
    table = catalog.load_table(name)

    df = _fix_timestamp_precision(df)
    arrow_table = pa.Table.from_pandas(df)
    table.overwrite(arrow_table)

    return len(df)


def drop_table(name: str, branch: str = "main") -> None:
    """Drop a table.

    Args:
        name: Table name
        branch: Nessie branch
    """
    catalog = get_catalog(branch)
    catalog.drop_table(name)


def table_exists(name: str, branch: str = "main") -> bool:
    """Check if a table exists.

    Args:
        name: Table name
        branch: Nessie branch

    Returns:
        True if table exists
    """
    catalog = get_catalog(branch)
    try:
        catalog.load_table(name)
        return True
    except Exception:
        return False
