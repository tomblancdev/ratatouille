"""🐀 Iceberg utilities - Lakehouse table format with SQLite catalog.

Uses PyIceberg with SQLite for metadata storage and MinIO for data files.
No external catalog service needed!
"""

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog


def _fix_timestamp_precision(df: pd.DataFrame) -> pd.DataFrame:
    """Convert nanosecond timestamps to microseconds for Iceberg compatibility."""
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            # Convert ns to us precision
            df[col] = df[col].astype("datetime64[us]")
    return df


@lru_cache
def get_catalog():
    """Get the Iceberg catalog (cached singleton).

    Uses SQLite for metadata (lightweight, no extra service).
    Data files stored in MinIO.
    """
    # SQLite catalog stored in workspaces directory (mounted volume)
    catalog_path = os.getenv("ICEBERG_CATALOG_PATH", "/app/workspaces/.iceberg")

    # Create directory with proper error handling
    try:
        Path(catalog_path).mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Fallback to home directory if /app is not writable
        import tempfile

        catalog_path = os.path.join(tempfile.gettempdir(), "ratatouille-iceberg")
        Path(catalog_path).mkdir(parents=True, exist_ok=True)
        print(f"⚠️ Using fallback catalog path: {catalog_path}")

    def _require_env(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise OSError(
                f"Missing required environment variable: {name}\n"
                f"Make sure you have a .env file. See .env.example for reference."
            )
        return value

    warehouse_path = os.getenv("ICEBERG_WAREHOUSE", "s3://warehouse/")
    s3_endpoint = _require_env("S3_ENDPOINT")
    s3_access_key = _require_env("S3_ACCESS_KEY")
    s3_secret_key = _require_env("S3_SECRET_KEY")

    return SqlCatalog(
        "ratatouille",
        **{
            "uri": f"sqlite:///{catalog_path}/catalog.db",
            "warehouse": warehouse_path,
            "s3.endpoint": s3_endpoint,
            "s3.access-key-id": s3_access_key,
            "s3.secret-access-key": s3_secret_key,
            "s3.path-style-access": "true",  # Required for MinIO
        },
    )


def ensure_namespace(namespace: str) -> None:
    """Create namespace if it doesn't exist."""
    catalog = get_catalog()
    try:
        catalog.create_namespace(namespace)
        print(f"📁 Created namespace: {namespace}")
    except Exception:
        pass  # Already exists


def create_table(
    name: str,
    df: pd.DataFrame,
    partition_by: list[str] | None = None,
) -> str:
    """Create an Iceberg table from a DataFrame.

    Args:
        name: Table name (e.g., "bronze.transactions")
        df: DataFrame to create table from
        partition_by: Optional partition columns

    Returns:
        Full table identifier

    Example:
        create_table("bronze.sales", df, partition_by=["year", "month"])
    """
    catalog = get_catalog()

    # Ensure namespace exists
    namespace = name.split(".")[0] if "." in name else "default"
    ensure_namespace(namespace)

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

    print(f"✅ Created table: {name} ({len(df)} rows)")
    return name


def append(name: str, df: pd.DataFrame) -> int:
    """Append data to an existing Iceberg table.

    Args:
        name: Table name (e.g., "bronze.transactions")
        df: DataFrame to append

    Returns:
        Number of rows appended

    Example:
        append("bronze.transactions", new_df)
    """
    catalog = get_catalog()
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
) -> dict:
    """Merge (upsert) data into an Iceberg table.

    Deduplicates by merge_keys, keeping the latest record.

    Args:
        name: Table name
        df: DataFrame with new/updated records
        merge_keys: Columns that form unique key

    Returns:
        Dict with stats: {"inserted": n, "updated": n}

    Example:
        merge("silver.transactions", df, merge_keys=["date", "store_id", "product_id"])
    """
    catalog = get_catalog()

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
        create_table(name, df)
        inserted = len(df)
        updated = 0

    return {"inserted": max(0, inserted), "updated": max(0, updated)}


def read_table(name: str, where: str | None = None) -> pd.DataFrame:
    """Read an Iceberg table into a DataFrame.

    Args:
        name: Table name
        where: Optional filter expression (not implemented yet)

    Returns:
        DataFrame with table data

    Example:
        df = read_table("silver.transactions")
    """
    catalog = get_catalog()
    table = catalog.load_table(name)

    scan = table.scan()
    return scan.to_pandas()


