"""
🐀 Catalog Tools

Functions for exploring tables, schemas, and data in the workspace.
"""

import os
from dataclasses import dataclass
from typing import Any

import duckdb
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class TableInfo:
    """Information about a table."""

    name: str
    layer: str
    workspace: str
    path: str
    row_count: int | None = None
    columns: list[str] | None = None
    size_bytes: int | None = None

    @property
    def full_name(self) -> str:
        return f"{self.layer}.{self.name}"

    @property
    def size_human(self) -> str:
        if self.size_bytes is None:
            return "unknown"
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


@dataclass
class ColumnInfo:
    """Information about a column."""

    name: str
    dtype: str
    nullable: bool = True
    description: str | None = None


def _get_connection() -> duckdb.DuckDBPyConnection:
    """Get a configured DuckDB connection."""
    conn = duckdb.connect()

    # Configure S3/MinIO
    endpoint = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "ratatouille")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "ratatouille123")

    conn.execute(f"""
        SET s3_endpoint='{endpoint.replace("http://", "").replace("https://", "")}';
        SET s3_access_key_id='{access_key}';
        SET s3_secret_access_key='{secret_key}';
        SET s3_use_ssl=false;
        SET s3_url_style='path';
    """)

    return conn


def _get_workspace() -> str:
    return os.environ.get("RATATOUILLE_WORKSPACE", "demo")


def _get_bucket() -> str:
    return f"ratatouille-{_get_workspace()}"


def layers() -> list[str]:
    """List available medallion layers.

    Returns:
        List of layer names

    Example:
        >>> layers()
        ['bronze', 'silver', 'gold']
    """
    return ["bronze", "silver", "gold"]


def tables(
    layer: str | None = None,
    workspace: str | None = None,
    include_shared: bool = True,
) -> list[TableInfo]:
    """List available tables in the workspace.

    Args:
        layer: Filter by layer (bronze, silver, gold)
        workspace: Workspace name (default: current workspace)
        include_shared: Include shared data products

    Returns:
        List of TableInfo objects

    Example:
        >>> tables()
        [bronze.events, silver.events, gold.daily_sales, ...]
        >>> tables(layer="gold")
        [gold.daily_sales, gold.page_metrics, ...]
    """
    from ratatouille.tools.explorer import ls

    ws = workspace or _get_workspace()
    bucket = f"ratatouille-{ws}"

    table_list: list[TableInfo] = []
    search_layers = [layer] if layer else layers()

    for lyr in search_layers:
        # List folders in each layer
        objects = ls(f"{lyr}/", workspace=ws)

        for obj in objects:
            if obj.is_folder:
                table_name = obj.name
                path = f"s3://{bucket}/{lyr}/{table_name}/*.parquet"

                table_list.append(
                    TableInfo(
                        name=table_name,
                        layer=lyr,
                        workspace=ws,
                        path=path,
                    )
                )

    # Print table
    if table_list:
        tbl = Table(
            title=f"📊 Tables in {ws}", show_header=True, header_style="bold cyan"
        )
        tbl.add_column("Table")
        tbl.add_column("Layer")
        tbl.add_column("Path")

        for t in sorted(table_list, key=lambda x: (layers().index(x.layer), x.name)):
            layer_color = {
                "bronze": "yellow",
                "silver": "white",
                "gold": "bright_yellow",
            }[t.layer]
            tbl.add_row(
                t.name,
                f"[{layer_color}]{t.layer}[/{layer_color}]",
                t.path,
            )

        console.print(tbl)

    return table_list


def schema(table: str, layer: str | None = None) -> list[ColumnInfo]:
    """Get schema for a table.

    Args:
        table: Table name (can include layer like 'silver.events')
        layer: Layer name (if not included in table name)

    Returns:
        List of ColumnInfo objects

    Example:
        >>> schema("silver.events")
        [event_id: VARCHAR, user_id: VARCHAR, event_type: VARCHAR, ...]
        >>> schema("events", layer="silver")
        [event_id: VARCHAR, user_id: VARCHAR, event_type: VARCHAR, ...]
    """
    # Parse table name
    if "." in table:
        layer, table = table.split(".", 1)
    elif layer is None:
        # Try to find the table in any layer
        for lyr in layers():
            try:
                return schema(table, lyr)
            except Exception:
                continue
        raise ValueError(f"Table '{table}' not found in any layer")

    bucket = _get_bucket()
    path = f"s3://{bucket}/{layer}/{table}/*.parquet"

    conn = _get_connection()
    try:
        # Use DESCRIBE to get schema
        result = conn.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{path}')"
        ).fetchall()

        columns: list[ColumnInfo] = []
        for row in result:
            columns.append(
                ColumnInfo(
                    name=row[0],
                    dtype=row[1],
                    nullable=row[2] == "YES" if len(row) > 2 else True,
                )
            )

        # Print table
        tbl = Table(
            title=f"📋 Schema: {layer}.{table}",
            show_header=True,
            header_style="bold cyan",
        )
        tbl.add_column("Column")
        tbl.add_column("Type")
        tbl.add_column("Nullable")

        for col in columns:
            tbl.add_row(col.name, col.dtype, "✓" if col.nullable else "✗")

        console.print(tbl)

        return columns

    finally:
        conn.close()


