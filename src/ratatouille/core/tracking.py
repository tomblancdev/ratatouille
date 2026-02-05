"""🐀 File Tracking - Avoid re-ingesting files.

Tracks ingested files in a metadata table (bronze._file_registry).
Check before ingesting, mark as done after.
"""

import hashlib
from datetime import datetime
from io import BytesIO

import pandas as pd


def compute_file_hash(data: BytesIO) -> str:
    """Compute MD5 hash of file contents."""
    data.seek(0)
    file_hash = hashlib.md5(data.read()).hexdigest()
    data.seek(0)  # Reset for later reading
    return file_hash


def get_registry_table() -> str:
    """Get the registry table name."""
    return "bronze._file_registry"


def init_registry():
    """Initialize the file registry table if it doesn't exist."""
    from ratatouille.core.iceberg import ensure_namespace, get_catalog

    catalog = get_catalog()
    table_name = get_registry_table()

    # Ensure bronze namespace exists
    ensure_namespace("bronze")

    # Check if table exists
    try:
        catalog.load_table(table_name)
        return  # Already exists
    except Exception:
        pass

    # Create empty registry table
    df = pd.DataFrame(
        {
            "file_path": pd.Series(dtype="str"),
            "file_hash": pd.Series(dtype="str"),
            "target_table": pd.Series(dtype="str"),
            "rows_ingested": pd.Series(dtype="int64"),
            "ingested_at": pd.Series(dtype="datetime64[us]"),
            "status": pd.Series(dtype="str"),  # "success", "failed", "skipped"
        }
    )

    from ratatouille.core.iceberg import create_table

    create_table(table_name, df)
    print("📋 Created file registry table")


def is_file_ingested(file_path: str, file_hash: str | None = None) -> bool:
    """Check if a file has already been ingested.

    Args:
        file_path: S3 path of the file
        file_hash: Optional hash to check (if None, checks by path only)

    Returns:
        True if file was already ingested successfully
    """
    from ratatouille.core.iceberg import read_table

    try:
        registry = read_table(get_registry_table())
    except Exception:
        return False  # Registry doesn't exist yet

    if registry.empty:
        return False

    # Check by path
    matches = registry[
        (registry["file_path"] == file_path) & (registry["status"] == "success")
    ]

    if file_hash and not matches.empty:
        # Also verify hash matches (file wasn't modified)
        matches = matches[matches["file_hash"] == file_hash]

    return not matches.empty


def mark_file_ingested(
    file_path: str,
    file_hash: str,
    target_table: str,
    rows_ingested: int,
    status: str = "success",
):
    """Mark a file as ingested in the registry.

    Args:
        file_path: S3 path of the file
        file_hash: MD5 hash of file contents
        target_table: Target Iceberg table
        rows_ingested: Number of rows ingested
        status: "success", "failed", or "skipped"
    """
    from ratatouille.core.iceberg import append, create_table

    init_registry()  # Ensure registry exists

    record = pd.DataFrame(
        [
            {
                "file_path": file_path,
                "file_hash": file_hash,
                "target_table": target_table,
                "rows_ingested": rows_ingested,
                "ingested_at": datetime.utcnow(),
                "status": status,
            }
        ]
    )

    try:
        append(get_registry_table(), record)
    except Exception:
        create_table(get_registry_table(), record)


def get_ingestion_history(target_table: str | None = None) -> pd.DataFrame:
    """Get ingestion history from registry.

    Args:
        target_table: Filter by target table (optional)

    Returns:
        DataFrame with ingestion history
    """
    from ratatouille.core.iceberg import read_table

    try:
        registry = read_table(get_registry_table())
    except Exception:
        return pd.DataFrame()

    if target_table and not registry.empty:
        registry = registry[registry["target_table"] == target_table]

    return registry.sort_values("ingested_at", ascending=False)
