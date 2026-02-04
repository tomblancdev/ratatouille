"""📋 Pipeline Configuration - Pydantic models for pipeline YAML files.

Pipeline configs define:
- Schema (columns, types)
- Tests (not_null, unique, positive, etc.)
- Freshness SLAs
- Ownership
"""

from __future__ import annotations

from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class ColumnType(str, Enum):
    """Supported column types."""

    STRING = "string"
    INT = "int"
    BIGINT = "bigint"
    FLOAT = "float"
    DOUBLE = "double"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"


class TestConfig(BaseModel):
    """Custom test configuration."""

    name: str = Field(description="Test name")
    sql: str = Field(description="SQL that returns count of failures")
    expect: int = Field(default=0, description="Expected result (0 = no failures)")
    severity: Literal["warn", "error"] = Field(default="error")


class ColumnConfig(BaseModel):
    """Column schema and tests."""

    name: str = Field(description="Column name")
    type: str = Field(default="string", description="Column type")
    description: str = Field(default="", description="Column description")
    tests: list[str | dict] = Field(
        default_factory=list,
        description="Column tests: ['not_null', 'unique', {'accepted_values': [...]}]",
    )


class FreshnessConfig(BaseModel):
    """Data freshness SLA configuration."""

    warn_after: dict = Field(
        default_factory=lambda: {"hours": 24},
        description="Warn if data is older than this",
    )
    error_after: dict = Field(
        default_factory=lambda: {"hours": 48},
        description="Error if data is older than this",
    )

    def get_warn_timedelta(self) -> timedelta:
        """Get warn threshold as timedelta."""
        return timedelta(**self.warn_after)

    def get_error_timedelta(self) -> timedelta:
        """Get error threshold as timedelta."""
        return timedelta(**self.error_after)


class PipelineConfig(BaseModel):
    """Complete pipeline configuration from YAML.

    Example YAML:
        description: "Cleaned sales transactions"
        owner: data-team@acme.com

        columns:
          - name: txn_id
            type: string
            tests: [not_null, unique]
          - name: total
            type: decimal(10,2)
            tests: [not_null, positive]

        freshness:
          warn_after: {hours: 6}
          error_after: {hours: 24}

        tests:
          - name: totals_match
            sql: |
              SELECT COUNT(*) FROM {{ this }}
              WHERE ABS(total - quantity * price) > 0.01
            expect: 0
    """

    description: str = Field(default="", description="Pipeline description")
    owner: str | None = Field(default=None, description="Owner email or team")

    columns: list[ColumnConfig] = Field(
        default_factory=list, description="Column definitions and tests"
    )

    freshness: FreshnessConfig = Field(
        default_factory=FreshnessConfig, description="Freshness SLA"
    )

    tests: list[TestConfig] = Field(
        default_factory=list, description="Custom data tests"
    )

    # Materialization settings (can override SQL header)
    materialized: str | None = Field(
        default=None,
        description="Materialization strategy: table, view, incremental",
    )
    unique_key: list[str] = Field(
        default_factory=list, description="Unique key columns for incremental"
    )
    partition_by: list[str] = Field(
        default_factory=list, description="Partition columns"
    )

    @classmethod
    def from_yaml(cls, path: Path | str) -> "PipelineConfig":
        """Load configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineConfig":
        """Create from a dictionary."""
        return cls(**data)

    def get_column(self, name: str) -> ColumnConfig | None:
        """Get a column config by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def get_required_columns(self) -> list[str]:
        """Get list of columns with not_null test."""
        required = []
        for col in self.columns:
            if "not_null" in col.tests:
                required.append(col.name)
        return required

    def get_unique_columns(self) -> list[str]:
        """Get list of columns with unique test."""
        unique = []
        for col in self.columns:
            if "unique" in col.tests:
                unique.append(col.name)
        return unique


def load_pipeline_config(sql_path: Path | str) -> PipelineConfig:
    """Load pipeline config from YAML file matching SQL file.

    Args:
        sql_path: Path to the SQL file (e.g., "sales.sql")

    Returns:
        PipelineConfig from matching YAML (e.g., "sales.yaml")
        or empty config if no YAML exists
    """
    sql_path = Path(sql_path)
    yaml_path = sql_path.with_suffix(".yaml")

    if yaml_path.exists():
        return PipelineConfig.from_yaml(yaml_path)

    # Also check .yml extension
    yml_path = sql_path.with_suffix(".yml")
    if yml_path.exists():
        return PipelineConfig.from_yaml(yml_path)

    # Return empty config if no YAML found
    return PipelineConfig()
