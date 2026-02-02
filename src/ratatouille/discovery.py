"""🐀 Auto-discovery of pipelines from workspaces.

Scans workspaces/*/pipelines/*.py for Dagster assets and loads them automatically.

Usage in definitions.py:
    from ratatouille.discovery import discover_workspace_assets

    defs = Definitions(
        assets=[*builtin_assets, *discover_workspace_assets()],
    )
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any

from dagster import AssetsDefinition, asset


def discover_workspace_assets(
    workspaces_dir: str | Path = "/app/workspaces",
) -> list[AssetsDefinition]:
    """Discover and load assets from workspace pipeline files.

    Scans workspaces/*/pipelines/*.py for Dagster assets.

    Args:
        workspaces_dir: Path to workspaces directory

    Returns:
        List of discovered AssetsDefinition objects
    """
    workspaces_path = Path(workspaces_dir)
    discovered_assets: list[AssetsDefinition] = []

    if not workspaces_path.exists():
        return discovered_assets

    # Find all pipeline files: workspaces/*/pipelines/*.py
    pipeline_files = list(workspaces_path.glob("*/pipelines/*.py"))

    for pipeline_file in pipeline_files:
        # Skip __init__.py and __pycache__
        if pipeline_file.name.startswith("_"):
            continue

        try:
            assets = _load_assets_from_file(pipeline_file)
            discovered_assets.extend(assets)
        except Exception as e:
            print(f"⚠️  Failed to load {pipeline_file}: {e}")

    return discovered_assets


def _load_assets_from_file(file_path: Path) -> list[AssetsDefinition]:
    """Load Dagster assets from a Python file.

    Args:
        file_path: Path to the Python file

    Returns:
        List of AssetsDefinition objects found in the file
    """
    # Create a unique module name based on the file path
    workspace_name = file_path.parent.parent.name
    module_name = f"workspace_{workspace_name}_{file_path.stem}"

    # Load the module dynamically
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        return []

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"⚠️  Error executing {file_path}: {e}")
        return []

    # Find all AssetsDefinition objects in the module
    assets: list[AssetsDefinition] = []

    for name in dir(module):
        obj = getattr(module, name)

        # Check if it's an AssetsDefinition (decorated with @asset)
        if isinstance(obj, AssetsDefinition):
            assets.append(obj)

    if assets:
        print(f"   📦 Loaded {len(assets)} assets from {workspace_name}/pipelines/{file_path.name}")

    return assets


def list_workspaces(workspaces_dir: str | Path = "/app/workspaces") -> list[str]:
    """List all workspaces that have pipelines.

    Args:
        workspaces_dir: Path to workspaces directory

    Returns:
        List of workspace names with pipelines
    """
    workspaces_path = Path(workspaces_dir)

    if not workspaces_path.exists():
        return []

    workspaces = []
    for workspace_dir in workspaces_path.iterdir():
        if workspace_dir.is_dir():
            pipelines_dir = workspace_dir / "pipelines"
            if pipelines_dir.exists() and any(pipelines_dir.glob("*.py")):
                workspaces.append(workspace_dir.name)

    return workspaces
