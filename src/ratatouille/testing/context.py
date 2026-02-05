"""Test context for Python unit tests.

Provides a clean interface for running pipeline code with mock data.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .models import TestOutput, TestStatus, TestSeverity


@dataclass
class TestContext:
    """Context for executing Python unit tests.

    Provides:
    - Mock data loading
    - Pipeline execution
    - Result building

    Example:
        def test_api_ingestion(context: TestContext):
            result = context.run_pipeline()
            assert len(result) == 2
            return context.result(passed=True, data=result)
    """

    pipeline_name: str
    pipeline_path: Path
    mocks_path: Path | None = None

    # Loaded mock data
    _mock_data: dict[str, pd.DataFrame] = field(default_factory=dict)

    # Mock API responses
    _api_responses: dict[str, Any] = field(default_factory=dict)

    # Execution stats
    _api_calls: list[dict[str, Any]] = field(default_factory=list)

    def load_mock(self, table: str, data: pd.DataFrame) -> None:
        """Load mock data for a table.

        Args:
            table: Table name (e.g., 'bronze.raw_sales')
            data: DataFrame with mock data
        """
        self._mock_data[table] = data

    def get_mock(self, table: str) -> pd.DataFrame | None:
        """Get mock data for a table."""
        return self._mock_data.get(table)

    def mock_api_response(self, endpoint: str, response: Any) -> None:
        """Set a mock API response.

        Args:
            endpoint: API endpoint (e.g., 'GET /sales')
            response: Response data (dict, list, or exception)
        """
        self._api_responses[endpoint] = response

    def call_api(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """Make a mock API call.

        Records the call and returns the mock response if configured.
        """
        key = f"{method.upper()} {endpoint}"
        self._api_calls.append({
            "method": method,
            "endpoint": endpoint,
            "kwargs": kwargs,
        })

        if key in self._api_responses:
            response = self._api_responses[key]
            if isinstance(response, Exception):
                raise response
            return response

        raise ValueError(f"No mock response configured for: {key}")

    def run_pipeline(self, **kwargs: Any) -> pd.DataFrame:
        """Execute the pipeline and return results.

        This is a placeholder - actual implementation depends on
        the pipeline type (Python ingestion vs SQL transformation).
        """
        # For Python pipelines, we would import and run the module
        # For now, return empty DataFrame
        return pd.DataFrame()

    def mock_stats(self) -> dict[str, Any]:
        """Get statistics about mock API calls."""
        return {
            "total_calls": len(self._api_calls),
            "calls": self._api_calls,
        }

    def result(
        self,
        passed: bool,
        data: pd.DataFrame | None = None,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TestOutput:
        """Build a test result.

        Args:
            passed: Whether the test passed
            data: Data to show (failing rows or sample)
            message: Human-readable message
            metadata: Additional metadata

        Returns:
            TestOutput ready for reporting
        """
        return TestOutput(
            name="",  # Will be filled by executor
            description="",
            test_type="unit_python",
            status=TestStatus.PASSED if passed else TestStatus.FAILED,
            severity=TestSeverity.ERROR,
            data=data,
            row_count=len(data) if data is not None else 0,
            message=message,
            metadata=metadata or {},
        )


def use_mock(mock_path: str) -> Callable[[Callable], Callable]:
    """Decorator to specify mock data for a test.

    Example:
        @use_mock("mocks/api_emulator.py")
        def test_api_ingestion(context: TestContext):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._mock_path = mock_path  # type: ignore
        return func
    return decorator
