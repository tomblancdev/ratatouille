"""🐀 Ratatouille - Anyone Can Data!

File-First Pipeline Development:
    # Define pipelines as files (SQL/Python + YAML)
    # workspaces/myworkspace/pipelines/silver/sales.sql

    # Run from Python
    from ratatouille import run, workspace

    workspace("myworkspace")
    run("silver.sales")

    # Or use CLI
    # rat run silver.sales -w myworkspace

Exploration (for notebooks):
    from ratatouille import tools, query

    tools.tables()                    # List tables
    tools.schema("silver.sales")      # Get schema
    tools.preview("gold.metrics")     # Preview data

    df = query("SELECT * FROM ...")   # Quick query
"""

__version__ = "2.0.0"

# Tools module for exploration
from ratatouille import tools

# Core SDK functions
from ratatouille.sdk import (
    list_workspaces,
    query,
    run,
    workspace,
)

__all__ = [
    # SDK
    "run",
    "workspace",
    "list_workspaces",
    "query",
    # Exploration
    "tools",
    # Meta
    "__version__",
]
