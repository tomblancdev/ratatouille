"""🐀 Dagster Definitions - Ratatouille Data Platform.

Assets are loaded from:
1. Project pipelines (pipelines/) - Your production pipelines
2. Demo pipelines (src/ratatouille/pipelines/) - Built-in examples
3. Workspace pipelines (workspaces/*/pipelines/*.py) - Auto-discovered user pipelines
"""

import sys
from pathlib import Path

from dagster import Definitions, load_assets_from_modules

# Add project root to path so we can import from pipelines/
# In container: /app/src/ratatouille/definitions.py -> 3 parents -> /app
# Local: .../ratatouille/src/ratatouille/definitions.py -> 3 parents -> ratatouille/
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ratatouille.pipelines import pos_sales
from ratatouille.discovery import discover_workspace_assets, list_workspaces

# Import project pipelines (at root level)
try:
    import pipelines as project_pipelines
    project_assets = project_pipelines.all_assets
    project_sensors = project_pipelines.all_sensors
    project_checks = project_pipelines.all_asset_checks
    project_jobs = getattr(project_pipelines, 'all_jobs', [])
    print(f"   Project pipelines: {len(project_assets)} assets, {len(project_sensors)} sensors, {len(project_checks)} checks, {len(project_jobs)} jobs")
except ImportError as e:
    print(f"   ⚠️ No project pipelines found: {e}")
    project_assets = []
    project_sensors = []
    project_checks = []
    project_jobs = []

# Load demo assets
demo_assets = load_assets_from_modules([pos_sales])

# Auto-discover workspace assets
print("🐀 Ratatouille loading...")
workspace_assets = discover_workspace_assets()
workspaces = list_workspaces()

if workspaces:
    print(f"   Workspaces with pipelines: {', '.join(workspaces)}")
if workspace_assets:
    print(f"   Workspace assets: {len(workspace_assets)}")

# Combine all assets
all_assets = [*project_assets, *demo_assets, *workspace_assets]
all_sensors = [*project_sensors]
all_asset_checks = [*project_checks]
all_jobs = [*project_jobs]

# Dagster Definitions
defs = Definitions(
    assets=all_assets,
    sensors=all_sensors,
    asset_checks=all_asset_checks,
    jobs=all_jobs,
)

print(f"🐀 Ratatouille loaded! {len(all_assets)} assets, {len(all_sensors)} sensors, {len(all_asset_checks)} checks, {len(all_jobs)} jobs")
