"""Base class for test executors."""

import time
from abc import ABC, abstractmethod
from pathlib import Path

from ..models import DiscoveredPipeline, DiscoveredTest, TestOutput


class BaseTestExecutor(ABC):
    """Abstract base class for test executors.

    Subclasses implement specific test types:
    - QualityTestExecutor: Run quality/*.sql against real data
    - UnitSQLTestExecutor: Run unit/*.sql with mock data
    - UnitPythonTestExecutor: Run unit/*.py with TestContext
    """

    def __init__(self, workspace_path: Path) -> None:
        """Initialize the executor.

        Args:
            workspace_path: Path to the workspace root
        """
        self.workspace_path = workspace_path

    @abstractmethod
    def execute(
        self,
        pipeline: DiscoveredPipeline,
        test: DiscoveredTest,
    ) -> TestOutput:
        """Execute a single test and return the result.

        Args:
            pipeline: The pipeline being tested
            test: The test to execute

        Returns:
            TestOutput with status, data, and metadata
        """
        pass

    def execute_all(
        self,
        pipeline: DiscoveredPipeline,
        tests: list[DiscoveredTest],
    ) -> list[TestOutput]:
        """Execute multiple tests for a pipeline.

        Args:
            pipeline: The pipeline being tested
            tests: List of tests to execute

        Returns:
            List of TestOutput results
        """
        results = []
        for test in tests:
            result = self.execute(pipeline, test)
            results.append(result)
        return results

    def _time_execution(self) -> "ExecutionTimer":
        """Create a timer for measuring execution time."""
        return ExecutionTimer()


class ExecutionTimer:
    """Context manager for timing test execution."""

    def __init__(self) -> None:
        self.start_time: float = 0
        self.end_time: float = 0
        self._duration_ms: int = 0

    def __enter__(self) -> "ExecutionTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        self.end_time = time.perf_counter()
        self._duration_ms = max(0, int((self.end_time - self.start_time) * 1000))

    @property
    def duration_ms(self) -> int:
        """Get duration in milliseconds."""
        if self._duration_ms > 0:
            return self._duration_ms
        if self.end_time > 0:
            return max(0, int((self.end_time - self.start_time) * 1000))
        return max(0, int((time.perf_counter() - self.start_time) * 1000))
