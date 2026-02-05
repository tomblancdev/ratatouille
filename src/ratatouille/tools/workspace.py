"""
🐀 Workspace Tools

Functions for managing and exploring workspaces.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class WorkspaceInfo:
    """Information about a workspace."""

    name: str
    description: str
    version: str
    path: str | None = None
    nessie_branch: str | None = None
    s3_prefix: str | None = None


@dataclass
class ProductInfo:
    """Information about a shared data product."""

    name: str
    source_workspace: str
    version: str
    description: str | None = None
    schema: list[str] | None = None


def current_workspace() -> str:
    """Get the current workspace name.

    Returns:
        Current workspace name

    Example:
        >>> current_workspace()
        'demo'
    """
    return os.environ.get("RATATOUILLE_WORKSPACE", "demo")


def switch_workspace(name: str) -> None:
    """Switch to a different workspace.

    Note: This only affects the current Python process.
    For persistent change, set RATATOUILLE_WORKSPACE env var.

    Args:
        name: Workspace name

    Example:
        >>> switch_workspace("analytics")
        Switched to workspace: analytics
    """
    os.environ["RATATOUILLE_WORKSPACE"] = name
    console.print(f"✅ Switched to workspace: [bold]{name}[/bold]")


def info(workspace: str | None = None) -> WorkspaceInfo:
    """Get information about a workspace.

    Args:
        workspace: Workspace name (default: current workspace)

    Returns:
        WorkspaceInfo object

    Example:
        >>> info()
        WorkspaceInfo(name='demo', description='Demo workspace...', ...)
    """
    ws = workspace or current_workspace()

    # Try to load workspace.yaml
    workspace_paths = [
        Path("/workspace/workspace.yaml"),  # DevContainer
        Path(f"/app/workspaces/{ws}/workspace.yaml"),  # Docker
        Path(f"workspaces/{ws}/workspace.yaml"),  # Local
    ]

    config = {}
    ws_path = None

    for path in workspace_paths:
        if path.exists():
            with open(path) as f:
                config = yaml.safe_load(f) or {}
            ws_path = str(path.parent)
            break

    isolation = config.get("isolation", {})

    workspace_info = WorkspaceInfo(
        name=config.get("name", ws),
        description=config.get("description", "").strip(),
        version=config.get("version", "unknown"),
        path=ws_path,
        nessie_branch=isolation.get("nessie_branch", f"workspace/{ws}"),
        s3_prefix=isolation.get("s3_prefix", ws),
    )

    # Print panel
    console.print(
        Panel(
            f"""[bold]Name:[/bold] {workspace_info.name}
[bold]Version:[/bold] {workspace_info.version}
[bold]Description:[/bold] {workspace_info.description[:100]}{"..." if len(workspace_info.description) > 100 else ""}

[bold]Isolation:[/bold]
  Nessie Branch: {workspace_info.nessie_branch}
  S3 Prefix: {workspace_info.s3_prefix}
  Bucket: ratatouille-{workspace_info.name}

[bold]Path:[/bold] {workspace_info.path or "unknown"}""",
            title=f"🐀 Workspace: {workspace_info.name}",
            border_style="cyan",
        )
    )

    return workspace_info


def workspaces() -> list[str]:
    """List available workspaces.

    Returns:
        List of workspace names

    Example:
        >>> workspaces()
        ['demo', 'analytics', 'sales']
    """
    workspace_dirs = [
        Path("/app/workspaces"),
        Path("workspaces"),
    ]

    found_workspaces = []

    for ws_dir in workspace_dirs:
        if ws_dir.exists():
            for path in ws_dir.iterdir():
                if path.is_dir() and (path / "workspace.yaml").exists():
                    found_workspaces.append(path.name)

    # Remove duplicates
    found_workspaces = list(set(found_workspaces))

    if found_workspaces:
        current = current_workspace()
        tbl = Table(
            title="📦 Available Workspaces", show_header=True, header_style="bold cyan"
        )
        tbl.add_column("Workspace")
        tbl.add_column("Status")

        for ws in sorted(found_workspaces):
            status = "[green]● current[/green]" if ws == current else ""
            tbl.add_row(ws, status)

        console.print(tbl)

    return found_workspaces


def products(workspace: str | None = None) -> list[ProductInfo]:
    """List available data products (shared tables from other workspaces).

    Args:
        workspace: Workspace to check subscriptions for

    Returns:
        List of ProductInfo objects

    Example:
        >>> products()
        [ProductInfo(name='shared.customers', source='crm', version='1.2.0'), ...]
    """
    # TODO: Implement when data products registry is ready
    # For now, return empty list

    console.print("[dim]No shared data products configured.[/dim]")
    console.print("[dim]Use data products to share tables across workspaces.[/dim]")

    return []


def env() -> dict[str, str]:
    """Get current environment configuration.

    Returns:
        Dict of environment variables

    Example:
        >>> env()
        {
            'RATATOUILLE_WORKSPACE': 'demo',
            'MINIO_ENDPOINT': 'http://minio:9000',
            ...
        }
    """
    env_vars = {
        "RATATOUILLE_WORKSPACE": os.environ.get("RATATOUILLE_WORKSPACE", "demo"),
        "MINIO_ENDPOINT": os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        "MINIO_ACCESS_KEY": os.environ.get("MINIO_ACCESS_KEY", "ratatouille"),
        "NESSIE_URI": os.environ.get("NESSIE_URI", "http://localhost:19120/api/v1"),
    }

    tbl = Table(title="🔧 Environment", show_header=True, header_style="bold cyan")
    tbl.add_column("Variable")
    tbl.add_column("Value")

    for key, value in env_vars.items():
        # Mask secrets
        display_value = value
        if "SECRET" in key or "KEY" in key:
            display_value = value[:4] + "****" if value else ""
        tbl.add_row(key, display_value)

    console.print(tbl)

    return env_vars


def connections() -> dict[str, bool]:
    """Check connectivity to required services.

    Returns:
        Dict of service name -> connected status

    Example:
        >>> connections()
        {'minio': True, 'nessie': True}
    """
    import httpx

    services = {
        "minio": os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
        + "/minio/health/live",
        "nessie": os.environ.get("NESSIE_URI", "http://localhost:19120/api/v1")
        + "/config",
    }

    results = {}

    tbl = Table(
        title="🔌 Service Connections", show_header=True, header_style="bold cyan"
    )
    tbl.add_column("Service")
    tbl.add_column("Status")
    tbl.add_column("Endpoint")

    for name, url in services.items():
        try:
            response = httpx.get(url, timeout=5)
            connected = response.status_code < 400
        except Exception:
            connected = False

        results[name] = connected
        status = (
            "[green]● Connected[/green]" if connected else "[red]✗ Disconnected[/red]"
        )
        tbl.add_row(name, status, url.rsplit("/", 1)[0])

    console.print(tbl)

    return results
