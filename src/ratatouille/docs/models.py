"""📋 Enhanced Pipeline Configuration Models for Documentation.

Extends the base PipelineConfig with additional fields for:
- Owner details (team, email, slack)
- PII marking on columns
- Business rules documentation
- Tags and metadata

Backward compatible with existing config.yaml files.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class OwnerConfig(BaseModel):
    """Pipeline owner configuration.

    Can be a simple string (email) or a full object with team details.
    """

    team: str | None = Field(default=None, description="Owning team name")
    email: str | None = Field(default=None, description="Contact email")
    slack: str | None = Field(default=None, description="Slack channel for alerts")

    @classmethod
    def from_string_or_dict(cls, value: str | dict | None) -> "OwnerConfig | None":
        """Parse owner from string (email) or dict."""
        if value is None:
            return None
        if isinstance(value, str):
            return cls(email=value)
        if isinstance(value, dict):
            return cls(**value)
        return None

    def display_name(self) -> str:
        """Get a display name for the owner."""
        if self.team:
            return self.team
        if self.email:
            return self.email
        return "Unknown"


class BusinessRule(BaseModel):
    """A documented business rule for the pipeline.

    Rules can be defined explicitly in config or extracted from SQL WHERE clauses.
    """

    name: str = Field(description="Rule identifier (e.g., 'positive_quantities')")
    description: str = Field(description="Human-readable explanation")
    sql: str | None = Field(default=None, description="SQL expression implementing the rule")
    source: Literal["config", "sql", "test"] = Field(
        default="config", description="Where this rule was defined"
    )


class DocumentationConfig(BaseModel):
    """Documentation-specific configuration."""

    tags: list[str] = Field(
        default_factory=list,
        description="Categorization tags (e.g., ['sales', 'finance', 'daily'])",
    )
    rules: list[BusinessRule] = Field(
        default_factory=list,
        description="Explicit business rules documentation",
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

    def format_warn(self) -> str:
        """Format warn threshold for display."""
        return self._format_duration(self.warn_after)

    def format_error(self) -> str:
        """Format error threshold for display."""
        return self._format_duration(self.error_after)

    @staticmethod
    def _format_duration(d: dict) -> str:
        """Format duration dict as human-readable string."""
        parts = []
        if d.get("days"):
            parts.append(f"{d['days']} day(s)")
        if d.get("hours"):
            parts.append(f"{d['hours']} hour(s)")
        if d.get("minutes"):
            parts.append(f"{d['minutes']} minute(s)")
        return ", ".join(parts) or "N/A"


class TestConfig(BaseModel):
    """Custom test configuration."""

    name: str = Field(description="Test name")
    sql: str = Field(description="SQL that returns count of failures")
    expect: int = Field(default=0, description="Expected result (0 = no failures)")
    severity: Literal["warn", "error"] = Field(default="error")


class EnhancedColumnConfig(BaseModel):
    """Column schema with PII marking and documentation.

    Extends base ColumnConfig with:
    - pii: bool - Whether column contains PII
    - pii_type: str - Classification (e.g., 'email', 'customer_id', 'ip_address')
    - example: str - Example value for documentation
    """

    name: str = Field(description="Column name")
    type: str = Field(default="string", description="Column type")
    description: str = Field(default="", description="Column description")
    tests: list[str | dict] = Field(
        default_factory=list,
        description="Column tests: ['not_null', 'unique', {'accepted_values': [...]}]",
    )
    # New documentation fields
    pii: bool | None = Field(default=None, description="Whether this column contains PII")
    pii_type: str | None = Field(
        default=None,
        description="PII classification (e.g., 'email', 'customer_id', 'ssn')",
    )
    example: str | None = Field(default=None, description="Example value for documentation")

    def is_pii(self) -> bool:
        """Check if column is marked as PII."""
        return self.pii is True

    def has_pii_marking(self) -> bool:
        """Check if PII status has been explicitly set (true or false)."""
        return self.pii is not None


class EnhancedPipelineConfig(BaseModel):
    """Complete pipeline configuration with documentation enhancements.

    Backward compatible with existing config.yaml files. New fields are optional.

    Example YAML:
        description: |
          Transforms raw POS transactions into cleaned sales records.

        owner:
          team: data-platform
          email: data-team@acme.com
          slack: "#data-alerts"

        columns:
          - name: txn_id
            type: string
            description: Unique transaction identifier
            pii: false
            example: "T00123"
            tests: [not_null, unique]

          - name: customer_id
            type: string
            description: Customer identifier
            pii: true
            pii_type: customer_id

        freshness:
          warn_after: { hours: 6 }
          error_after: { hours: 24 }

        documentation:
          tags: [sales, finance, daily]
          rules:
            - name: positive_quantities
              description: Quantities must be greater than zero
              sql: "quantity > 0"
    """

    description: str = Field(default="", description="Pipeline description")

    # Owner can be string (backward compat) or OwnerConfig
    owner: str | OwnerConfig | None = Field(
        default=None, description="Owner email/team or full config"
    )

    columns: list[EnhancedColumnConfig] = Field(
        default_factory=list, description="Column definitions with PII marking"
    )

    freshness: FreshnessConfig = Field(
        default_factory=FreshnessConfig, description="Freshness SLA"
    )

    tests: list[TestConfig] = Field(
        default_factory=list, description="Custom data tests"
    )

    # Documentation section
    documentation: DocumentationConfig = Field(
        default_factory=DocumentationConfig,
        description="Documentation-specific configuration",
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

    @field_validator("owner", mode="before")
    @classmethod
    def parse_owner(cls, v: Any) -> OwnerConfig | str | None:
        """Parse owner from string or dict."""
        if v is None:
            return None
        if isinstance(v, str):
            return OwnerConfig(email=v)
        if isinstance(v, dict):
            return OwnerConfig(**v)
        return v

    @classmethod
    def from_yaml(cls, path: Path | str) -> "EnhancedPipelineConfig":
        """Load configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)

    @classmethod
    def from_dict(cls, data: dict) -> "EnhancedPipelineConfig":
        """Create from a dictionary."""
        return cls(**data)

    def get_owner_config(self) -> OwnerConfig | None:
        """Get owner as OwnerConfig object."""
        if self.owner is None:
            return None
        if isinstance(self.owner, str):
            return OwnerConfig(email=self.owner)
        return self.owner

    def get_column(self, name: str) -> EnhancedColumnConfig | None:
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

    def get_pii_columns(self) -> list[EnhancedColumnConfig]:
        """Get list of columns marked as PII."""
        return [col for col in self.columns if col.is_pii()]

    def get_tags(self) -> list[str]:
        """Get documentation tags."""
        return self.documentation.tags

    def get_business_rules(self) -> list[BusinessRule]:
        """Get documented business rules."""
        return self.documentation.rules

    def has_complete_pii_marking(self) -> bool:
        """Check if all columns have explicit PII marking."""
        return all(col.has_pii_marking() for col in self.columns)

    def columns_missing_pii_marking(self) -> list[str]:
        """Get list of column names without PII marking."""
        return [col.name for col in self.columns if not col.has_pii_marking()]


def load_enhanced_config(config_path: Path | str) -> EnhancedPipelineConfig:
    """Load enhanced pipeline config from YAML file.

    Args:
        config_path: Path to config.yaml

    Returns:
        EnhancedPipelineConfig from YAML or empty config if not found
    """
    config_path = Path(config_path)

    if config_path.exists():
        return EnhancedPipelineConfig.from_yaml(config_path)

    # Return empty config if not found
    return EnhancedPipelineConfig()
