"""
🐀 Ratatouille Workspace Tools

Utility functions for exploring and working with workspace data.

Usage:
    from ratatouille.tools import (
        ls,           # List files in S3
        tables,       # List available tables
        schema,       # Get table schema
        preview,      # Preview table data (first N rows)
        s3_path,      # Get S3 path for a table
        s3_uri,       # Get full S3 URI
        layers,       # List medallion layers
        workspaces,   # List available workspaces
        products,     # List shared data products
        info,         # Get workspace info
    )

Or use the tools object:
    from ratatouille import tools

    tools.ls("bronze/")
    tools.tables()
"""

from ratatouille.tools.catalog import (
    columns,
    count,
    describe,
    layers,
    preview,
    schema,
    tables,
)
from ratatouille.tools.explorer import (
    bucket_name,
    find,
    ls,
    ls_recursive,
    s3_path,
    s3_uri,
    tree,
)
from ratatouille.tools.workspace import (
    connections,
    current_workspace,
    env,
    info,
    products,
    switch_workspace,
    workspaces,
)

__all__ = [
    # Explorer
    "ls",
    "ls_recursive",
    "tree",
    "find",
    "s3_path",
    "s3_uri",
    "bucket_name",
    # Catalog
    "tables",
    "schema",
    "columns",
    "preview",
    "count",
    "layers",
    "describe",
    # Workspace
    "info",
    "workspaces",
    "products",
    "current_workspace",
    "switch_workspace",
    "env",
    "connections",
]
