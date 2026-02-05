"""🏢 Workspace Manager - Create, load, and manage isolated workspaces."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ratatouille.catalog.iceberg import IcebergCatalog
    from ratatouille.engine.duckdb import DuckDBEngine
    from ratatouille.resources.config import ResourceConfig

from .config import WorkspaceConfig


class Workspace:
    """An isolated workspace with its own storage, catalog branch, and config.

    Each workspace has:
    - Its own Nessie branch (catalog isolation)
    - Its own S3 prefix (storage isolation)
    - Its own resource limits
    - Its own pipeline definitions

    Example:
        workspace = Workspace.load("acme")
        engine = workspace.get_engine()
        df = engine.query("SELECT * FROM bronze.sales")
    """

    def __init__(self, path: Path, config: WorkspaceConfig):
        self.path = path
        self.config = config
        self._engine: DuckDBEngine | None = None
        self._resources: ResourceConfig | None = None
        self._catalog: IcebergCatalog | None = None

    @classmethod
    def load(cls, name_or_path: str | Path) -> Workspace:
        """Load a workspace by name or path.

        Args:
            name_or_path: Workspace name (looked up in workspaces/) or full path

        Returns:
            Loaded Workspace instance

        Example:
            ws = Workspace.load("acme")
            ws = Workspace.load("/path/to/workspace")
        """
        path = Path(name_or_path)

        # If not a path, look up in standard locations
        if not path.exists():
            path = _find_workspace(name_or_path)

        config = WorkspaceConfig.from_directory(path)
        return cls(path=path, config=config)

    @classmethod
    def create(
        cls,
        name: str,
        base_dir: Path | str | None = None,
        description: str = "",
        git_sync: bool = False,
    ) -> Workspace:
        """Create a new workspace with default structure.

        Args:
            name: Workspace name (also used for S3 prefix)
            base_dir: Parent directory for workspaces (default: ./workspaces)
            description: Optional workspace description
            git_sync: If True, use "auto" mode for Nessie branch (syncs with Git)

        Returns:
            Created Workspace instance

        Example:
            # Standard workspace with fixed branch
            Workspace.create("acme")

            # Git-synced workspace (branch follows Git)
            Workspace.create("acme", git_sync=True)
        """
        if base_dir is None:
            base_dir = _get_workspaces_dir()
        else:
            base_dir = Path(base_dir)

        workspace_dir = base_dir / name

        # Create directory structure
        (workspace_dir / "pipelines" / "bronze").mkdir(parents=True, exist_ok=True)
        (workspace_dir / "pipelines" / "silver").mkdir(parents=True, exist_ok=True)
        (workspace_dir / "pipelines" / "gold").mkdir(parents=True, exist_ok=True)
        (workspace_dir / "schemas").mkdir(parents=True, exist_ok=True)
        (workspace_dir / "macros").mkdir(parents=True, exist_ok=True)
        (workspace_dir / "notebooks").mkdir(parents=True, exist_ok=True)

        # Determine Nessie branch configuration
        if git_sync:
            nessie_branch_config = "auto"
        else:
            nessie_branch_config = f"workspace/{name}"

        # Create config
        config = WorkspaceConfig(
            name=name,
            description=description,
            isolation={
                "nessie_branch": nessie_branch_config,
                "s3_prefix": name,
            },
        )
        config.to_yaml(workspace_dir / "workspace.yaml")

        # Create .gitkeep files
        for subdir in ["bronze", "silver", "gold"]:
            (workspace_dir / "pipelines" / subdir / ".gitkeep").touch()

        # Create the workspace instance first (so nessie_branch property resolves correctly)
        workspace = cls(path=workspace_dir, config=config)

        # Resolve the actual branch name (handles "auto" mode)
        actual_branch = workspace.nessie_branch

        # Create Nessie branch for workspace isolation
        nessie_uri = os.getenv("NESSIE_URI", "http://localhost:19120/api/v2")

        try:
            from ratatouille.catalog.nessie import BranchExistsError, NessieClient

            nessie = NessieClient(nessie_uri)
            try:
                nessie.create_branch(actual_branch, from_branch="main")
                print(f"🌳 Created Nessie branch: {actual_branch}")
            except BranchExistsError:
                print(f"🌳 Using existing Nessie branch: {actual_branch}")
            except Exception as e:
                # Nessie might not be available during testing/offline
                print(f"⚠️ Could not create Nessie branch: {e}")
            finally:
                nessie.close()
        except ImportError:
            print("⚠️ Nessie client not available, skipping branch creation")

        print(f"✅ Created workspace: {name}")
        print(f"   Path: {workspace_dir}")
        if git_sync:
            print(f"   Nessie branch: auto (currently: {actual_branch})")
            print("   💡 Tip: Run install_git_hooks() to auto-create branches on checkout")
        else:
            print(f"   Nessie branch: {actual_branch}")
        print(f"   S3 prefix: {name}/")

        return workspace

    @property
    def name(self) -> str:
        """Workspace name."""
        return self.config.name

    @property
    def nessie_branch(self) -> str:
        """Nessie branch for this workspace.

        Supports auto-detection from Git:
        - "auto" or "git": Uses current Git branch
        - "git:prefix/": Uses Git branch with prefix
        - Any other value: Uses as-is (literal branch name)
        """
        from .git_sync import resolve_nessie_branch

        return resolve_nessie_branch(
            configured_branch=self.config.isolation.nessie_branch,
            workspace_name=self.name,
            repo_path=self.path,
        )

    @property
    def s3_prefix(self) -> str:
        """S3 prefix for this workspace."""
        return self.config.isolation.s3_prefix

    @property
    def s3_endpoint(self) -> str:
        """S3 endpoint from environment."""
        return os.getenv("S3_ENDPOINT", "http://localhost:9000")

    @property
    def s3_access_key(self) -> str:
        """S3 access key from environment."""
        return os.getenv("S3_ACCESS_KEY", "ratatouille")

    @property
    def s3_secret_key(self) -> str:
        """S3 secret key from environment."""
        return os.getenv("S3_SECRET_KEY", "ratatouille123")

    @property
    def nessie_uri(self) -> str:
        """Nessie URI from environment."""
        return os.getenv("NESSIE_URI", "http://localhost:19120/api/v2")

    @property
    def resources(self) -> ResourceConfig:
        """Get resource configuration for this workspace."""
        if self._resources is None:
            from ratatouille.resources.config import ResourceConfig

            # Load base profile
            self._resources = ResourceConfig.from_profile(self.config.resources.profile)

            # Apply overrides
            overrides = self.config.resources.overrides
            if overrides.max_memory_mb:
                self._resources.max_memory_mb = overrides.max_memory_mb
            if overrides.max_parallel_pipelines:
                self._resources.max_parallel_pipelines = (
                    overrides.max_parallel_pipelines
                )
            if overrides.chunk_size_rows:
                self._resources.chunk_size_rows = overrides.chunk_size_rows

        return self._resources

    def get_engine(self) -> DuckDBEngine:
        """Get a DuckDB engine configured for this workspace."""
        if self._engine is None:
            from ratatouille.engine.duckdb import DuckDBEngine

            self._engine = DuckDBEngine.for_workspace(self)

        return self._engine

    def get_catalog(self) -> IcebergCatalog:
        """Get Iceberg catalog for this workspace's branch.

        The catalog is bound to this workspace's Nessie branch,
        providing isolation for data operations.

        Returns:
            IcebergCatalog instance

        Example:
            catalog = workspace.get_catalog()
            catalog.create_table("bronze.sales", df)
        """
        if self._catalog is None:
            from ratatouille.catalog.iceberg import IcebergCatalog

            self._catalog = IcebergCatalog.for_workspace(self)

        return self._catalog

    def s3_path(self, layer: str, table: str) -> str:
        """Get the S3 path for a table in this workspace.

        Args:
            layer: Medallion layer (bronze, silver, gold)
            table: Table name

        Returns:
            Full S3 path (e.g., "s3://warehouse/acme/bronze/sales/")
        """
        warehouse = os.getenv("ICEBERG_WAREHOUSE", "s3://warehouse/")
        warehouse = warehouse.rstrip("/")
        return f"{warehouse}/{self.s3_prefix}/{layer}/{table}/"

    def list_pipelines(self) -> dict[str, list[str]]:
        """List all pipelines in this workspace by layer.

        Returns:
            Dict mapping layer to list of pipeline files
        """
        result = {"bronze": [], "silver": [], "gold": []}

        for layer in result.keys():
            layer_dir = self.path / "pipelines" / layer
            if layer_dir.exists():
                # Python pipelines
                for f in layer_dir.glob("*.py"):
                    if not f.name.startswith("_"):
                        result[layer].append(f.name)
                # SQL pipelines
                for f in layer_dir.glob("*.sql"):
                    result[layer].append(f.name)

        return result

    def __repr__(self) -> str:
        return f"Workspace(name={self.name!r}, branch={self.nessie_branch!r})"


def _get_workspaces_dir() -> Path:
    """Get the default workspaces directory."""
    # Check common locations
    for path in [
        Path("workspaces"),
        Path("/app/workspaces"),
        Path.home() / "ratatouille" / "workspaces",
    ]:
        if path.exists():
            return path

    # Default to current directory
    return Path("workspaces")


def _find_workspace(name: str) -> Path:
    """Find a workspace by name in standard locations."""
    base = _get_workspaces_dir()
    path = base / name

    if path.exists():
        return path

    raise FileNotFoundError(
        f"Workspace '{name}' not found in {base}. "
        f"Available workspaces: {list_workspaces()}"
    )


def list_workspaces() -> list[str]:
    """List all available workspaces."""
    base = _get_workspaces_dir()
    if not base.exists():
        return []

    workspaces = []
    for path in base.iterdir():
        if path.is_dir() and (path / "workspace.yaml").exists():
            workspaces.append(path.name)

    return sorted(workspaces)


@lru_cache
def get_workspace(name: str | None = None) -> Workspace:
    """Get a workspace by name (cached).

    Args:
        name: Workspace name (default: "default")

    Returns:
        Cached Workspace instance
    """
    if name is None:
        name = os.getenv("WORKSPACE", "default")
    return Workspace.load(name)