def columns(table: str, layer: str | None = None) -> list[str]:
    """Get column names for a table.

    Args:
        table: Table name
        layer: Layer name (optional if table includes layer)

    Returns:
        List of column names

    Example:
        >>> columns("silver.events")
        ['event_id', 'user_id', 'event_type', 'page_url', ...]
    """
    schema_info = schema(table, layer)
    return [col.name for col in schema_info]


def count(table: str, layer: str | None = None) -> int:
    """Get row count for a table.

    Args:
        table: Table name
        layer: Layer name (optional)

    Returns:
        Number of rows

    Example:
        >>> count("silver.events")
        1234567
    """
    # Parse table name
    if "." in table:
        layer, table = table.split(".", 1)
    elif layer is None:
        raise ValueError(
            "Layer must be specified or included in table name (e.g., 'silver.events')"
        )

    bucket = _get_bucket()
    path = f"s3://{bucket}/{layer}/{table}/*.parquet"

    conn = _get_connection()
    try:
        result = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()
        row_count = result[0] if result else 0

        console.print(f"📊 {layer}.{table}: [bold]{row_count:,}[/bold] rows")

        return row_count
    finally:
        conn.close()


def preview(
    table: str,
    layer: str | None = None,
    limit: int = 10,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Preview data from a table.

    Args:
        table: Table name
        layer: Layer name (optional)
        limit: Number of rows to show
        columns: Specific columns to show

    Returns:
        DataFrame with preview data

    Example:
        >>> preview("silver.events")
              event_id    user_id  event_type
        0     abc123      user1    PAGEVIEW
        1     def456      user2    CLICK
        ...
        >>> preview("silver.events", columns=["event_type"], limit=5)
    """
    # Parse table name
    if "." in table:
        layer, table = table.split(".", 1)
    elif layer is None:
        raise ValueError("Layer must be specified or included in table name")

    bucket = _get_bucket()
    path = f"s3://{bucket}/{layer}/{table}/*.parquet"

    # Build column list
    col_expr = ", ".join(columns) if columns else "*"

    conn = _get_connection()
    try:
        df = conn.execute(
            f"SELECT {col_expr} FROM read_parquet('{path}') LIMIT {limit}"
        ).fetchdf()

        console.print(f"\n📊 Preview: {layer}.{table} ({limit} rows)\n")
        console.print(df.to_string())

        return df
    finally:
        conn.close()


def describe(table: str, layer: str | None = None) -> dict[str, Any]:
    """Get detailed statistics about a table.

    Args:
        table: Table name
        layer: Layer name (optional)

    Returns:
        Dict with table statistics

    Example:
        >>> describe("silver.events")
        {
            'name': 'events',
            'layer': 'silver',
            'row_count': 1234567,
            'columns': ['event_id', 'user_id', ...],
            'size': '45.2 MB',
            'path': 's3://...'
        }
    """
    # Parse table name
    if "." in table:
        layer, table = table.split(".", 1)
    elif layer is None:
        raise ValueError("Layer must be specified")

    bucket = _get_bucket()
    path = f"s3://{bucket}/{layer}/{table}/*.parquet"

    conn = _get_connection()
    try:
        # Get row count
        row_count = conn.execute(
            f"SELECT COUNT(*) FROM read_parquet('{path}')"
        ).fetchone()[0]

        # Get schema
        schema_info = conn.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{path}')"
        ).fetchall()
        cols = [row[0] for row in schema_info]

        info = {
            "name": table,
            "layer": layer,
            "full_name": f"{layer}.{table}",
            "row_count": row_count,
            "columns": cols,
            "column_count": len(cols),
            "path": path,
        }

        # Print panel
        console.print(
            Panel(
                f"""[bold]Table:[/bold] {layer}.{table}
[bold]Rows:[/bold] {row_count:,}
[bold]Columns:[/bold] {len(cols)} ({", ".join(cols[:5])}{"..." if len(cols) > 5 else ""})
[bold]Path:[/bold] {path}""",
                title=f"📊 {layer}.{table}",
                border_style="cyan",
            )
        )

        return info

    finally:
        conn.close()
