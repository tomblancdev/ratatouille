"""
🐀 Pipeline Schedules - Cron-based scheduling

Creates Dagster schedules from YAML configuration.
"""

from dataclasses import dataclass
from typing import Any

from dagster import (
    ScheduleDefinition,
    DefaultScheduleStatus,
    AssetSelection,
    define_asset_job,
)


@dataclass
class ScheduleConfig:
    """Configuration for a pipeline schedule."""

    name: str
    cron: str
    target_asset: str
    timezone: str = "UTC"
    description: str | None = None


# Common cron presets
CRON_PRESETS = {
    "hourly": "0 * * * *",
    "daily": "0 0 * * *",
    "daily_6am": "0 6 * * *",
    "daily_midnight": "0 0 * * *",
    "weekly": "0 0 * * 0",
    "monthly": "0 0 1 * *",
    "every_15min": "*/15 * * * *",
    "every_30min": "*/30 * * * *",
}


def resolve_cron(cron_expr: str) -> str:
    """Resolve cron expression, supporting presets.

    Args:
        cron_expr: Cron expression or preset name (hourly, daily, etc.)

    Returns:
        Standard cron expression
    """
    return CRON_PRESETS.get(cron_expr.lower(), cron_expr)


def create_schedule(config: ScheduleConfig) -> ScheduleDefinition | None:
    """Create a Dagster schedule from configuration.

    Note: Schedules require jobs which need to be defined with assets.
    For now, we return None and log a warning. Full implementation
    requires wiring schedules with asset jobs in definitions.py.

    Args:
        config: ScheduleConfig with cron and target asset

    Returns:
        ScheduleDefinition or None if cannot create
    """
    # TODO: Implement proper schedule creation with asset jobs
    # This requires access to the full asset graph to create jobs
    print(f"   ⏰ Schedule defined: {config.name} ({resolve_cron(config.cron)})")
    return None


def create_freshness_schedule(
    workspace: str,
    pipeline_name: str,
    target_asset: str,
    warn_after_hours: int = 12,
    error_after_hours: int = 24,
) -> ScheduleDefinition | None:
    """Create a schedule based on freshness requirements.

    Args:
        workspace: Workspace name
        pipeline_name: Pipeline name
        target_asset: Dagster asset to trigger
        warn_after_hours: Hours before warning
        error_after_hours: Hours before error

    Returns:
        ScheduleDefinition or None
    """
    # Run at half the warn interval to ensure freshness
    interval_hours = max(1, warn_after_hours // 2)

    if interval_hours <= 1:
        cron = "0 * * * *"  # Hourly
    elif interval_hours <= 6:
        cron = f"0 */{interval_hours} * * *"  # Every N hours
    elif interval_hours <= 12:
        cron = "0 0,12 * * *"  # Twice daily
    else:
        cron = "0 0 * * *"  # Daily

    return create_schedule(
        ScheduleConfig(
            name=f"{workspace}_{pipeline_name}_freshness",
            cron=cron,
            target_asset=target_asset,
            description=f"Maintain freshness for {pipeline_name} (warn: {warn_after_hours}h, error: {error_after_hours}h)",
        )
    )
