#!/usr/bin/env python3
"""
🐀 Ratatouille CLI - Anyone Can Data!

Usage:
    rat init <name>        Create a new workspace
    rat run <pipeline>     Run a pipeline
    rat query <sql>        Execute SQL query
    rat test               Run pipeline tests
    rat docs generate      Generate pipeline documentation
    rat docs check         Validate documentation completeness
    rat --help             Show help
"""

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()


def get_workspace_path() -> Path:
    """Get the current workspace path from environment or current directory."""
    ws_path = os.getenv("RATATOUILLE_WORKSPACE_PATH")
    if ws_path:
        return Path(ws_path)

    # Try to find workspace by looking for pipelines/ folder
    cwd = Path.cwd()
    if (cwd / "pipelines").exists():
        return cwd
    if (cwd / "workspace.yaml").exists():
        return cwd

    # Check parent directories
    for parent in cwd.parents:
        if (parent / "pipelines").exists() or (parent / "workspace.yaml").exists():
            return parent

    return cwd


def get_template_dir() -> Path:
    """Get the templates directory."""
    return Path(__file__).parent / "templates"


def init_workspace(name: str, path: Path | None = None) -> None:
    """Initialize a new workspace."""
    from ratatouille.templates import scaffold_workspace

    target = path or Path.cwd() / name

    if target.exists() and any(target.iterdir()):
        console.print(
            f"[red]Error:[/red] Directory '{target}' already exists and is not empty"
        )
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
  from ratatouille import query
  query("SHOW TABLES")
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
    from ratatouille import run

    console.print(f"⚡ Running pipeline [cyan]{pipeline}[/cyan]...")

    try:
        result = run(pipeline, full_refresh=full_refresh)
        console.print(f"[green]✓[/green] Pipeline completed: {result}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def run_query(sql: str) -> None:
    """Execute a SQL query."""
    from ratatouille import query

    try:
        result = query(sql)
        console.print(result)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def generate_docs(
    workspace: str | None = None,
    pipeline: str | None = None,
) -> None:
    """Generate documentation for pipelines.

    Args:
        workspace: Workspace name or path
        pipeline: Specific pipeline (e.g., "silver/sales")
    """
    from ratatouille.docs import DocumentationGenerator

    # Determine workspace path
    workspace_path = _resolve_workspace_path(workspace)

    if not workspace_path.exists():
        console.print(f"[red]Error:[/red] Workspace not found: {workspace_path}")
        sys.exit(1)

    console.print(
        f"📚 Generating documentation for [cyan]{workspace_path.name}[/cyan]..."
    )
    console.print()

    generator = DocumentationGenerator(workspace_path, console)

    if pipeline:
        result = generator.generate_for_pipeline(pipeline)
        results = [result]
    else:
        results = generator.generate_all()

    # Report results
    total_created = sum(len(r.files_created) for r in results)
    total_updated = sum(len(r.files_updated) for r in results)
    errors = [r for r in results if r.errors]

    for result in results:
        if result.errors:
            console.print(f"[red]❌ {result.pipeline}[/red]")
            for error in result.errors:
                console.print(f"   {error}")
        else:
            created = len(result.files_created)
            updated = len(result.files_updated)
            console.print(
                f"[green]✅ {result.pipeline}[/green] ({created} created, {updated} updated)"
            )

    console.print()
    console.print(
        f"[bold]📊 Summary:[/bold] {len(results)} pipelines | {total_created} created | {total_updated} updated"
    )

    if errors:
        console.print(f"[bold red]{len(errors)} pipeline(s) had errors[/bold red]")
        sys.exit(1)
    else:
        console.print(
            "[bold green]Documentation generated successfully! 🎉[/bold green]"
        )


def check_docs(
    workspace: str | None = None,
    strict: bool = False,
    verbose: bool = False,
) -> None:
    """Check documentation completeness.

    Args:
        workspace: Workspace name or path
        strict: Treat warnings as errors
        verbose: Show all pipelines, not just failures
    """
    from ratatouille.docs import CompletenessValidator

    # Determine workspace path
    workspace_path = _resolve_workspace_path(workspace)

    if not workspace_path.exists():
        console.print(f"[red]Error:[/red] Workspace not found: {workspace_path}")
        sys.exit(1)

    validator = CompletenessValidator(workspace_path, console)
    results = validator.validate_all(strict=strict)

    validator.print_results(results, verbose=verbose)

    # Exit with error if any failures
    if strict:
        if not all(r.passed_strict for r in results):
            sys.exit(1)
    else:
        if not all(r.passed for r in results):
            sys.exit(1)


def _resolve_workspace_path(workspace: str | None) -> Path:
    """Resolve workspace name/path to actual path."""
    if workspace:
        workspace_path = Path(workspace)
        if not workspace_path.is_absolute():
            # Try as workspace name in workspaces/
            workspaces_dir = Path.cwd() / "workspaces"
            if (workspaces_dir / workspace).exists():
                workspace_path = workspaces_dir / workspace
            else:
                workspace_path = Path.cwd() / workspace
    else:
        workspace_path = get_workspace_path()

    return workspace_path


def run_tests(
    workspace: str | None = None,
    pipeline: str | None = None,
    layer: str | None = None,
    test_type: list[str] | None = None,
    output: str = "console",
    verbose: bool = False,
    fail_fast: bool = False,
) -> None:
    """Run pipeline tests.

    Args:
        workspace: Workspace name or path
        pipeline: Filter by pipeline name
        layer: Filter by layer (bronze, silver, gold)
        test_type: Filter by test type (quality, unit)
        output: Output format (console, json)
        verbose: Show verbose output
        fail_fast: Stop on first failure
    """
    from ratatouille.testing.reporters.console import ConsoleReporter
    from ratatouille.testing.reporters.json import JSONReporter
    from ratatouille.testing.runner import TestRunner

    # Determine workspace path
    if workspace:
        workspace_path = Path(workspace)
        if not workspace_path.is_absolute():
            # Try as workspace name in workspaces/
            workspaces_dir = Path.cwd() / "workspaces"
            if (workspaces_dir / workspace).exists():
                workspace_path = workspaces_dir / workspace
            else:
                workspace_path = Path.cwd() / workspace
    else:
        workspace_path = get_workspace_path()

    if not workspace_path.exists():
        console.print(f"[red]Error:[/red] Workspace not found: {workspace_path}")
        sys.exit(1)

    workspace_name = workspace_path.name

    # Select reporter
    if output == "json":
        reporter = JSONReporter(pretty=verbose)
    else:
        reporter = ConsoleReporter(verbose=verbose, fail_fast=fail_fast)

    # Create runner and execute
    runner = TestRunner(workspace_path, workspace_name, reporter)

    try:
        if pipeline:
            results = runner.run(pipeline=pipeline, layer=layer, test_types=test_type)
        else:
            results = runner.run_all(layer=layer, test_types=test_type)

        # Exit with error code if any tests failed
        total_failed = sum(r.failed + r.errored for r in results)
        if total_failed > 0:
            sys.exit(1)

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
  rat test                     Run all tests in current workspace
  rat test -w demo             Run tests for demo workspace
  rat test -p sales -t quality Run quality tests for sales pipeline
  rat docs generate -w demo    Generate docs for demo workspace
  rat docs check -w demo       Validate docs completeness
  rat docs check --strict      Treat warnings as errors
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

    # test command
    test_parser = subparsers.add_parser("test", help="Run pipeline tests")
    test_parser.add_argument(
        "--workspace", "-w", help="Workspace name or path (default: current workspace)"
    )
    test_parser.add_argument(
        "--pipeline", "-p", help="Filter by pipeline name (e.g., 'sales')"
    )
    test_parser.add_argument(
        "--layer", "-l", choices=["bronze", "silver", "gold"], help="Filter by layer"
    )
    test_parser.add_argument(
        "--type",
        "-t",
        action="append",
        dest="test_type",
        choices=["quality", "unit"],
        help="Filter by test type (can specify multiple)",
    )
    test_parser.add_argument(
        "--output",
        "-o",
        choices=["console", "json"],
        default="console",
        help="Output format (default: console)",
    )
    test_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output with data samples",
    )
    test_parser.add_argument(
        "--fail-fast", "-x", action="store_true", help="Stop on first failure"
    )

    # docs command group
    docs_parser = subparsers.add_parser(
        "docs", help="Generate and validate documentation"
    )
    docs_subparsers = docs_parser.add_subparsers(
        dest="docs_command", help="Documentation commands"
    )

    # docs generate
    docs_gen_parser = docs_subparsers.add_parser(
        "generate", help="Generate documentation"
    )
    docs_gen_parser.add_argument(
        "--workspace", "-w", help="Workspace name or path (default: current workspace)"
    )
    docs_gen_parser.add_argument(
        "--pipeline", "-p", help="Generate for specific pipeline (e.g., 'silver/sales')"
    )

    # docs check
    docs_check_parser = docs_subparsers.add_parser(
        "check", help="Validate documentation completeness"
    )
    docs_check_parser.add_argument(
        "--workspace", "-w", help="Workspace name or path (default: current workspace)"
    )
    docs_check_parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors"
    )
    docs_check_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all pipelines, not just failures",
    )

    # version
    parser.add_argument("--version", action="version", version="%(prog)s 2.0.0")

    args = parser.parse_args()

    if args.command == "init":
        target = (args.path or Path.cwd()) / args.name
        init_workspace(args.name, target)
    elif args.command == "run":
        run_pipeline(args.pipeline, args.full_refresh)
    elif args.command == "query":
        run_query(args.sql)
    elif args.command == "test":
        run_tests(
            workspace=args.workspace,
            pipeline=args.pipeline,
            layer=args.layer,
            test_type=args.test_type,
            output=args.output,
            verbose=args.verbose,
            fail_fast=args.fail_fast,
        )
    elif args.command == "docs":
        if args.docs_command == "generate":
            generate_docs(
                workspace=args.workspace,
                pipeline=args.pipeline,
            )
        elif args.docs_command == "check":
            check_docs(
                workspace=args.workspace,
                strict=args.strict,
                verbose=args.verbose,
            )
        else:
            docs_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
