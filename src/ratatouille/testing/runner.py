"""Main test runner that orchestrates test execution."""

import time
from pathlib import Path

from .discovery import discover_pipelines
from .executors.quality import QualityTestExecutor
from .executors.unit_sql import UnitSQLTestExecutor
from .models import (
    DiscoveredPipeline,
    TestSuiteResult,
)
from .reporters.console import ConsoleReporter


class TestRunner:
    """Orchestrate test execution for pipelines.

    Example:
        runner = TestRunner(Path("workspaces/demo"))
        results = runner.run_all()

        # Or filtered
        results = runner.run(
            pipeline="sales",
            layer="silver",
            test_types=["quality"],
        )
    """

    def __init__(
        self,
        workspace_path: Path,
        workspace_name: str | None = None,
        reporter: ConsoleReporter | None = None,
    ) -> None:
        """Initialize the test runner.

        Args:
            workspace_path: Path to workspace root
            workspace_name: Name of the workspace (for S3 paths)
            reporter: Reporter for output (default: ConsoleReporter)
        """
        self.workspace_path = workspace_path
        self.workspace_name = workspace_name or workspace_path.name
        self.reporter = reporter or ConsoleReporter()

        # Initialize executors
        self.quality_executor = QualityTestExecutor(workspace_path, workspace_name)
        self.unit_sql_executor = UnitSQLTestExecutor(workspace_path)

    def run_all(
        self,
        layer: str | None = None,
        test_types: list[str] | None = None,
    ) -> list[TestSuiteResult]:
        """Run all tests in the workspace.

        Args:
            layer: Filter by layer (bronze, silver, gold)
            test_types: Filter by test type (quality, unit)

        Returns:
            List of TestSuiteResult for each pipeline
        """
        self.reporter.report_start(self.workspace_name)

        pipelines = discover_pipelines(self.workspace_path)

        # Filter by layer
        if layer:
            pipelines = [p for p in pipelines if p.layer == layer]

        results = []
        for pipeline in pipelines:
            if pipeline.quality_tests or pipeline.unit_tests:
                suite = self.run_pipeline(pipeline, test_types)
                results.append(suite)

                # Check for fail-fast
                if (
                    not suite.success
                    and hasattr(self.reporter, "fail_fast")
                    and self.reporter.fail_fast
                ):
                    break

        self.reporter.report_summary(results)
        return results

    def run_pipeline(
        self,
        pipeline: DiscoveredPipeline,
        test_types: list[str] | None = None,
    ) -> TestSuiteResult:
        """Run all tests for a single pipeline.

        Args:
            pipeline: The pipeline to test
            test_types: Filter by test type

        Returns:
            TestSuiteResult with all test results
        """
        start_time = time.perf_counter()

        suite = TestSuiteResult(
            pipeline=pipeline.name,
            workspace=self.workspace_name,
            layer=pipeline.layer,
        )

        # Determine which test types to run
        run_quality = test_types is None or "quality" in test_types
        run_unit = test_types is None or "unit" in test_types

        # Run quality tests
        if run_quality:
            for test in pipeline.quality_tests:
                result = self.quality_executor.execute(pipeline, test)
                suite.add_result(result)

                if self.reporter.should_stop(result):
                    break

        # Run unit SQL tests
        if run_unit and not (
            suite.failed > 0
            and hasattr(self.reporter, "fail_fast")
            and self.reporter.fail_fast
        ):
            for test in pipeline.unit_tests:
                if test.test_type == "unit_sql":
                    result = self.unit_sql_executor.execute(pipeline, test)
                    suite.add_result(result)

                    if self.reporter.should_stop(result):
                        break
                # TODO: Add unit_python executor

        suite.duration_ms = int((time.perf_counter() - start_time) * 1000)

        self.reporter.report_pipeline(suite)
        return suite

    def run(
        self,
        pipeline: str | None = None,
        layer: str | None = None,
        test_types: list[str] | None = None,
    ) -> list[TestSuiteResult]:
        """Run tests with filters.

        Args:
            pipeline: Filter by pipeline name
            layer: Filter by layer
            test_types: Filter by test type

        Returns:
            List of TestSuiteResult
        """
        self.reporter.report_start(self.workspace_name)

        all_pipelines = discover_pipelines(self.workspace_path)

        # Apply filters
        if pipeline:
            all_pipelines = [p for p in all_pipelines if p.name == pipeline]
        if layer:
            all_pipelines = [p for p in all_pipelines if p.layer == layer]

        results = []
        for pip in all_pipelines:
            if pip.quality_tests or pip.unit_tests:
                suite = self.run_pipeline(pip, test_types)
                results.append(suite)

        self.reporter.report_summary(results)
        return results
