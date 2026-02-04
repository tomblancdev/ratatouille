"""
🐀 Pipeline Schedules - Cron-based scheduling

Creates Dagster schedules from YAML configuration.
"""

from dataclasses import dataclass
from typing import Any

from dagster import (
    ScheduleDefinition,
    DefaultScheduleStatus,
    RunRequest,
    schedule,
    ScheduleEvaluationContext,
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


def create_schedule(config: ScheduleConfig) -> ScheduleDefinition:
    """Create a Dagster schedule from configuration.

    Args:
        config: ScheduleConfig with cron and target asset

    Returns:
        ScheduleDefinition that runs on the specified cron
    """
    cron_schedule = resolve_cron(config.cron)

    @schedule(
        name=config.name,
        cron_schedule=cron_schedule,
        default_status=DefaultScheduleStatus.RUNNING,
        execution_timezone=config.timezone,
        description=config.description or f"Run {config.target_asset} on schedule: {cron_schedule}",
    )
    def pipeline_schedule(context: ScheduleEvaluationContext):
        """Scheduled pipeline run."""
        return RunRequest(
            run_key=f"{config.name}_{context.scheduled_execution_time.isoformat()}",
            run_config={},
            tags={
                "trigger": "schedule",
                "schedule": config.name,
                "cron": cron_schedule,
            },
        )

    return pipeline_schedule


def create_freshness_schedule(
    workspace: str,
    pipeline_name: str,
    target_asset: str,
    warn_after_hours: int = 12,
    error_after_hours: int = 24,
) -> ScheduleDefinition:
    """Create a schedule based on freshness requirements.

    Runs frequently enough to meet freshness SLA.

    Args:
        workspace: Workspace name
        pipeline_name: Pipeline name
        target_asset: Dagster asset to trigger
        warn_after_hours: Hours before warning
        error_after_hours: Hours before error

    Returns:
        ScheduleDefinition that maintains freshness
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
