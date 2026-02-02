"""📦 Ratatouille Pipelines - Production data pipelines.

This module exports all assets, sensors, and checks from submodules.

Structure:
    pipelines/
    ├── __init__.py      ← This file
    └── your_pipeline/   ← Your pipeline folder
        ├── __init__.py
        ├── assets.py
        └── checks.py

To add a new pipeline:
1. Create a folder: pipelines/my_pipeline/
2. Add __init__.py with: all_assets = [...], all_checks = [...]
3. Import and add to the lists below

Example:
    from .my_pipeline import all_assets as my_assets, all_checks as my_checks

    all_assets = [*my_assets]
    all_asset_checks = [*my_checks]
"""

# Combine all pipeline exports
all_assets = []
all_sensors = []
all_asset_checks = []
all_jobs = []
