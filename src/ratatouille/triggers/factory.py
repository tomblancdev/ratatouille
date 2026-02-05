"""
🐀 Trigger Factory - Create triggers from YAML configuration

Parses pipeline YAML files and creates appropriate Dagster sensors/schedules.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from dagster import ScheduleDefinition, SensorDefinition

from ratatouille.triggers.schedules import (
    ScheduleConfig,
    create_freshness_schedule,
    create_schedule,
)
from ratatouille.triggers.sensors import S3SensorConfig, create_s3_sensor


@dataclass
class TriggerBundle:
    """Collection of triggers created from YAML configs."""

    sensors: list[SensorDefinition]
    schedules: list[ScheduleDefinition]


def create_triggers_from_yaml(
    yaml_path: Path,
    workspace: str,
    target_asset: str,
) -> TriggerBundle:
    """Create triggers from a pipeline YAML configuration.

    YAML format:
    ```yaml
    triggers:
      - type: s3_sensor
        path: bronze/sales/
        interval: 60

      - type: schedule
        cron: hourly  # or "0 * * * *"

      - type: freshness
        # Uses freshness config from YAML

    freshness:
      warn_after:
        hours: 6
      error_after:
        hours: 24
    ```

    Args:
        yaml_path: Path to the pipeline YAML file
        workspace: Workspace name
        target_asset: Dagster asset key to trigger

    Returns:
        TriggerBundle with sensors and schedules
    """
    sensors: list[SensorDefinition] = []
    schedules: list[ScheduleDefinition] = []

    if not yaml_path.exists():
        return TriggerBundle(sensors=sensors, schedules=schedules)

    with open(yaml_path) as f:
        config = yaml.safe_load(f) or {}

    pipeline_name = yaml_path.stem
    triggers = config.get("triggers", [])
    freshness = config.get("freshness", {})

    for trigger in triggers:
        trigger_type = trigger.get("type", "").lower()

        if trigger_type == "s3_sensor":
            sensor = _create_s3_trigger(trigger, workspace, pipeline_name, target_asset)
            if sensor:
                sensors.append(sensor)

        elif trigger_type == "schedule":
            sched = _create_schedule_trigger(
                trigger, workspace, pipeline_name, target_asset
            )
            if sched is not None:
                schedules.append(sched)

        elif trigger_type == "freshness":
            # Create schedule based on freshness requirements
            if freshness:
                sched = _create_freshness_trigger(
                    freshness, workspace, pipeline_name, target_asset
                )
                if sched is not None:
                    schedules.append(sched)

    return TriggerBundle(sensors=sensors, schedules=schedules)


def _create_s3_trigger(
    trigger: dict,
    workspace: str,
    pipeline_name: str,
    target_asset: str,
) -> SensorDefinition | None:
    """Create an S3 sensor from trigger config."""
    path = trigger.get("path", "")
    if not path:
        return None

    bucket = trigger.get("bucket", f"ratatouille-{workspace}")
    interval = trigger.get("interval", 60)
    pattern = trigger.get("pattern", "*.parquet")

    return create_s3_sensor(
        S3SensorConfig(
            name=f"{workspace}_{pipeline_name}_s3_sensor",
            bucket=bucket,
            prefix=path,
            target_asset=target_asset,
            interval_seconds=interval,
            file_pattern=pattern,
        )
    )


def _create_schedule_trigger(
    trigger: dict,
    workspace: str,
    pipeline_name: str,
    target_asset: str,
) -> ScheduleDefinition | None:
    """Create a schedule from trigger config."""
    cron = trigger.get("cron", "")
    if not cron:
        return None

    timezone = trigger.get("timezone", "UTC")

    return create_schedule(
        ScheduleConfig(
            name=f"{workspace}_{pipeline_name}_schedule",
            cron=cron,
            target_asset=target_asset,
            timezone=timezone,
        )
    )


def _create_freshness_trigger(
    freshness: dict,
    workspace: str,
    pipeline_name: str,
    target_asset: str,
) -> ScheduleDefinition | None:
    """Create a freshness-based schedule."""
    warn_after = freshness.get("warn_after", {})
    error_after = freshness.get("error_after", {})

    warn_hours = warn_after.get("hours", 12)
    error_hours = error_after.get("hours", 24)

    return create_freshness_schedule(
        workspace=workspace,
        pipeline_name=pipeline_name,
        target_asset=target_asset,
        warn_after_hours=warn_hours,
        error_after_hours=error_hours,
    )


def discover_workspace_triggers(
    workspace_path: Path,
    workspace_name: str,
) -> TriggerBundle:
    """Discover all triggers from a workspace's pipeline YAML files.

    Scans pipelines/**/*.yaml for trigger configurations.

    Args:
        workspace_path: Path to workspace directory
        workspace_name: Name of the workspace

    Returns:
        TriggerBundle with all discovered sensors and schedules
    """
    all_sensors: list[SensorDefinition] = []
    all_schedules: list[ScheduleDefinition] = []

    pipelines_dir = workspace_path / "pipelines"
    if not pipelines_dir.exists():
        return TriggerBundle(sensors=all_sensors, schedules=all_schedules)

    # Scan all YAML files in bronze/, silver/, gold/
    for layer in ["bronze", "silver", "gold"]:
        layer_dir = pipelines_dir / layer
        if not layer_dir.exists():
            continue

        for yaml_file in layer_dir.glob("*.yaml"):
            pipeline_name = yaml_file.stem
            target_asset = f"{workspace_name}__{layer}_{pipeline_name}"

            bundle = create_triggers_from_yaml(
                yaml_path=yaml_file,
                workspace=workspace_name,
                target_asset=target_asset,
            )

            all_sensors.extend(bundle.sensors)
            all_schedules.extend(bundle.schedules)

    return TriggerBundle(sensors=all_sensors, schedules=all_schedules)
