"""
🐀 Pipeline Triggers - Multiple ways to run pipelines

Supports:
- S3 Sensors: Watch for new files in S3/MinIO
- Schedules: Cron-based scheduling
- Webhooks: HTTP endpoints for external triggers
- Dependencies: Auto-trigger downstream when upstream completes
"""

from ratatouille.triggers.sensors import create_s3_sensor, S3SensorConfig
from ratatouille.triggers.schedules import create_schedule, ScheduleConfig
from ratatouille.triggers.factory import create_triggers_from_yaml

__all__ = [
    "create_s3_sensor",
    "S3SensorConfig",
    "create_schedule",
    "ScheduleConfig",
    "create_triggers_from_yaml",
]
