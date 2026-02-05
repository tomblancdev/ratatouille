"""Pydantic models for test configuration and results."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field


class TestSeverity(str, Enum):
    """Severity level for test failures."""
    WARN = "warn"
    ERROR = "error"


class TestStatus(str, Enum):
    """Status of a test execution."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class MockData(BaseModel):
    """Mock data configuration for unit tests.

    Supports multiple formats:
    - YAML with inline rows
    - CSV files
    - Excel files (with optional sheet name)
    - JSON files
    - Parquet files
    - Python generators
    """
    table: str = Field(..., description="Table name to create, e.g., 'bronze.raw_sales'")

    # Inline data
    rows: list[dict[str, Any]] | None = Field(
        default=None,
        description="Inline row data as list of dicts"
    )

    # File-based data
    file: str | None = Field(
        default=None,
        description="Path to data file (CSV, Excel, JSON, Parquet)"
    )
    sheet: str | None = Field(
        default=None,
        description="Sheet name for Excel files"
    )

    # Generator-based data
    generator: str | None = Field(
        default=None,
        description="Path to Python generator file"
    )
    generator_args: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to generator"
    )


class ExpectedResult(BaseModel):
    """Expected output for unit tests."""

    rows: list[dict[str, Any]] | None = Field(
        default=None,
        description="Expected rows (compared with actual)"
    )
    columns: list[str] | None = Field(
        default=None,
        description="Columns to compare (subset of output)"
    )
    row_count: int | None = Field(
        default=None,
        description="Expected number of rows"
    )
    tolerance: float = Field(
        default=0.01,
        description="Tolerance for numeric comparisons"
    )
    order_by: list[str] | None = Field(
        default=None,
        description="Columns to sort by before comparison"
    )


class TestConfig(BaseModel):
    """Configuration for a single test.

    Parsed from SQL comment metadata:
    -- @name: test_name
    -- @description: Test description
    -- @severity: error
    -- @mocks: mocks/data.yaml
    """
    name: str = Field(..., description="Unique test name")
    description: str = Field(default="", description="Human-readable description")
    severity: TestSeverity = Field(default=TestSeverity.ERROR)

    # For quality tests
    expect_zero_rows: bool = Field(
        default=True,
        description="Test passes if query returns 0 rows"
    )

    # For unit tests
    mocks: list[str] = Field(
        default_factory=list,
        description="Paths to mock data files"
    )
    mode: Literal["full_refresh", "incremental"] = Field(
        default="full_refresh",
        description="Pipeline execution mode"
    )
    watermarks: dict[str, str] = Field(
        default_factory=dict,
        description="Watermark values for incremental mode"
    )
    expect: ExpectedResult | None = Field(
        default=None,
        description="Expected output for unit tests"
    )


@dataclass
class TestOutput:
    """Result of a single test execution.

    Contains all information needed to understand what happened
    and debug failures.
    """
    name: str
    description: str
    test_type: Literal["quality", "unit_sql", "unit_python"]
    status: TestStatus
    severity: TestSeverity = TestSeverity.ERROR

    # Data context - the actual problematic/sample data
    data: pd.DataFrame | None = None
    row_count: int = 0
    columns_checked: list[str] = field(default_factory=list)

    # Execution context
    sql: str | None = None
    mocks_used: list[str] = field(default_factory=list)
    duration_ms: int = 0

    # Human-readable explanation
    message: str | None = None

    # Extra debugging info
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Check if test passed."""
        return self.status == TestStatus.PASSED

    @property
    def failed(self) -> bool:
        """Check if test failed (not error or skipped)."""
        return self.status == TestStatus.FAILED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "test_type": self.test_type,
            "status": self.status.value,
            "severity": self.severity.value,
            "row_count": self.row_count,
            "columns_checked": self.columns_checked,
            "mocks_used": self.mocks_used,
            "duration_ms": self.duration_ms,
            "message": self.message,
            "metadata": self.metadata,
            # Data is converted separately if needed
            "data": self.data.to_dict(orient="records") if self.data is not None else None,
            "sql": self.sql,
        }


@dataclass
class TestSuiteResult:
    """Result of running all tests for a pipeline."""
    pipeline: str
    workspace: str
    layer: str

    total: int = 0
    passed: int = 0
    failed: int = 0
    warned: int = 0
    skipped: int = 0
    errored: int = 0

    duration_ms: int = 0
    results: list[TestOutput] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if all tests passed (no failures or errors)."""
        return self.failed == 0 and self.errored == 0

    def add_result(self, result: TestOutput) -> None:
        """Add a test result and update counters."""
        self.results.append(result)
        self.total += 1

        if result.status == TestStatus.PASSED:
            self.passed += 1
        elif result.status == TestStatus.FAILED:
            if result.severity == TestSeverity.WARN:
                self.warned += 1
            else:
                self.failed += 1
        elif result.status == TestStatus.SKIPPED:
            self.skipped += 1
        elif result.status == TestStatus.ERROR:
            self.errored += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pipeline": self.pipeline,
            "workspace": self.workspace,
            "layer": self.layer,
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "warned": self.warned,
                "skipped": self.skipped,
                "errored": self.errored,
            },
            "duration_ms": self.duration_ms,
            "success": self.success,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class DiscoveredTest:
    """A test file discovered in a pipeline's tests/ folder."""
    path: Path
    test_type: Literal["quality", "unit_sql", "unit_python"]
    config: TestConfig

    # For SQL tests, the raw SQL content
    sql: str | None = None

    # For Python tests, the module path
    module_path: str | None = None


@dataclass
class DiscoveredPipeline:
    """A pipeline discovered in the workspace."""
    name: str
    layer: str
    path: Path

    # Pipeline file
    pipeline_file: Path | None = None  # pipeline.sql or pipeline.py
    config_file: Path | None = None     # config.yaml

    # Test folders
    tests_path: Path | None = None
    mocks_path: Path | None = None
    quality_tests: list[DiscoveredTest] = field(default_factory=list)
    unit_tests: list[DiscoveredTest] = field(default_factory=list)

    # Documentation
    docs_path: Path | None = None
    readme_file: Path | None = None
