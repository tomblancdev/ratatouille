"""✅ Documentation Validator - Check documentation completeness.

Validates that pipeline documentation meets quality standards:
- README exists
- Description is meaningful
- Owner is defined
- PII marking complete
- Column descriptions exist
- Freshness SLA defined

Usage:
    validator = CompletenessValidator(workspace_path)
    results = validator.validate_all()
    # or
    validator.validate_all(strict=True)  # Warnings become errors
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from rich.console import Console

from .models import EnhancedPipelineConfig, load_enhanced_config


class Severity(Enum):
    """Validation rule severity."""

    ERROR = "error"
    WARN = "warn"

    def __str__(self) -> str:
        return self.value


@dataclass
class ValidationIssue:
    """A single validation issue."""

    rule: str
    message: str
    severity: Severity
    pipeline: str
    file: str | None = None


@dataclass
class ValidationResult:
    """Result of validating a single pipeline."""

    pipeline: str
    layer: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARN]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    @property
    def passed_strict(self) -> bool:
        return len(self.issues) == 0


@dataclass
class ValidationRule:
    """A validation rule definition."""

    name: str
    description: str
    severity: Severity
    check: Callable[[EnhancedPipelineConfig, Path], str | None]


class CompletenessValidator:
    """Validate documentation completeness for pipelines.

    Rules are checked in order of severity (errors first).
    """

    def __init__(
        self,
        workspace_path: Path | str,
        console: Console | None = None,
    ) -> None:
        """Initialize the validator.

        Args:
            workspace_path: Path to workspace root
            console: Rich console for output
        """
        self.workspace_path = Path(workspace_path)
        self.console = console or Console()
        self._rules = self._build_rules()

    def _build_rules(self) -> list[ValidationRule]:
        """Build the list of validation rules."""
        return [
            # ERROR rules
            ValidationRule(
                name="readme_exists",
                description="README.md must exist",
                severity=Severity.ERROR,
                check=self._check_readme_exists,
            ),
            ValidationRule(
                name="description_length",
                description="Description must be at least 50 characters",
                severity=Severity.ERROR,
                check=self._check_description_length,
            ),
            ValidationRule(
                name="owner_defined",
                description="Owner must be defined",
                severity=Severity.ERROR,
                check=self._check_owner_defined,
            ),
            ValidationRule(
                name="pii_marked",
                description="All columns must have pii: true/false",
                severity=Severity.ERROR,
                check=self._check_pii_marked,
            ),
            # WARN rules
            ValidationRule(
                name="data_dictionary_exists",
                description="docs/data_dictionary.md should exist",
                severity=Severity.WARN,
                check=self._check_data_dictionary_exists,
            ),
            ValidationRule(
                name="column_descriptions",
                description="All columns should have descriptions",
                severity=Severity.WARN,
                check=self._check_column_descriptions,
            ),
            ValidationRule(
                name="freshness_defined",
                description="Freshness SLA should be configured",
                severity=Severity.WARN,
                check=self._check_freshness_defined,
            ),
            ValidationRule(
                name="lineage_exists",
                description="docs/lineage.md should exist",
                severity=Severity.WARN,
                check=self._check_lineage_exists,
            ),
        ]

    def validate_all(self, strict: bool = False) -> list[ValidationResult]:
        """Validate all pipelines in the workspace.

        Args:
            strict: If True, warnings are treated as errors

        Returns:
            List of ValidationResult for each pipeline
        """
        results = []

        for pipeline_path in self._discover_pipelines():
            result = self._validate_pipeline(pipeline_path)

            # In strict mode, promote warnings to errors
            if strict:
                for issue in result.issues:
                    if issue.severity == Severity.WARN:
                        issue.severity = Severity.ERROR

            results.append(result)

        return results

    def validate_pipeline(
        self, pipeline: str, strict: bool = False
    ) -> ValidationResult:
        """Validate a specific pipeline.

        Args:
            pipeline: Pipeline path relative to pipelines/ (e.g., "silver/sales")
            strict: If True, warnings are treated as errors

        Returns:
            ValidationResult
        """
        pipeline_path = self.workspace_path / "pipelines" / pipeline
        if not pipeline_path.exists():
            # Try as file-based pipeline
            parts = pipeline.split("/")
            if len(parts) == 2:
                pipeline_path = self.workspace_path / "pipelines" / parts[0] / parts[1]

        result = self._validate_pipeline(pipeline_path)

        if strict:
            for issue in result.issues:
                if issue.severity == Severity.WARN:
                    issue.severity = Severity.ERROR

        return result

    def _discover_pipelines(self) -> Generator[Path, None, None]:
        """Discover all pipeline directories in the workspace."""
        pipelines_dir = self.workspace_path / "pipelines"
        if not pipelines_dir.exists():
            return

        # Folder-based pipelines
        for config_file in pipelines_dir.rglob("config.yaml"):
            if "tests" not in config_file.parts:
                yield config_file.parent

        # File-based pipelines (check for .yaml files without folder)
        for layer_dir in pipelines_dir.iterdir():
            if not layer_dir.is_dir():
                continue
            for yaml_file in layer_dir.glob("*.yaml"):
                folder = layer_dir / yaml_file.stem
                if not folder.exists():
                    yield yaml_file.parent / yaml_file.stem

    def _validate_pipeline(self, pipeline_path: Path) -> ValidationResult:
        """Validate a single pipeline."""
        # Determine layer and name
        try:
            parts = pipeline_path.relative_to(self.workspace_path / "pipelines").parts
            layer = parts[0] if parts else "unknown"
            name = parts[1] if len(parts) > 1 else pipeline_path.name
        except ValueError:
            layer = "unknown"
            name = pipeline_path.name

        result = ValidationResult(pipeline=f"{layer}/{name}", layer=layer)

        # Load config
        config = self._load_config(pipeline_path)

        # Run all rules
        for rule in self._rules:
            error_message = rule.check(config, pipeline_path)
            if error_message:
                result.issues.append(
                    ValidationIssue(
                        rule=rule.name,
                        message=error_message,
                        severity=rule.severity,
                        pipeline=f"{layer}/{name}",
                    )
                )

        return result

    def _load_config(self, pipeline_path: Path) -> EnhancedPipelineConfig:
        """Load configuration for a pipeline."""
        if pipeline_path.is_dir():
            config_path = pipeline_path / "config.yaml"
        else:
            config_path = pipeline_path.with_suffix(".yaml")

        if config_path.exists():
            return load_enhanced_config(config_path)
        return EnhancedPipelineConfig()

    # Validation checks

    def _check_readme_exists(
        self, config: EnhancedPipelineConfig, path: Path
    ) -> str | None:
        """Check that README.md exists."""
        if path.is_dir():
            readme = path / "README.md"
        else:
            readme = path.parent / path.name / "README.md"

        if not readme.exists():
            return "README.md not found"
        return None

    def _check_description_length(
        self, config: EnhancedPipelineConfig, path: Path
    ) -> str | None:
        """Check that description is meaningful."""
        if not config.description:
            return "No description provided"
        if len(config.description.strip()) < 50:
            return f"Description too short ({len(config.description.strip())} chars, need 50+)"
        return None

    def _check_owner_defined(
        self, config: EnhancedPipelineConfig, path: Path
    ) -> str | None:
        """Check that owner is defined."""
        owner = config.get_owner_config()
        if not owner:
            return "No owner defined"
        if not owner.email and not owner.team:
            return "Owner has no email or team"
        return None

    def _check_pii_marked(
        self, config: EnhancedPipelineConfig, path: Path
    ) -> str | None:
        """Check that all columns have PII marking."""
        if not config.columns:
            return None  # No columns is fine (maybe no schema defined yet)

        unmarked = config.columns_missing_pii_marking()
        if unmarked:
            if len(unmarked) <= 3:
                return f"Columns missing pii marking: {', '.join(unmarked)}"
            return f"{len(unmarked)} columns missing pii marking"
        return None

    def _check_data_dictionary_exists(
        self, config: EnhancedPipelineConfig, path: Path
    ) -> str | None:
        """Check that data dictionary exists."""
        if path.is_dir():
            docs_dir = path / "docs"
        else:
            docs_dir = path.parent / path.name / "docs"

        dict_path = docs_dir / "data_dictionary.md"
        if not dict_path.exists():
            return "docs/data_dictionary.md not found"
        return None

    def _check_column_descriptions(
        self, config: EnhancedPipelineConfig, path: Path
    ) -> str | None:
        """Check that all columns have descriptions."""
        if not config.columns:
            return None

        missing = [col.name for col in config.columns if not col.description]
        if missing:
            if len(missing) <= 3:
                return f"Columns missing descriptions: {', '.join(missing)}"
            return f"{len(missing)} columns missing descriptions"
        return None

    def _check_freshness_defined(
        self, config: EnhancedPipelineConfig, path: Path
    ) -> str | None:
        """Check that freshness SLA is configured."""
        # Check if using default values
        if config.freshness.warn_after == {
            "hours": 24
        } and config.freshness.error_after == {"hours": 48}:
            return "Using default freshness SLA (consider setting explicit values)"
        return None

    def _check_lineage_exists(
        self, config: EnhancedPipelineConfig, path: Path
    ) -> str | None:
        """Check that lineage doc exists."""
        if path.is_dir():
            docs_dir = path / "docs"
        else:
            docs_dir = path.parent / path.name / "docs"

        lineage_path = docs_dir / "lineage.md"
        if not lineage_path.exists():
            return "docs/lineage.md not found"
        return None

    # Reporting

    def print_results(
        self,
        results: list[ValidationResult],
        verbose: bool = False,
    ) -> None:
        """Print validation results to console.

        Args:
            results: List of validation results
            verbose: Show all rules, not just failures
        """
        total_errors = sum(len(r.errors) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)

        self.console.print()
        self.console.print("[bold cyan]🐀 Documentation Validation Results[/bold cyan]")
        self.console.print("[dim]" + "━" * 50 + "[/dim]")
        self.console.print()

        for result in results:
            self._print_pipeline_result(result, verbose)

        # Summary
        self.console.print("[dim]" + "━" * 50 + "[/dim]")
        self.console.print()

        if total_errors == 0 and total_warnings == 0:
            self.console.print(
                "[bold green]✅ All pipelines pass validation![/bold green]"
            )
        else:
            parts = [f"[bold]{len(results)}[/bold] pipelines"]
            if total_errors:
                parts.append(f"[red]{total_errors} errors ❌[/red]")
            if total_warnings:
                parts.append(f"[yellow]{total_warnings} warnings ⚠️[/yellow]")
            self.console.print(f"[bold]📊 Summary:[/bold] {' | '.join(parts)}")

            if total_errors > 0:
                self.console.print()
                self.console.print(
                    "[bold red]Validation failed. Fix errors before proceeding.[/bold red]"
                )

        self.console.print()

    def _print_pipeline_result(
        self,
        result: ValidationResult,
        verbose: bool,
    ) -> None:
        """Print result for a single pipeline."""
        if result.passed and not result.warnings and not verbose:
            return  # Skip fully passing pipelines in non-verbose mode

        # Header
        if result.passed and not result.warnings:
            icon = "✅"
        elif result.passed:
            icon = "⚠️"
        else:
            icon = "❌"

        self.console.print(f"[bold]{icon} {result.pipeline}[/bold]")

        # Issues
        for issue in result.issues:
            if issue.severity == Severity.ERROR:
                self.console.print(f"  [red]❌ {issue.rule}:[/red] {issue.message}")
            else:
                self.console.print(
                    f"  [yellow]⚠️ {issue.rule}:[/yellow] {issue.message}"
                )

        if result.passed and not result.warnings:
            self.console.print("  [green]All checks passed[/green]")

        self.console.print()


def validate_workspace(
    workspace_path: Path | str,
    strict: bool = False,
) -> tuple[bool, list[ValidationResult]]:
    """Convenience function to validate a workspace.

    Args:
        workspace_path: Path to workspace root
        strict: If True, warnings are treated as errors

    Returns:
        Tuple of (passed, results)
    """
    validator = CompletenessValidator(workspace_path)
    results = validator.validate_all(strict=strict)

    if strict:
        passed = all(r.passed_strict for r in results)
    else:
        passed = all(r.passed for r in results)

    return passed, results
