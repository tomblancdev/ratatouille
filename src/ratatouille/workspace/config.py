"""🏢 Workspace Configuration - Pydantic models for workspace settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class IsolationConfig(BaseModel):
    """Workspace isolation settings."""

    nessie_branch: str = Field(
        description="Dedicated Nessie branch for this workspace"
    )
    s3_prefix: str = Field(
        description="S3 prefix for all workspace data (e.g., 'acme' -> s3://warehouse/acme/)"
    )


class LayerConfig(BaseModel):
    """Medallion layer configuration."""

    retention_days: int | None = Field(
        default=None,
        description="Data retention in days (null = forever)"
    )
    partition_by: list[str] = Field(
        default_factory=list,
        description="Default partition columns for this layer"
    )


class LayersConfig(BaseModel):
    """All medallion layers configuration."""

    bronze: LayerConfig = Field(default_factory=lambda: LayerConfig(retention_days=90))
    silver: LayerConfig = Field(default_factory=lambda: LayerConfig(retention_days=365))
    gold: LayerConfig = Field(default_factory=lambda: LayerConfig(retention_days=None))


class ProductPublishConfig(BaseModel):
    """Data product publication configuration."""

    name: str = Field(description="Product name")
    source: str = Field(description="Source table (e.g., 'gold.daily_kpis')")
    access: list[dict] = Field(
        default_factory=list,
        description="Access rules: [{'workspace': '*', 'level': 'read'}]"
    )
    sla: dict = Field(
        default_factory=dict,
        description="SLA settings: {'freshness_hours': 24}"
    )


class ProductSubscriptionConfig(BaseModel):
    """Data product subscription configuration."""

    product: str = Field(description="Product name to subscribe to")
    alias: str | None = Field(
        default=None,
        description="Local alias for the product"
    )
    version_constraint: str = Field(
        default="latest",
        description="Version constraint (e.g., '2.x', '^2.0.0', 'latest')"
    )


class ResourceOverrides(BaseModel):
    """Workspace-specific resource overrides."""

    max_memory_mb: int | None = None
    max_parallel_pipelines: int | None = None
    chunk_size_rows: int | None = None


class ResourcesConfig(BaseModel):
    """Workspace resource configuration."""

    profile: Literal["tiny", "small", "medium", "large"] = Field(default="small")
    overrides: ResourceOverrides = Field(default_factory=ResourceOverrides)


class WorkspaceConfig(BaseModel):
    """Complete workspace configuration.

    Loaded from workspace.yaml in the workspace directory.

    Example:
        name: acme
        version: "1.0"
        description: "ACME Corp data workspace"

        isolation:
          nessie_branch: "workspace/acme"
          s3_prefix: "acme"

        resources:
          profile: small
          overrides:
            max_memory_mb: 4096

        layers:
          bronze:
            retention_days: 90
          silver:
            retention_days: 365
          gold:
            retention_days: null

        products:
          - name: sales_kpis
            source: gold.daily_sales_kpis
            access:
              - workspace: "*"
                level: read

        subscriptions:
          - product: inventory/stock_levels
            alias: ext_inventory
    """

    name: str = Field(description="Workspace identifier")
    version: str = Field(default="1.0", description="Workspace config version")
    description: str = Field(default="", description="Workspace description")

    isolation: IsolationConfig = Field(description="Isolation settings")
    resources: ResourcesConfig = Field(default_factory=ResourcesConfig)
    layers: LayersConfig = Field(default_factory=LayersConfig)

    products: list[ProductPublishConfig] = Field(
        default_factory=list,
        description="Data products this workspace publishes"
    )
    subscriptions: list[ProductSubscriptionConfig] = Field(
        default_factory=list,
        description="Data products this workspace subscribes to"
    )

    @classmethod
    def from_yaml(cls, path: Path | str) -> "WorkspaceConfig":
        """Load configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def from_directory(cls, workspace_dir: Path | str) -> "WorkspaceConfig":
        """Load configuration from a workspace directory."""
        workspace_dir = Path(workspace_dir)
        config_path = workspace_dir / "workspace.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"No workspace.yaml found in {workspace_dir}. "
                f"Create one to configure this workspace."
            )

        return cls.from_yaml(config_path)

    def to_yaml(self, path: Path | str) -> None:
        """Save configuration to a YAML file."""
        with open(path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)
