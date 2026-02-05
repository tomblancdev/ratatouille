"""
🐀 S3/MinIO Explorer Tools

Functions for exploring files and paths in the workspace storage.
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

import boto3
from botocore.client import Config
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

console = Console()


@dataclass
class S3Object:
    """Represents an object in S3."""
    key: str
    size: int
    last_modified: datetime
    is_folder: bool = False

    @property
    def name(self) -> str:
        return self.key.split("/")[-1] if not self.is_folder else self.key.rstrip("/").split("/")[-1]

    @property
    def size_human(self) -> str:
        """Human-readable size."""
        if self.is_folder:
            return "-"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if self.size < 1024:
                return f"{self.size:.1f} {unit}"
            self.size /= 1024
        return f"{self.size:.1f} PB"


def _get_s3_client():
    """Get configured S3 client."""
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY", "ratatouille"),
        aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY", "ratatouille123"),
        config=Config(signature_version="s3v4"),
    )


def _get_workspace() -> str:
    """Get current workspace name."""
    return os.environ.get("RATATOUILLE_WORKSPACE", "demo")


def bucket_name(workspace: str | None = None) -> str:
    """Get the S3 bucket name for a workspace.

    Args:
        workspace: Workspace name (default: current workspace)

    Returns:
        Bucket name like 'ratatouille-demo'

    Example:
        >>> bucket_name()
        'ratatouille-demo'
        >>> bucket_name("analytics")
        'ratatouille-analytics'
    """
    ws = workspace or _get_workspace()
    return f"ratatouille-{ws}"


def s3_path(layer: str, table: str, workspace: str | None = None) -> str:
    """Get the S3 path for a table.

    Args:
        layer: Medallion layer (bronze, silver, gold)
        table: Table name
        workspace: Workspace name (default: current workspace)

    Returns:
        S3 path like 'bronze/events/'

    Example:
        >>> s3_path("silver", "events")
        'silver/events/'
    """
    return f"{layer}/{table}/"


def s3_uri(
    layer: str,
    table: str,
    workspace: str | None = None,
    pattern: str = "*.parquet",
) -> str:
    """Get the full S3 URI for a table.

    Args:
        layer: Medallion layer (bronze, silver, gold)
        table: Table name
        workspace: Workspace name (default: current workspace)
        pattern: File pattern (default: *.parquet)

    Returns:
        Full S3 URI like 's3://ratatouille-demo/silver/events/*.parquet'

    Example:
        >>> s3_uri("silver", "events")
        's3://ratatouille-demo/silver/events/*.parquet'
        >>> s3_uri("bronze", "raw", pattern="*.json")
        's3://ratatouille-demo/bronze/raw/*.json'
    """
    bucket = bucket_name(workspace)
    path = s3_path(layer, table, workspace)
    return f"s3://{bucket}/{path}{pattern}"


def ls(
    path: str = "",
    workspace: str | None = None,
    show_size: bool = True,
    show_date: bool = True,
) -> list[S3Object]:
    """List files and folders in S3.

    Args:
        path: Path within workspace (e.g., 'bronze/', 'silver/events/')
        workspace: Workspace name (default: current workspace)
        show_size: Show file sizes
        show_date: Show modification dates

    Returns:
        List of S3Object

    Example:
        >>> ls()  # List root
        [bronze/, silver/, gold/]
        >>> ls("bronze/")
        [events/, sales/]
        >>> ls("bronze/events/")
        [data_20240101.parquet, data_20240102.parquet, ...]
    """
    s3 = _get_s3_client()
    bucket = bucket_name(workspace)

    # Normalize path
    prefix = path.strip("/")
    if prefix:
        prefix += "/"

    try:
        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            Delimiter="/",
        )
    except Exception as e:
        console.print(f"[red]Error listing {bucket}/{prefix}: {e}[/red]")
        return []

    objects: list[S3Object] = []

    # Add folders (CommonPrefixes)
    for prefix_obj in response.get("CommonPrefixes", []):
        folder_path = prefix_obj["Prefix"]
        objects.append(
            S3Object(
                key=folder_path,
                size=0,
                last_modified=datetime.min,
                is_folder=True,
            )
        )

    # Add files
    for obj in response.get("Contents", []):
        # Skip the prefix itself
        if obj["Key"] == prefix:
            continue
        objects.append(
            S3Object(
                key=obj["Key"],
                size=obj["Size"],
                last_modified=obj["LastModified"].replace(tzinfo=None),
                is_folder=False,
            )
        )

    # Print table
    if objects:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Name")
        if show_size:
            table.add_column("Size", justify="right")
        if show_date:
            table.add_column("Modified")

        for obj in sorted(objects, key=lambda x: (not x.is_folder, x.key)):
            name = f"📁 {obj.name}/" if obj.is_folder else f"   {obj.name}"
            row = [name]
            if show_size:
                row.append(obj.size_human)
            if show_date:
                row.append(obj.last_modified.strftime("%Y-%m-%d %H:%M") if not obj.is_folder else "")
            table.add_row(*row)

        console.print(table)

    return objects


def ls_recursive(
    path: str = "",
    workspace: str | None = None,
    pattern: str = "*",
) -> list[S3Object]:
    """List all files recursively in S3.

    Args:
        path: Path within workspace
        workspace: Workspace name (default: current workspace)
        pattern: Glob pattern to filter files

    Returns:
        List of all S3Object (files only)

    Example:
        >>> ls_recursive("bronze/")
        [bronze/events/data1.parquet, bronze/sales/data1.parquet, ...]
    """
    s3 = _get_s3_client()
    bucket = bucket_name(workspace)

    prefix = path.strip("/")
    if prefix:
        prefix += "/"

    objects: list[S3Object] = []
    paginator = s3.get_paginator("list_objects_v2")

    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                # Apply pattern filter
                key = obj["Key"]
                if pattern != "*":
                    import fnmatch
                    if not fnmatch.fnmatch(key.split("/")[-1], pattern):
                        continue

                objects.append(
                    S3Object(
                        key=key,
                        size=obj["Size"],
                        last_modified=obj["LastModified"].replace(tzinfo=None),
                        is_folder=False,
                    )
                )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return []

    return objects


def tree(path: str = "", workspace: str | None = None, max_depth: int = 3) -> None:
    """Display folder structure as a tree.

    Args:
        path: Starting path
        workspace: Workspace name (default: current workspace)
        max_depth: Maximum depth to display

    Example:
        >>> tree()
        📦 ratatouille-demo
        ├── 📁 bronze
        │   ├── 📁 events
        │   └── 📁 sales
        ├── 📁 silver
        │   └── 📁 events
        └── 📁 gold
            └── 📁 daily_sales
    """
    bucket = bucket_name(workspace)
    root = Tree(f"📦 {bucket}")

    def add_level(parent: Tree, prefix: str, depth: int):
        if depth >= max_depth:
            return

        objects = ls(prefix, workspace)
        for obj in objects:
            if obj.is_folder:
                folder_name = obj.name
                child = parent.add(f"📁 {folder_name}")
                add_level(child, obj.key, depth + 1)
            else:
                parent.add(f"📄 {obj.name}")

    add_level(root, path, 0)
    console.print(root)


def find(
    pattern: str,
    path: str = "",
    workspace: str | None = None,
) -> list[str]:
    """Find files matching a pattern.

    Args:
        pattern: Glob pattern (e.g., '*.parquet', 'events*')
        path: Path to search in
        workspace: Workspace name (default: current workspace)

    Returns:
        List of matching S3 keys

    Example:
        >>> find("*.parquet", "bronze/")
        ['bronze/events/data1.parquet', 'bronze/sales/data1.parquet']
        >>> find("events*")
        ['bronze/events/', 'silver/events/']
    """
    objects = ls_recursive(path, workspace, pattern)
    keys = [obj.key for obj in objects]

    if keys:
        for key in keys:
            console.print(f"  {key}")

    return keys
