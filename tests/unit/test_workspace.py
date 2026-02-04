"""🧪 Tests for Workspace management."""

import pytest
import tempfile
from pathlib import Path

from ratatouille.workspace.config import (
    WorkspaceConfig,
    IsolationConfig,
    ResourcesConfig,
)
from ratatouille.workspace.manager import Workspace


class TestWorkspaceConfig:
    """Tests for WorkspaceConfig."""

    def test_create_minimal_config(self):
        """Test creating config with minimal required fields."""
        config = WorkspaceConfig(
            name="test",
            isolation=IsolationConfig(
                nessie_branch="workspace/test",
                s3_prefix="test",
            ),
        )

        assert config.name == "test"
        assert config.isolation.nessie_branch == "workspace/test"
        assert config.resources.profile == "small"  # default

    def test_from_yaml(self, tmp_path):
        """Test loading config from YAML."""
        yaml_content = """
name: test-workspace
version: "1.0"
description: "Test workspace"

isolation:
  nessie_branch: "workspace/test"
  s3_prefix: "test"

resources:
  profile: medium
  overrides:
    max_memory_mb: 8192
"""
        yaml_file = tmp_path / "workspace.yaml"
        yaml_file.write_text(yaml_content)

        config = WorkspaceConfig.from_yaml(yaml_file)

        assert config.name == "test-workspace"
        assert config.description == "Test workspace"
        assert config.resources.profile == "medium"
        assert config.resources.overrides.max_memory_mb == 8192

    def test_to_yaml(self, tmp_path):
        """Test saving config to YAML."""
        config = WorkspaceConfig(
            name="test",
            description="My workspace",
            isolation=IsolationConfig(
                nessie_branch="workspace/test",
                s3_prefix="test",
            ),
        )

        yaml_file = tmp_path / "workspace.yaml"
        config.to_yaml(yaml_file)

        # Reload and verify
        loaded = WorkspaceConfig.from_yaml(yaml_file)
        assert loaded.name == "test"
        assert loaded.description == "My workspace"

    def test_products_config(self, tmp_path):
        """Test products configuration."""
        yaml_content = """
name: test
isolation:
  nessie_branch: "workspace/test"
  s3_prefix: "test"

products:
  - name: sales_kpis
    source: gold.daily_sales
    access:
      - workspace: "*"
        level: read
    sla:
      freshness_hours: 24

subscriptions:
  - product: external_data
    alias: ext_data
    version_constraint: "^1.0.0"
"""
        yaml_file = tmp_path / "workspace.yaml"
        yaml_file.write_text(yaml_content)

        config = WorkspaceConfig.from_yaml(yaml_file)

        assert len(config.products) == 1
        assert config.products[0].name == "sales_kpis"
        assert config.products[0].source == "gold.daily_sales"

        assert len(config.subscriptions) == 1
        assert config.subscriptions[0].product == "external_data"
        assert config.subscriptions[0].alias == "ext_data"


class TestWorkspace:
    """Tests for Workspace class."""

    @pytest.fixture
    def workspace_dir(self, tmp_path):
        """Create a test workspace directory."""
        ws_dir = tmp_path / "test-workspace"
        ws_dir.mkdir()

        # Create workspace.yaml
        (ws_dir / "workspace.yaml").write_text("""
name: test
version: "1.0"
isolation:
  nessie_branch: "workspace/test"
  s3_prefix: "test"
""")

        # Create pipeline directories
        (ws_dir / "pipelines" / "bronze").mkdir(parents=True)
        (ws_dir / "pipelines" / "silver").mkdir(parents=True)
        (ws_dir / "pipelines" / "gold").mkdir(parents=True)

        return ws_dir

    def test_load_workspace(self, workspace_dir):
        """Test loading a workspace from path."""
        ws = Workspace.load(workspace_dir)

        assert ws.name == "test"
        assert ws.nessie_branch == "workspace/test"
        assert ws.s3_prefix == "test"

    def test_create_workspace(self, tmp_path):
        """Test creating a new workspace."""
        ws = Workspace.create(
            name="new-workspace",
            base_dir=tmp_path,
            description="A new workspace",
        )

        assert ws.name == "new-workspace"
        assert (tmp_path / "new-workspace" / "workspace.yaml").exists()
        assert (tmp_path / "new-workspace" / "pipelines" / "bronze").exists()
        assert (tmp_path / "new-workspace" / "pipelines" / "silver").exists()
        assert (tmp_path / "new-workspace" / "pipelines" / "gold").exists()

    def test_s3_path(self, workspace_dir, monkeypatch):
        """Test S3 path generation."""
        monkeypatch.setenv("ICEBERG_WAREHOUSE", "s3://my-warehouse")

        ws = Workspace.load(workspace_dir)

        path = ws.s3_path("bronze", "sales")
        assert path == "s3://my-warehouse/test/bronze/sales/"

    def test_list_pipelines(self, workspace_dir):
        """Test listing pipelines."""
        # Create some pipeline files
        (workspace_dir / "pipelines" / "bronze" / "ingest.py").touch()
        (workspace_dir / "pipelines" / "silver" / "clean.sql").touch()
        (workspace_dir / "pipelines" / "silver" / "clean.yaml").touch()
        (workspace_dir / "pipelines" / "gold" / "metrics.sql").touch()

        ws = Workspace.load(workspace_dir)
        pipelines = ws.list_pipelines()

        assert "ingest.py" in pipelines["bronze"]
        assert "clean.sql" in pipelines["silver"]
        assert "metrics.sql" in pipelines["gold"]
