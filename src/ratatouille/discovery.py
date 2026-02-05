"""🐀 Auto-discovery of pipelines from workspaces.

Discovers and creates Dagster assets from:
1. Python files with @asset decorators (workspaces/*/pipelines/*.py)
2. SQL files with YAML configs (workspaces/*/pipelines/**/*.sql)

Also discovers triggers (sensors, schedules) from YAML configurations.

Usage in definitions.py:
    from ratatouille.discovery import discover_workspace_assets, discover_workspace_triggers

    assets = discover_workspace_assets()
    triggers = discover_workspace_triggers()

    defs = Definitions(
        assets=assets,
        sensors=triggers.sensors,
        schedules=triggers.schedules,
    )
"""

import importlib.util
import os
import sys
from pathlib import Path

import yaml
from dagster import (
    AssetExecutionContext,
    AssetIn,
    AssetKey,
    AssetsDefinition,
    Output,
    asset,
)

from ratatouille.pipeline.parser import SQLParser
from ratatouille.triggers.factory import (
    TriggerBundle,
)
from ratatouille.triggers.factory import (
    discover_workspace_triggers as _discover_triggers,
)


def discover_workspace_assets(
    workspaces_dir: str | Path = "/app/workspaces",
) -> list[AssetsDefinition]:
    """Discover and load assets from workspace pipeline files.

    Scans:
    - workspaces/*/pipelines/*.py - Python assets with @asset decorator
    - workspaces/*/pipelines/**/*.sql - SQL pipelines with YAML config

    Args:
        workspaces_dir: Path to workspaces directory

    Returns:
        List of discovered AssetsDefinition objects
    """
    workspaces_path = Path(workspaces_dir)
    discovered_assets: list[AssetsDefinition] = []

    if not workspaces_path.exists():
        return discovered_assets

    # Find all workspaces
    for workspace_dir in workspaces_path.iterdir():
        if not workspace_dir.is_dir():
            continue

        workspace_name = workspace_dir.name
        pipelines_dir = workspace_dir / "pipelines"

        if not pipelines_dir.exists():
            continue

        # Discover Python assets
        python_assets = _discover_python_assets(pipelines_dir, workspace_name)
        discovered_assets.extend(python_assets)

        # Discover SQL assets
        sql_assets = _discover_sql_assets(pipelines_dir, workspace_name)
        discovered_assets.extend(sql_assets)

    return discovered_assets


def discover_workspace_triggers(
    workspaces_dir: str | Path = "/app/workspaces",
) -> TriggerBundle:
    """Discover triggers (sensors, schedules) from workspace YAML configs.

    Args:
        workspaces_dir: Path to workspaces directory

    Returns:
        TriggerBundle with all sensors and schedules
    """
    workspaces_path = Path(workspaces_dir)
    all_sensors = []
    all_schedules = []

    if not workspaces_path.exists():
        return TriggerBundle(sensors=all_sensors, schedules=all_schedules)

    for workspace_dir in workspaces_path.iterdir():
        if not workspace_dir.is_dir():
            continue

        bundle = _discover_triggers(workspace_dir, workspace_dir.name)
        all_sensors.extend(bundle.sensors)
        all_schedules.extend(bundle.schedules)

    return TriggerBundle(sensors=all_sensors, schedules=all_schedules)


def _discover_python_assets(
    pipelines_dir: Path,
    workspace_name: str,
) -> list[AssetsDefinition]:
    """Discover Python assets with @asset decorator."""
    assets: list[AssetsDefinition] = []

    # Find all .py files (not in subdirectories for now)
    for py_file in pipelines_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        try:
            file_assets = _load_assets_from_file(py_file, workspace_name)
            assets.extend(file_assets)
        except Exception as e:
            print(f"⚠️  Failed to load {py_file}: {e}")

    return assets


def _discover_sql_assets(
    pipelines_dir: Path,
    workspace_name: str,
) -> list[AssetsDefinition]:
    """Discover SQL assets from bronze/silver/gold directories."""
    assets: list[AssetsDefinition] = []

    for layer in ["bronze", "silver", "gold"]:
        layer_dir = pipelines_dir / layer

        if not layer_dir.exists():
            continue

        # Find all .sql files
        for sql_file in layer_dir.glob("*.sql"):
            yaml_file = sql_file.with_suffix(".yaml")

            try:
                asset_def = _create_sql_asset(
                    sql_file=sql_file,
                    yaml_file=yaml_file if yaml_file.exists() else None,
                    workspace_name=workspace_name,
                    layer=layer,
                )
                if asset_def:
                    assets.append(asset_def)
                    print(
                        f"   📦 Loaded SQL asset: {workspace_name}/{layer}/{sql_file.stem}"
                    )
            except Exception as e:
                print(f"⚠️  Failed to load {sql_file}: {e}")

    return assets


