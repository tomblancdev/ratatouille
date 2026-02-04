"""
🐀 S3 Sensors - Watch for new files in S3/MinIO

Creates Dagster sensors that poll S3 for new files and trigger pipelines.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from dagster import (
    RunRequest,
    SensorDefinition,
    SensorEvaluationContext,
    sensor,
    SkipReason,
    DefaultSensorStatus,
)

import boto3
from botocore.client import Config
import os


@dataclass
class S3SensorConfig:
    """Configuration for an S3 sensor."""

    name: str
    bucket: str
    prefix: str
    target_asset: str
    interval_seconds: int = 60
    file_pattern: str = "*.parquet"


def get_s3_client():
    """Get S3 client configured for MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY", "ratatouille"),
        aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY", "ratatouille123"),
        config=Config(signature_version="s3v4"),
    )


def create_s3_sensor(config: S3SensorConfig) -> SensorDefinition:
    """Create a Dagster sensor that watches S3 for new files.

    Args:
        config: S3SensorConfig with bucket, prefix, and target asset

    Returns:
        SensorDefinition that triggers when new files appear
    """

    @sensor(
        name=config.name,
        minimum_interval_seconds=config.interval_seconds,
        default_status=DefaultSensorStatus.RUNNING,
        description=f"Watch s3://{config.bucket}/{config.prefix} for new files",
    )
    def s3_file_sensor(context: SensorEvaluationContext):
        """Check S3 for new files since last run."""
        # Get last check time from cursor
        last_check_str = context.cursor
        if last_check_str:
            last_check = datetime.fromisoformat(last_check_str)
        else:
            # First run - look back 1 hour
            last_check = datetime.utcnow() - timedelta(hours=1)

        try:
            s3 = get_s3_client()

            # List objects in the prefix
            response = s3.list_objects_v2(
                Bucket=config.bucket,
                Prefix=config.prefix,
            )

            new_files = []
            if "Contents" in response:
                for obj in response["Contents"]:
                    # Check if file is newer than last check
                    modified = obj["LastModified"].replace(tzinfo=None)
                    if modified > last_check:
                        # Check file pattern
                        key = obj["Key"]
                        if config.file_pattern == "*" or key.endswith(
                            config.file_pattern.replace("*", "")
                        ):
                            new_files.append(key)

            # Update cursor to now
            context.update_cursor(datetime.utcnow().isoformat())

            if new_files:
                context.log.info(f"Found {len(new_files)} new files in {config.prefix}")
                # Trigger the target asset
                return RunRequest(
                    run_key=f"{config.name}_{datetime.utcnow().isoformat()}",
                    run_config={},
                    tags={
                        "trigger": "s3_sensor",
                        "sensor": config.name,
                        "new_files": str(len(new_files)),
                    },
                )
            else:
                return SkipReason(f"No new files in s3://{config.bucket}/{config.prefix}")

        except Exception as e:
            context.log.error(f"S3 sensor error: {e}")
            return SkipReason(f"Error checking S3: {e}")

    return s3_file_sensor


def create_bronze_sensor(
    workspace: str,
    source_name: str,
    target_asset: str,
    interval_seconds: int = 60,
) -> SensorDefinition:
    """Convenience function to create a sensor for bronze layer data.

    Args:
        workspace: Workspace name
        source_name: Name of the data source (e.g., 'sales', 'events')
        target_asset: Dagster asset to trigger
        interval_seconds: Polling interval

    Returns:
        SensorDefinition watching for new bronze data
    """
    bucket = f"ratatouille-{workspace}"
    prefix = f"bronze/{source_name}/"

    return create_s3_sensor(
        S3SensorConfig(
            name=f"{workspace}_{source_name}_sensor",
            bucket=bucket,
            prefix=prefix,
            target_asset=target_asset,
            interval_seconds=interval_seconds,
        )
    )
