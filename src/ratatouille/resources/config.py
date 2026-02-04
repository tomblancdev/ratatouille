"""⚙️ Resource Configuration - Pydantic models for resource limits."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class DuckDBConfig(BaseModel):
    """DuckDB-specific configuration."""

    threads: int = Field(default=2, ge=1, le=64)
    memory_limit: str = Field(default="8GB")
    temp_directory: str = Field(default="/tmp/duckdb")
    preserve_insertion_order: bool = Field(default=True)


class ContainerLimits(BaseModel):
    """Docker container memory limits."""

    minio_memory: str = Field(default="1G")
    nessie_memory: str = Field(default="768M")
    dagster_memory: str = Field(default="2G")
    jupyter_memory: str = Field(default="2G")


class ResourceConfig(BaseModel):
    """Resource configuration for a Ratatouille instance.

    Controls memory usage, parallelism, and processing behavior.
    Can be loaded from a profile YAML or set programmatically.
    """

    # Memory limits
    max_memory_mb: int = Field(
        default=4096,
        ge=256,
        description="Maximum memory per pipeline operation in MB",
    )
    duckdb_memory_mb: int = Field(
        default=8192,
        ge=512,
        description="Total DuckDB memory limit in MB",
    )

    # Processing
    chunk_size_rows: int = Field(
        default=50000,
        ge=1000,
        description="Number of rows to process per chunk for large tables",
    )
    max_parallel_pipelines: int = Field(
        default=2,
        ge=1,
        le=32,
        description="Maximum concurrent pipeline executions",
    )

    # DuckDB settings
    duckdb: DuckDBConfig = Field(default_factory=DuckDBConfig)

    # Container limits
    containers: ContainerLimits = Field(default_factory=ContainerLimits)

    @classmethod
    def from_yaml(cls, path: Path | str) -> "ResourceConfig":
        """Load configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data.get("resources", data))

    @classmethod
    def from_profile(cls, profile: str) -> "ResourceConfig":
        """Load a named profile (tiny, small, medium, large)."""
        from .profiles import get_profile_path

        path = get_profile_path(profile)
        return cls.from_yaml(path)

    def to_duckdb_settings(self) -> dict[str, str]:
        """Generate DuckDB SET statements."""
        return {
            "memory_limit": self.duckdb.memory_limit,
            "threads": str(self.duckdb.threads),
            "temp_directory": f"'{self.duckdb.temp_directory}'",
            "preserve_insertion_order": str(self.duckdb.preserve_insertion_order).lower(),
        }


class Settings(BaseSettings):
    """Environment-based settings."""

    # S3/MinIO
    s3_endpoint: str = Field(default="http://localhost:9000")
    s3_access_key: str = Field(default="ratatouille")
    s3_secret_key: str = Field(default="ratatouille123")

    # Nessie
    nessie_uri: str = Field(default="http://localhost:19120/api/v2")
    nessie_default_branch: str = Field(default="main")

    # Iceberg
    iceberg_warehouse: str = Field(default="s3://warehouse/")

    # Resource profile
    rat_profile: Literal["tiny", "small", "medium", "large"] = Field(default="small")

    class Config:
        env_prefix = ""
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings from environment."""
    return Settings()


@lru_cache()
def get_resource_config() -> ResourceConfig:
    """Get resource configuration based on RAT_PROFILE env var."""
    settings = get_settings()
    return ResourceConfig.from_profile(settings.rat_profile)