def list_tables(namespace: str = "bronze") -> list[str]:
    """List all tables in a namespace."""
    catalog = get_catalog()
    try:
        ensure_namespace(namespace)
        return [t[1] for t in catalog.list_tables(namespace)]
    except Exception:
        return []


def list_namespaces() -> list[str]:
    """List all namespaces (bronze, silver, gold, etc.)."""
    catalog = get_catalog()
    try:
        return [ns[0] for ns in catalog.list_namespaces()]
    except Exception:
        return []


def table_history(name: str) -> pd.DataFrame:
    """Get table snapshot history (time travel metadata).

    Args:
        name: Table name

    Returns:
        DataFrame with snapshot info
    """
    catalog = get_catalog()
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


def read_snapshot(name: str, snapshot_id: int) -> pd.DataFrame:
    """Read table at a specific snapshot (time travel).

    Args:
        name: Table name
        snapshot_id: Snapshot ID from table_history()

    Returns:
        DataFrame at that point in time
    """
    catalog = get_catalog()
    table = catalog.load_table(name)

    return table.scan(snapshot_id=snapshot_id).to_pandas()


# =========================================================================
# Iceberg Branch Operations (Dev Mode)
# =========================================================================


def create_branch(table: str, branch_name: str) -> str:
    """Create a new branch from current snapshot.

    Branches are metadata-only - no data is copied until you write.
    Uses Iceberg's native branching for zero-copy isolation.

    Args:
        table: Table name (e.g., "bronze.sales")
        branch_name: Name for the new branch

    Returns:
        The branch name

    Raises:
        ValueError: If table has no snapshots yet

    Example:
        create_branch("bronze.sales", "feature/new-cleaning")
    """
    catalog = get_catalog()
    ice_table = catalog.load_table(table)

    # Get current snapshot ID
    current = ice_table.current_snapshot()
    if current is None:
        raise ValueError(f"Table {table} has no snapshots yet")

    # Create branch pointing to current snapshot
    ice_table.manage_snapshots().create_branch(
        snapshot_id=current.snapshot_id, branch_name=branch_name
    ).commit()

    return branch_name


def list_branches(table: str) -> list[dict]:
    """List all branches for a table.

    Args:
        table: Table name

    Returns:
        List of dicts with branch info: [{"name": "main", "type": "branch"}, ...]

    Example:
        branches = list_branches("bronze.sales")
        # → [{"name": "main", "type": "branch"}, {"name": "dev/feature", "type": "branch"}]
    """
    catalog = get_catalog()
    ice_table = catalog.load_table(table)

    branches = []
    for ref_name, ref in ice_table.metadata.refs.items():
        branches.append(
            {
                "name": ref_name,
                "type": ref.snapshot_ref_type,
                "snapshot_id": ref.snapshot_id,
            }
        )

    return branches


def drop_branch(table: str, branch_name: str) -> None:
    """Delete a branch.

    Cannot delete the main branch.

    Args:
        table: Table name
        branch_name: Branch to delete

    Raises:
        ValueError: If trying to delete main branch

    Example:
        drop_branch("bronze.sales", "feature/abandoned")
    """
    if branch_name == "main":
        raise ValueError("Cannot delete main branch")

    catalog = get_catalog()
    ice_table = catalog.load_table(table)
    ice_table.manage_snapshots().remove_branch(branch_name).commit()


def read_branch(table: str, branch_name: str) -> pd.DataFrame:
    """Read table at a specific branch.

    Args:
        table: Table name
        branch_name: Branch to read from

    Returns:
        DataFrame with table data at that branch

    Example:
        df = read_branch("bronze.sales", "feature/new-cleaning")
    """
    catalog = get_catalog()
    ice_table = catalog.load_table(table)

    # Get snapshot ID from branch reference
    refs = ice_table.metadata.refs
    if branch_name not in refs:
        raise ValueError(f"Branch '{branch_name}' not found in table {table}")

    snapshot_id = refs[branch_name].snapshot_id
    return ice_table.scan(snapshot_id=snapshot_id).to_pandas()


