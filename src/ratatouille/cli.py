#!/usr/bin/env python3
"""
🐀 Ratatouille CLI - Anyone Can Data!

Usage:
    rat init <name>     Create a new workspace
    rat run <pipeline>  Run a pipeline
    rat query <sql>     Execute SQL query
    rat --help          Show help
"""

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()


def get_template_dir() -> Path:
    """Get the templates directory."""
    return Path(__file__).parent / "templates"


def init_workspace(name: str, path: Path | None = None) -> None:
    """Initialize a new workspace."""
    from ratatouille.templates import scaffold_workspace

    target = path or Path.cwd() / name

    if target.exists() and any(target.iterdir()):
        console.print(f"[red]Error:[/red] Directory '{target}' already exists and is not empty")
        sys.exit(1)

    console.print(f"🐀 Creating workspace [cyan]{name}[/cyan]...")

    try:
        scaffold_workspace(name, target)

        console.print(
            Panel(
                f"""[green]✓[/green] Workspace created at [cyan]{target}[/cyan]

[bold]Next steps:[/bold]
  1. cd {target.name}
  2. Open in VS Code (will prompt for DevContainer)
  3. Start building pipelines!

[bold]Quick start:[/bold]
  [dim]# In the devcontainer[/dim]
  from ratatouille import sdk
  sdk.query("SHOW TABLES")
""",
                title="🐀 Workspace Ready!",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def run_pipeline(pipeline: str, full_refresh: bool = False) -> None:
    """Run a pipeline."""
    from ratatouille import sdk

    console.print(f"⚡ Running pipeline [cyan]{pipeline}[/cyan]...")

    try:
        result = sdk.run(pipeline, full_refresh=full_refresh)
        console.print(f"[green]✓[/green] Pipeline completed: {result}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def run_query(sql: str) -> None:
    """Execute a SQL query."""
    from ratatouille import sdk

    try:
        result = sdk.query(sql)
        console.print(result)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="rat",
        description="🐀 Ratatouille - Anyone Can Data!",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  rat init my-project          Create new workspace in ./my-project
  rat init analytics --path ~  Create workspace at ~/analytics
  rat run silver.events        Run the silver.events pipeline
  rat query "SHOW TABLES"      Execute SQL query
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Create a new workspace")
    init_parser.add_argument("name", help="Workspace name")
    init_parser.add_argument(
        "--path", "-p", type=Path, help="Parent directory (default: current directory)"
    )

    # run command
    run_parser = subparsers.add_parser("run", help="Run a pipeline")
    run_parser.add_argument("pipeline", help="Pipeline name (e.g., silver.events)")
    run_parser.add_argument(
        "--full-refresh", "-f", action="store_true", help="Full refresh (rebuild all)"
    )

    # query command
    query_parser = subparsers.add_parser("query", help="Execute SQL query")
    query_parser.add_argument("sql", help="SQL query to execute")

    # version
    parser.add_argument("--version", "-v", action="version", version="%(prog)s 2.0.0")

    args = parser.parse_args()

    if args.command == "init":
        target = (args.path or Path.cwd()) / args.name
        init_workspace(args.name, target)
    elif args.command == "run":
        run_pipeline(args.pipeline, args.full_refresh)
    elif args.command == "query":
        run_query(args.sql)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
