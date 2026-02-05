"""🐀 Ratatouille SDK - Minimal interface for file-first pipeline development.

Pipelines are defined as files (SQL/Python + YAML), and this SDK provides
simple operations for running and exploring.

Example:
    from ratatouille import run, workspace, query

    # Load workspace and run pipelines
    workspace("analytics")
    run("silver.sales")
    run("gold.daily_kpis", full_refresh=True)

    # Quick queries (for notebooks)
    df = query("SELECT * FROM bronze.sales LIMIT 100")
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from ratatouille.workspace.manager import Workspace

# Module-level state
_workspace: Workspace | None = None


def workspace(name: str | None = None) -> Workspace:
    """Load or get current workspace.

    Args:
        name: Workspace name (default: from $RATATOUILLE_WORKSPACE env or "default")

    Returns:
        Loaded Workspace instance

    Example:
        ws = workspace("analytics")
        print(ws.name, ws.nessie_branch)
    """
    global _workspace
    from ratatouille.workspace.manager import Workspace

    if name is None:
        name = os.getenv("RATATOUILLE_WORKSPACE", "default")

    if _workspace is None or _workspace.name != name:
        _workspace = Workspace.load(name)

    return _workspace


def list_workspaces() -> list[str]:
    """List all available workspaces.

    Returns:
        List of workspace names

    Example:
        workspaces = list_workspaces()
        # ['default', 'analytics', 'demo']
    """
    from ratatouille.workspace.manager import list_workspaces as _list

    return _list()


def run(pipeline: str, full_refresh: bool = False) -> dict[str, Any]:
    """Run a pipeline by name.

    Args:
        pipeline: Pipeline name (e.g., "silver.sales" or "silver/sales")
        full_refresh: Force full refresh instead of incremental

    Returns:
        Execution result dict

    Example:
        run("silver.sales")
        run("gold.daily_kpis", full_refresh=True)
    """
    from ratatouille.pipeline import PipelineExecutor

    ws = workspace()
    executor = PipelineExecutor(ws)
    return executor.run_pipeline(pipeline, full_refresh=full_refresh)


def query(sql: str) -> pd.DataFrame:
    """Execute SQL query (for notebooks/exploration).

    Args:
        sql: SQL query string

    Returns:
        DataFrame with results

    Example:
        df = query("SELECT * FROM bronze.sales LIMIT 10")
        df = query("SHOW TABLES")
    """
    ws = workspace()
    engine = ws.get_engine()
    return engine.query(sql)
