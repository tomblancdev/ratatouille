"""Rich console reporter for test results."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..models import TestOutput, TestSuiteResult, TestStatus, TestSeverity


class ConsoleReporter:
    """Format and display test results in the console.

    Uses Rich for colorful, formatted output with data tables.
    """

    def __init__(
        self,
        console: Console | None = None,
        verbose: bool = False,
        fail_fast: bool = False,
    ) -> None:
        self.console = console or Console()
        self.verbose = verbose
        self.fail_fast = fail_fast

    def report_start(self, workspace: str) -> None:
        """Report the start of test execution."""
        self.console.print()
        self.console.print(f"[bold cyan]🐀 Running tests for workspace: {workspace}[/bold cyan]")
        self.console.print("[dim]" + "━" * 50 + "[/dim]")
        self.console.print()

    def report_pipeline(self, suite: TestSuiteResult) -> None:
        """Report results for a single pipeline."""
        self.console.print(f"[bold]📦 {suite.layer}/{suite.pipeline}[/bold]")

        for result in suite.results:
            self._report_single_test(result)

        self.console.print()

    def _report_single_test(self, result: TestOutput) -> None:
        """Report a single test result."""
        # Status icon and color
        if result.status == TestStatus.PASSED:
            icon = "✅"
            color = "green"
        elif result.status == TestStatus.FAILED:
            if result.severity == TestSeverity.WARN:
                icon = "⚠️"
                color = "yellow"
            else:
                icon = "❌"
                color = "red"
        elif result.status == TestStatus.SKIPPED:
            icon = "⏭️"
            color = "dim"
        else:  # ERROR
            icon = "💥"
            color = "red"

        # Format test line
        test_type = f"[{result.test_type}]"
        duration = f"{result.duration_ms}ms"

        self.console.print(
            f"  {icon} [bold]{result.name:<35}[/bold] "
            f"[dim]{test_type:<12}[/dim] "
            f"[dim]{duration:>6}[/dim]"
        )

        # Show message for failures
        if result.status in (TestStatus.FAILED, TestStatus.ERROR):
            self.console.print(f"     [dim]→[/dim] [{color}]{result.message}[/{color}]")

            # Show data table if available
            if result.data is not None and len(result.data) > 0:
                self._print_data_table(result.data)

        # Show details in verbose mode
        elif self.verbose and result.message:
            self.console.print(f"     [dim]→ {result.message}[/dim]")

    def _print_data_table(self, df: "pd.DataFrame", max_rows: int = 5) -> None:
        """Print a DataFrame as a Rich table."""
        import pandas as pd

        table = Table(show_header=True, header_style="bold", padding=(0, 1))

        # Add columns
        for col in df.columns:
            table.add_column(str(col))

        # Add rows (limit to max_rows)
        for _, row in df.head(max_rows).iterrows():
            table.add_row(*[str(v) for v in row.values])

        if len(df) > max_rows:
            table.add_row(*["..." for _ in df.columns])

        self.console.print("     ", table)

    def report_summary(self, suites: list[TestSuiteResult]) -> None:
        """Report final summary."""
        total = sum(s.total for s in suites)
        passed = sum(s.passed for s in suites)
        failed = sum(s.failed for s in suites)
        warned = sum(s.warned for s in suites)
        errored = sum(s.errored for s in suites)
        skipped = sum(s.skipped for s in suites)
        duration = sum(s.duration_ms for s in suites)

        self.console.print("[dim]" + "━" * 50 + "[/dim]")
        self.console.print()

        # Summary line
        parts = [f"[bold]{total}[/bold] tests"]
        if passed:
            parts.append(f"[green]{passed} passed ✅[/green]")
        if failed:
            parts.append(f"[red]{failed} failed ❌[/red]")
        if warned:
            parts.append(f"[yellow]{warned} warned ⚠️[/yellow]")
        if errored:
            parts.append(f"[red]{errored} errored 💥[/red]")
        if skipped:
            parts.append(f"[dim]{skipped} skipped ⏭️[/dim]")

        self.console.print(f"[bold]📊 Summary:[/bold] {' | '.join(parts)} | [dim]{duration}ms[/dim]")
        self.console.print()

        # Final status
        if failed == 0 and errored == 0:
            self.console.print("[bold green]All tests passed! 🎉[/bold green]")
        else:
            self.console.print(f"[bold red]{failed + errored} test(s) failed[/bold red]")

        self.console.print()

    def report_error(self, message: str) -> None:
        """Report an error."""
        self.console.print(f"[bold red]Error:[/bold red] {message}")

    def should_stop(self, result: TestOutput) -> bool:
        """Check if we should stop execution (fail-fast mode)."""
        return self.fail_fast and result.status in (TestStatus.FAILED, TestStatus.ERROR)
