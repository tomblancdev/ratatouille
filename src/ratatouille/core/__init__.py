"""🐀 Core utilities for Ratatouille.

Storage operations (S3/MinIO) and dev mode utilities.

Note: For query operations, use the DuckDB engine:
    from ratatouille.workspace import Workspace
    ws = Workspace.load("my-workspace")
    engine = ws.get_engine()
    df = engine.query("SELECT * FROM ...")
"""

from ratatouille.core.dev import (
    dev_mode,
    enter_dev,
    exit_dev,
    get_effective_branch,
    is_dev_mode,
)
from ratatouille.core.storage import (
    delete_file,
    ensure_bucket,
    get_s3_client,
    get_s3_config,
    list_files,
    read_file,
    read_parquet,
    s3_path,
    write_parquet,
)

__all__ = [
    # Storage (S3/MinIO)
    "get_s3_client",
    "get_s3_config",
    "s3_path",
    "read_file",
    "read_parquet",
    "write_parquet",
    "list_files",
    "ensure_bucket",
    "delete_file",
    # Dev Mode
    "is_dev_mode",
    "get_effective_branch",
    "dev_mode",
    "enter_dev",
    "exit_dev",
]
