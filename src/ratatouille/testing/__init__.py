"""Ratatouille Testing Framework.

Comprehensive testing for data pipelines with:
- Quality tests (data validation against real data)
- Unit tests (transformation testing with mocks)
- Multiple mock formats (YAML, CSV, Excel, JSON, Parquet)
- API emulation for ingestion testing
"""

from .context import TestContext
from .models import (
    ExpectedResult,
    MockData,
    TestConfig,
    TestOutput,
    TestSeverity,
    TestStatus,
)
from .runner import TestRunner

__all__ = [
    "TestConfig",
    "TestOutput",
    "TestSeverity",
    "TestStatus",
    "MockData",
    "ExpectedResult",
    "TestContext",
    "TestRunner",
]