def append_to_branch(table: str, df: pd.DataFrame, branch_name: str) -> int:
    """Append data to a specific branch.

    Uses copy-on-write - only the new data is written, existing data
    is shared with other branches.

    Args:
        table: Table name
        df: DataFrame to append
        branch_name: Branch to append to

    Returns:
        Number of rows appended

    Example:
        append_to_branch("bronze.sales", df, "feature/new-data")
    """
    catalog = get_catalog()
    ice_table = catalog.load_table(table)

    # Fix timestamp precision (ns → us) for Iceberg compatibility
    df = _fix_timestamp_precision(df)

    arrow_table = pa.Table.from_pandas(df)
    ice_table.append(arrow_table, branch=branch_name)

    return len(df)


def overwrite_branch(table: str, df: pd.DataFrame, branch_name: str) -> int:
    """Overwrite data on a specific branch.

    Replaces all data on the branch. Other branches are not affected.

    Args:
        table: Table name
        df: DataFrame to write
        branch_name: Branch to overwrite

    Returns:
        Number of rows written

    Example:
        overwrite_branch("silver.sales", df, "feature/new-cleaning")
    """
    catalog = get_catalog()
    ice_table = catalog.load_table(table)

    # Fix timestamp precision (ns → us) for Iceberg compatibility
    df = _fix_timestamp_precision(df)

    arrow_table = pa.Table.from_pandas(df)
    ice_table.overwrite(arrow_table, branch=branch_name)

    return len(df)


def merge_to_branch(
    table: str,
    df: pd.DataFrame,
    merge_keys: list[str],
    branch_name: str,
) -> dict:
    """Merge (upsert) data into a specific branch.

    Deduplicates by merge_keys, keeping the latest record.

    Args:
        table: Table name
        df: DataFrame with new/updated records
        merge_keys: Columns that form unique key
        branch_name: Branch to merge into

    Returns:
        Dict with stats: {"inserted": n, "updated": n}

    Example:
        stats = merge_to_branch("silver.sales", df, ["id"], "feature/updates")
    """
    catalog = get_catalog()

    # Fix timestamp precision (ns → us) for Iceberg compatibility
    df = _fix_timestamp_precision(df)

    try:
        ice_table = catalog.load_table(table)

        # Read existing data from branch
        existing_df = ice_table.scan(branch=branch_name).to_pandas()

        # Combine and dedupe
        combined = pd.concat([existing_df, df], ignore_index=True)
        combined = combined.drop_duplicates(subset=merge_keys, keep="last")

        # Fix timestamps again after concat
        combined = _fix_timestamp_precision(combined)

        # Overwrite on branch
        arrow_table = pa.Table.from_pandas(combined)
        ice_table.overwrite(arrow_table, branch=branch_name)

        inserted = len(combined) - len(existing_df)
        updated = len(df) - inserted

    except Exception:
        # Table doesn't exist, create it
        create_table(table, df)
        # Then create the branch
        create_branch(table, branch_name)
        inserted = len(df)
        updated = 0

    return {"inserted": max(0, inserted), "updated": max(0, updated)}


def fast_forward_branch(table: str, source: str, target: str = "main") -> dict:
    """Merge source branch to target by copying data.

    Reads the data from the source branch and overwrites the target branch.
    This effectively merges the changes from source to target.

    Args:
        table: Table name
        source: Source branch name
        target: Target branch name (default: "main")

    Returns:
        Dict with merge info

    Raises:
        ValueError: If source and target are the same

    Example:
        fast_forward_branch("bronze.sales", "feature/done", "main")
    """
    if source == target:
        raise ValueError("Cannot merge branch into itself")

    catalog = get_catalog()
    ice_table = catalog.load_table(table)

    # Get snapshot ID from source branch
    refs = ice_table.metadata.refs
    if source not in refs:
        raise ValueError(f"Branch '{source}' not found in table {table}")

    # Read data from source branch
    source_snapshot_id = refs[source].snapshot_id
    source_df = ice_table.scan(snapshot_id=source_snapshot_id).to_pandas()

    # Fix timestamp precision
    source_df = _fix_timestamp_precision(source_df)

    # Overwrite target branch with source data
    arrow_table = pa.Table.from_pandas(source_df)
    ice_table.overwrite(arrow_table, branch=target)

    return {"merged": source, "into": target, "table": table, "rows": len(source_df)}