def _load_assets_from_file(
    file_path: Path,
    workspace_name: str,
) -> list[AssetsDefinition]:
    """Load Dagster assets from a Python file."""
    module_name = f"workspace_{workspace_name}_{file_path.stem}"

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

    assets: list[AssetsDefinition] = []
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, AssetsDefinition):
            assets.append(obj)

    if assets:
        print(
            f"   📦 Loaded {len(assets)} Python assets from {workspace_name}/{file_path.name}"
        )

    return assets


def _create_sql_asset(
    sql_file: Path,
    yaml_file: Path | None,
    workspace_name: str,
    layer: str,
) -> AssetsDefinition | None:
    """Create a Dagster asset from a SQL file.

    The asset will:
    1. Parse the SQL template
    2. Resolve {{ ref() }} dependencies
    3. Execute the SQL using DuckDB
    4. Write results to S3/MinIO as Parquet
    """
    # Parse SQL file
    parser = SQLParser()
    parsed = parser.parse_file(str(sql_file))

    # Load YAML config if exists
    config = {}
    if yaml_file and yaml_file.exists():
        with open(yaml_file) as f:
            config = yaml.safe_load(f) or {}

    # Build asset key
    asset_name = parsed.name or sql_file.stem
    asset_key = AssetKey([workspace_name, layer, asset_name])

    # Build dependencies from {{ ref() }} calls
    deps = {}
    for dep in parsed.dependencies:
        # Parse dependency like "silver.events" -> ["workspace", "silver", "events"]
        if "." in dep:
            dep_layer, dep_name = dep.split(".", 1)
        else:
            dep_layer = "bronze"
            dep_name = dep

        dep_key = AssetKey([workspace_name, dep_layer, dep_name])
        deps[dep] = AssetIn(key=dep_key)

    # Get metadata from YAML
    description = config.get("description", f"{layer.title()} pipeline: {asset_name}")
    owner = config.get("owner", parsed.owner)
    columns = config.get("columns", [])

    # Create the asset (use key only, not name)
    @asset(
        key=asset_key,
        ins=deps if deps else None,
        description=description,
        owners=[owner] if owner else None,
        metadata={
            "sql_file": str(sql_file),
            "layer": layer,
            "workspace": workspace_name,
            "materialized": parsed.materialized,
            "columns": len(columns),
        },
        compute_kind="duckdb",
    )
    def sql_asset(context: AssetExecutionContext, **inputs):
        """Execute SQL pipeline and write to storage."""
        import duckdb

        # Compile SQL with current context
        sql = parser.compile(
            parsed,
            is_incremental=False,  # TODO: Check if incremental run
        )

        context.log.info(f"Executing SQL:\n{sql[:500]}...")

        # Execute with DuckDB
        conn = duckdb.connect()

        # Configure S3/MinIO access
        endpoint = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
        access_key = os.environ.get("MINIO_ACCESS_KEY", "ratatouille")
        secret_key = os.environ.get("MINIO_SECRET_KEY", "ratatouille123")

        conn.execute(f"""
            SET s3_endpoint='{endpoint.replace("http://", "").replace("https://", "")}';
            SET s3_access_key_id='{access_key}';
            SET s3_secret_access_key='{secret_key}';
            SET s3_use_ssl=false;
            SET s3_url_style='path';
        """)

        try:
            result = conn.execute(sql).fetchdf()
            context.log.info(f"Query returned {len(result)} rows")

            # Write to S3
            bucket = f"ratatouille-{workspace_name}"
            output_path = f"s3://{bucket}/{layer}/{asset_name}/data.parquet"

            conn.execute(f"""
                COPY (SELECT * FROM result) TO '{output_path}'
                (FORMAT PARQUET, OVERWRITE_OR_IGNORE true)
            """)

            context.log.info(f"Written to {output_path}")

            return Output(
                value=result,
                metadata={
                    "rows": len(result),
                    "columns": list(result.columns),
                    "output_path": output_path,
                },
            )

        finally:
            conn.close()

    return sql_asset


def list_workspaces(workspaces_dir: str | Path = "/app/workspaces") -> list[str]:
    """List all workspaces that have pipelines."""
    workspaces_path = Path(workspaces_dir)

    if not workspaces_path.exists():
        return []

    workspaces = []
    for workspace_dir in workspaces_path.iterdir():
        if workspace_dir.is_dir():
            pipelines_dir = workspace_dir / "pipelines"
            if pipelines_dir.exists():
                # Check for any .py or .sql files
                has_pipelines = any(pipelines_dir.glob("*.py")) or any(
                    pipelines_dir.glob("**/*.sql")
                )
                if has_pipelines:
                    workspaces.append(workspace_dir.name)

    return workspaces
