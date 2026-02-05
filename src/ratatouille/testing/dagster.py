"""Dagster Asset Checks integration for pipeline tests.

Converts quality tests into Dagster asset checks that can block
downstream assets on failure.

Usage:
    from ratatouille.testing.dagster import discover_asset_checks

    checks = discover_asset_checks(workspaces_dir)

    defs = Definitions(
        assets=assets,
        asset_checks=checks,  # <-- Add checks here
    )
"""

from pathlib import Path

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetCheckSpec,
    AssetKey,
    asset_check,
)

from .discovery import discover_pipelines
from .executors.quality import QualityTestExecutor
from .models import TestSeverity


def discover_asset_checks(
    workspaces_dir: str | Path,
) -> list:
    """Discover quality tests and convert to Dagster asset checks.

    Quality tests with severity=error become blocking checks.
    Quality tests with severity=warn become non-blocking checks.

    Args:
        workspaces_dir: Path to workspaces directory

    Returns:
        List of asset check functions
    """
    workspaces_path = Path(workspaces_dir)
    checks = []

    if not workspaces_path.exists():
        return checks

    for workspace_dir in workspaces_path.iterdir():
        if not workspace_dir.is_dir():
            continue

        workspace_name = workspace_dir.name
        workspace_checks = _discover_workspace_checks(workspace_dir, workspace_name)
        checks.extend(workspace_checks)

    return checks


def _discover_workspace_checks(
    workspace_dir: Path,
    workspace_name: str,
) -> list:
    """Discover asset checks for a single workspace."""
    checks = []

    pipelines = discover_pipelines(workspace_dir)

    for pipeline in pipelines:
        # Skip if no quality tests
        if not pipeline.quality_tests:
            continue

        # Create asset check for each quality test
        for test in pipeline.quality_tests:
            check_fn = _create_asset_check(
                workspace_path=workspace_dir,
                workspace_name=workspace_name,
                pipeline=pipeline,
                test=test,
            )
            if check_fn:
                checks.append(check_fn)

    return checks


def _create_asset_check(
    workspace_path: Path,
    workspace_name: str,
    pipeline,
    test,
):
    """Create a Dagster asset check from a quality test.

    Blocking behavior:
    - severity=error → blocking=True (blocks downstream assets)
    - severity=warn → blocking=False (warning only)
    """

    # Build asset key
    asset_key = AssetKey([workspace_name, pipeline.layer, pipeline.name])

    # Map severity to Dagster severity
    is_blocking = test.config.severity == TestSeverity.ERROR
    dagster_severity = (
        AssetCheckSeverity.ERROR
        if test.config.severity == TestSeverity.ERROR
        else AssetCheckSeverity.WARN
    )

    # Create a unique check name
    check_name = test.config.name

    @asset_check(
        asset=asset_key,
        name=check_name,
        description=test.config.description or f"Quality check: {check_name}",
        blocking=is_blocking,
    )
    def quality_check(context) -> AssetCheckResult:
        """Execute quality test as asset check."""
        executor = QualityTestExecutor(
            workspace_path=workspace_path,
            workspace_name=workspace_name,
        )

        # Run the test
        result = executor.execute(pipeline, test)

        # Convert to Dagster result
        passed = result.status.value == "passed"

        metadata = {
            "duration_ms": result.duration_ms,
            "row_count": result.row_count or 0,
            "test_type": result.test_type,
        }

        if result.sql:
            metadata["sql"] = result.sql[:500]  # Truncate for display

        if result.mocks_used:
            metadata["mocks_used"] = result.mocks_used

        if not passed and result.data is not None:
            # Include sample of failing rows
            metadata["sample_failures"] = result.data.head(5).to_dict(orient="records")

        return AssetCheckResult(
            passed=passed,
            severity=dagster_severity,
            metadata=metadata,
            description=result.message,
        )

    return quality_check


def discover_asset_check_specs(
    workspaces_dir: str | Path,
) -> list[AssetCheckSpec]:
    """Discover asset check specs (for lazy loading).

    Use this when you want to define checks without loading all test logic.
    """
    workspaces_path = Path(workspaces_dir)
    specs = []

    if not workspaces_path.exists():
        return specs

    for workspace_dir in workspaces_path.iterdir():
        if not workspace_dir.is_dir():
            continue

        workspace_name = workspace_dir.name
        pipelines = discover_pipelines(workspace_dir)

        for pipeline in pipelines:
            if not pipeline.quality_tests:
                continue

            asset_key = AssetKey([workspace_name, pipeline.layer, pipeline.name])

            for test in pipeline.quality_tests:
                spec = AssetCheckSpec(
                    name=test.config.name,
                    asset=asset_key,
                    description=test.config.description,
                )
                specs.append(spec)

    return specs
