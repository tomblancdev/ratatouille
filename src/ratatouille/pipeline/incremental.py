"""📈 Incremental Processing - Track watermarks and process only new data.

Incremental pipelines only process new/changed data by:
1. Tracking the last processed value (watermark) for a column
2. Injecting WHERE clauses to filter for new data
3. Merging results with existing data using unique keys
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class WatermarkState:
    """State for a single watermark."""

    pipeline_name: str
    column: str
    value: Any
    updated_at: datetime
    row_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "pipeline_name": self.pipeline_name,
            "column": self.column,
            "value": self.value
            if not isinstance(self.value, datetime)
            else self.value.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "row_count": self.row_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> WatermarkState:
        """Create from dictionary."""
        updated_at = data["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            pipeline_name=data["pipeline_name"],
            column=data["column"],
            value=data["value"],
            updated_at=updated_at,
            row_count=data.get("row_count", 0),
        )


class WatermarkTracker:
    """Track watermarks for incremental pipelines.

    Watermarks are stored in a JSON file in the workspace directory.
    For production, this should be stored in the Iceberg catalog.

    Example:
        tracker = WatermarkTracker(workspace_path)

        # Get last watermark
        last_value = tracker.get("silver_sales", "transaction_time")

        # Update after successful run
        tracker.set("silver_sales", "transaction_time", max_timestamp, row_count=1000)
    """

    def __init__(self, storage_path: Path | str):
        """Initialize tracker with storage path.

        Args:
            storage_path: Directory to store watermark state
        """
        self.storage_path = Path(storage_path)
        self._state_file = self.storage_path / ".watermarks.json"
        self._state: dict[str, dict[str, WatermarkState]] = {}
        self._load()

    def _load(self) -> None:
        """Load state from disk."""
        if self._state_file.exists():
            try:
                with open(self._state_file) as f:
                    data = json.load(f)
                    for pipeline_name, columns in data.items():
                        self._state[pipeline_name] = {
                            col: WatermarkState.from_dict(state)
                            for col, state in columns.items()
                        }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"⚠️ Could not load watermarks: {e}")
                self._state = {}

    def _save(self) -> None:
        """Save state to disk."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        data = {
            pipeline: {col: state.to_dict() for col, state in columns.items()}
            for pipeline, columns in self._state.items()
        }
        with open(self._state_file, "w") as f:
            json.dump(data, f, indent=2)

    def get(
        self,
        pipeline_name: str,
        column: str,
        default: Any = None,
    ) -> Any:
        """Get the last watermark value for a pipeline column.

        Args:
            pipeline_name: Name of the pipeline
            column: Watermark column name
            default: Default value if no watermark exists

        Returns:
            Last watermark value or default
        """
        if pipeline_name in self._state:
            if column in self._state[pipeline_name]:
                return self._state[pipeline_name][column].value
        return default

    def get_state(
        self,
        pipeline_name: str,
        column: str,
    ) -> WatermarkState | None:
        """Get the full watermark state for a pipeline column."""
        if pipeline_name in self._state:
            return self._state[pipeline_name].get(column)
        return None

    def set(
        self,
        pipeline_name: str,
        column: str,
        value: Any,
        row_count: int = 0,
    ) -> None:
        """Set the watermark for a pipeline column.

        Args:
            pipeline_name: Name of the pipeline
            column: Watermark column name
            value: New watermark value
            row_count: Number of rows processed
        """
        if pipeline_name not in self._state:
            self._state[pipeline_name] = {}

        self._state[pipeline_name][column] = WatermarkState(
            pipeline_name=pipeline_name,
            column=column,
            value=value,
            updated_at=datetime.utcnow(),
            row_count=row_count,
        )
        self._save()

    def get_all(self, pipeline_name: str) -> dict[str, Any]:
        """Get all watermarks for a pipeline.

        Returns:
            Dict mapping column name to watermark value
        """
        if pipeline_name not in self._state:
            return {}
        return {col: state.value for col, state in self._state[pipeline_name].items()}

    def reset(self, pipeline_name: str, column: str | None = None) -> None:
        """Reset watermarks for a pipeline.

        Args:
            pipeline_name: Name of the pipeline
            column: Specific column to reset (or all if None)
        """
        if pipeline_name in self._state:
            if column:
                self._state[pipeline_name].pop(column, None)
            else:
                del self._state[pipeline_name]
            self._save()

    def list_pipelines(self) -> list[str]:
        """List all pipelines with watermarks."""
        return list(self._state.keys())

    def get_history(self, pipeline_name: str) -> list[dict]:
        """Get watermark history for a pipeline.

        Note: This simple implementation only stores current state.
        For full history, use Iceberg table with time travel.
        """
        if pipeline_name not in self._state:
            return []
        return [state.to_dict() for state in self._state[pipeline_name].values()]


def compute_watermark(
    df: pd.DataFrame,
    column: str,
    agg: str = "max",
) -> Any:
    """Compute watermark value from a DataFrame.

    Args:
        df: DataFrame with processed data
        column: Column to compute watermark for
        agg: Aggregation function (max, min)

    Returns:
        Watermark value
    """
    if df.empty or column not in df.columns:
        return None

    if agg == "max":
        return df[column].max()
    elif agg == "min":
        return df[column].min()
    else:
        raise ValueError(f"Unknown aggregation: {agg}")


def detect_watermark_column(
    parsed_sql: str,
) -> str | None:
    """Detect the watermark column from SQL template.

    Looks for patterns like:
    - WHERE transaction_time > '{{ watermark('transaction_time') }}'
    - AND _ingested_at > '{{ watermark }}'

    Returns:
        Detected column name or None
    """
    import re

    # Match watermark('column') pattern
    match = re.search(r"watermark\(['\"](\w+)['\"]\)", parsed_sql)
    if match:
        return match.group(1)

    # Match common incremental patterns
    patterns = [
        r">\s*'\s*\{\{\s*watermark\s*\}\}'\s*--\s*(\w+)",
        r"(\w+)\s*>\s*'\s*\{\{\s*watermark",
        r"WHERE\s+(\w+)\s*>",
    ]

    for pattern in patterns:
        match = re.search(pattern, parsed_sql, re.IGNORECASE)
        if match:
            return match.group(1)

    return None
