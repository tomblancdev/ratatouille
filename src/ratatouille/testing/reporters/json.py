"""JSON reporter for test results.

Outputs structured JSON for CI/CD integration.
"""

import json
import sys
from datetime import datetime
from typing import TextIO

from ..models import TestSuiteResult


class JSONReporter:
    """Output test results as JSON for CI/CD pipelines."""

    def __init__(
        self,
        output: TextIO | None = None,
        pretty: bool = False,
    ) -> None:
        """Initialize the JSON reporter.

        Args:
            output: File to write to (default: stdout)
            pretty: Pretty-print JSON with indentation
        """
        self.output = output or sys.stdout
        self.pretty = pretty
        self._suites: list[TestSuiteResult] = []

    def report_start(self, workspace: str) -> None:
        """Record workspace for final output."""
        self._workspace = workspace
        self._start_time = datetime.utcnow()

    def report_pipeline(self, suite: TestSuiteResult) -> None:
        """Collect suite results for final output."""
        self._suites.append(suite)

    def report_summary(self, suites: list[TestSuiteResult]) -> None:
        """Output final JSON report."""
        total = sum(s.total for s in suites)
        passed = sum(s.passed for s in suites)
        failed = sum(s.failed for s in suites)
        warned = sum(s.warned for s in suites)
        errored = sum(s.errored for s in suites)
        skipped = sum(s.skipped for s in suites)
        duration = sum(s.duration_ms for s in suites)

        report = {
            "workspace": getattr(self, "_workspace", "unknown"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "warned": warned,
                "errored": errored,
                "skipped": skipped,
                "success": failed == 0 and errored == 0,
            },
            "duration_ms": duration,
            "pipelines": [s.to_dict() for s in suites],
        }

        indent = 2 if self.pretty else None
        json.dump(report, self.output, indent=indent, default=str)
        self.output.write("\n")

    def report_error(self, message: str) -> None:
        """Output error as JSON."""
        error = {
            "error": True,
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        json.dump(error, self.output, default=str)
        self.output.write("\n")

    def should_stop(self, result: "TestOutput") -> bool:
        """JSON reporter never stops early."""
        return False
