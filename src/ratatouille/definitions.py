"""🐀 Dagster Definitions - Ratatouille Data Platform.

Auto-discovers and loads:
1. SQL pipelines from workspaces/*/pipelines/**/*.sql
2. Python assets from workspaces/*/pipelines/*.py
3. Triggers (sensors, schedules) from YAML configs

The medallion architecture (bronze → silver → gold) is automatically
wired via {{ ref() }} dependencies in SQL files.
"""

import os
import sys
from pathlib import Path

from dagster import Definitions, load_assets_from_modules

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Determine workspaces directory
# In container: /app/workspaces
# Local dev: ./workspaces (relative to project root)
WORKSPACES_DIR = os.environ.get(
    "RATATOUILLE_WORKSPACES_DIR",
    "/app/workspaces"
    if Path("/app/workspaces").exists()
    else str(project_root / "workspaces"),
)

print("🐀 Ratatouille loading...")
print(f"   Workspaces dir: {WORKSPACES_DIR}")

# Import discovery functions (must be after sys.path modification)
from ratatouille.discovery import (  # noqa: E402
    discover_workspace_assets,
    discover_workspace_triggers,
    list_workspaces,
)
from ratatouille.testing.dagster import discover_asset_checks  # noqa: E402

# Import built-in demo pipelines (if they exist)
try:
    from ratatouille.pipelines import pos_sales

    demo_assets = load_assets_from_modules([pos_sales])
    print(f"   Demo assets: {len(demo_assets)}")
except ImportError:
    demo_assets = []

# Auto-discover workspace assets (SQL + Python)
workspace_assets = discover_workspace_assets(WORKSPACES_DIR)
workspaces = list_workspaces(WORKSPACES_DIR)

if workspaces:
    print(f"   Workspaces: {', '.join(workspaces)}")
if workspace_assets:
    print(f"   Workspace assets: {len(workspace_assets)}")

# Auto-discover triggers (sensors, schedules)
triggers = discover_workspace_triggers(WORKSPACES_DIR)

if triggers.sensors:
    print(f"   Sensors: {len(triggers.sensors)}")
if triggers.schedules:
    print(f"   Schedules: {len(triggers.schedules)}")

# Auto-discover asset checks (from quality tests)
asset_checks = discover_asset_checks(WORKSPACES_DIR)
if asset_checks:
    print(f"   Asset checks: {len(asset_checks)}")

# Import project-level pipelines (at root level, if they exist)
try:
    import pipelines as project_pipelines

    project_assets = getattr(project_pipelines, "all_assets", [])
    project_sensors = getattr(project_pipelines, "all_sensors", [])
    project_schedules = getattr(project_pipelines, "all_schedules", [])
    project_jobs = getattr(project_pipelines, "all_jobs", [])

    if project_assets:
        print(f"   Project assets: {len(project_assets)}")
except ImportError:
    project_assets = []
    project_sensors = []
    project_schedules = []
    project_jobs = []

# Combine all definitions
all_assets = [*demo_assets, *workspace_assets, *project_assets]
all_sensors = [*triggers.sensors, *project_sensors]
all_schedules = [*triggers.schedules, *project_schedules]
all_jobs = [*project_jobs]

# Create Dagster Definitions
defs = Definitions(
    assets=all_assets,
    asset_checks=asset_checks,
    sensors=all_sensors,
    schedules=all_schedules,
    jobs=all_jobs,
)

print("🐀 Ratatouille ready!")
print(
    f"   Total: {len(all_assets)} assets, {len(asset_checks)} checks, {len(all_sensors)} sensors, {len(all_schedules)} schedules"
)
