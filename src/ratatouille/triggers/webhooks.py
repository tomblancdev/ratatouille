"""
🐀 Webhook Triggers - HTTP endpoints for external triggers

Creates webhook endpoints that can be called by:
- MinIO bucket notifications
- External systems (Airflow, CI/CD, etc.)
- Manual triggers via curl/API
"""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime

from dagster import RunRequest


@dataclass
class WebhookConfig:
    """Configuration for a webhook trigger."""

    name: str
    endpoint: str
    target_asset: str
    secret: str | None = None  # For signature verification


@dataclass
class WebhookPayload:
    """Parsed webhook payload."""

    source: str
    event_type: str
    bucket: str | None = None
    key: str | None = None
    timestamp: datetime | None = None
    raw: dict | None = None


def parse_minio_webhook(payload: dict) -> WebhookPayload:
    """Parse MinIO bucket notification webhook.

    MinIO sends notifications in S3-compatible format:
    {
        "EventName": "s3:ObjectCreated:Put",
        "Key": "bucket/path/to/file.parquet",
        "Records": [...]
    }
    """
    event_name = payload.get("EventName", "")
    key = payload.get("Key", "")

    # Parse bucket and object key
    parts = key.split("/", 1)
    bucket = parts[0] if parts else None
    object_key = parts[1] if len(parts) > 1 else None

    return WebhookPayload(
        source="minio",
        event_type=event_name,
        bucket=bucket,
        key=object_key,
        timestamp=datetime.utcnow(),
        raw=payload,
    )


def parse_generic_webhook(payload: dict) -> WebhookPayload:
    """Parse a generic webhook payload.

    Expected format:
    {
        "source": "my-system",
        "event": "data_ready",
        "bucket": "my-bucket",
        "key": "path/to/data"
    }
    """
    return WebhookPayload(
        source=payload.get("source", "unknown"),
        event_type=payload.get("event", payload.get("event_type", "trigger")),
        bucket=payload.get("bucket"),
        key=payload.get("key", payload.get("path")),
        timestamp=datetime.utcnow(),
        raw=payload,
    )


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify webhook signature using HMAC-SHA256.

    Args:
        payload: Raw request body
        signature: Signature from X-Webhook-Signature header
        secret: Shared secret for verification

    Returns:
        True if signature is valid
    """
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


def create_run_request_from_webhook(
    config: WebhookConfig,
    payload: WebhookPayload,
) -> RunRequest:
    """Create a Dagster RunRequest from a webhook payload.

    Args:
        config: Webhook configuration
        payload: Parsed webhook payload

    Returns:
        RunRequest to trigger the pipeline
    """
    return RunRequest(
        run_key=f"{config.name}_{payload.timestamp.isoformat() if payload.timestamp else datetime.utcnow().isoformat()}",
        run_config={},
        tags={
            "trigger": "webhook",
            "webhook": config.name,
            "source": payload.source,
            "event": payload.event_type,
            **({"bucket": payload.bucket} if payload.bucket else {}),
            **({"key": payload.key} if payload.key else {}),
        },
    )


# FastAPI endpoint factory (for use with Dagster's webserver or standalone API)
def create_webhook_endpoint(config: WebhookConfig) -> dict:
    """Create webhook endpoint configuration for FastAPI/Dagster.

    Returns a dict that can be used to register the endpoint:
    {
        "path": "/webhooks/my-pipeline",
        "handler": <function>,
        "methods": ["POST"],
    }

    Usage with FastAPI:
        endpoint = create_webhook_endpoint(config)
        app.add_api_route(endpoint["path"], endpoint["handler"], methods=endpoint["methods"])
    """

    async def webhook_handler(
        request_body: dict, x_webhook_signature: str | None = None
    ):
        """Handle incoming webhook."""
        # Verify signature if secret is configured
        if config.secret and x_webhook_signature:
            # Note: In real implementation, you'd get raw bytes from request
            import json

            payload_bytes = json.dumps(request_body).encode()
            if not verify_webhook_signature(
                payload_bytes, x_webhook_signature, config.secret
            ):
                return {"error": "Invalid signature"}, 401

        # Parse payload (try MinIO format first, then generic)
        if "EventName" in request_body:
            payload = parse_minio_webhook(request_body)
        else:
            payload = parse_generic_webhook(request_body)

        # Create run request (this would be sent to Dagster)
        run_request = create_run_request_from_webhook(config, payload)

        return {
            "status": "triggered",
            "run_key": run_request.run_key,
            "target": config.target_asset,
            "tags": run_request.tags,
        }

    return {
        "path": config.endpoint,
        "handler": webhook_handler,
        "methods": ["POST"],
        "name": config.name,
    }


# Example MinIO notification configuration
MINIO_WEBHOOK_CONFIG_EXAMPLE = """
# MinIO bucket notification setup (mc command):
#
# 1. Add webhook endpoint:
#    mc admin config set myminio notify_webhook:ratatouille \\
#        endpoint="http://dagster:3000/webhooks/bronze-sales" \\
#        queue_limit="10000"
#
# 2. Restart MinIO:
#    mc admin service restart myminio
#
# 3. Add bucket notification:
#    mc event add myminio/ratatouille-demo arn:minio:sqs::ratatouille:webhook \\
#        --prefix bronze/sales/ \\
#        --suffix .parquet \\
#        --event put
#
# Now any .parquet file uploaded to bronze/sales/ will trigger the webhook!
"""
