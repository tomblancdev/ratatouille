# ⏰ Pipeline Triggers

Multiple ways to run your pipelines: sensors, schedules, and webhooks.

---

## Overview

| Trigger Type | Use Case | How It Works |
|--------------|----------|--------------|
| **S3 Sensor** | New file arrives | Polls S3/MinIO for new files |
| **Schedule** | Recurring runs | Cron-based scheduling |
| **Webhook** | External trigger | HTTP endpoint for external systems |
| **Freshness** | Data SLAs | Auto-schedule based on freshness requirements |

---

## S3 Sensors

Watch for new files in S3/MinIO and trigger pipelines automatically.

### YAML Configuration

Add to your pipeline's `config.yaml`:

```yaml
triggers:
  - type: s3_sensor
    path: bronze/sales/
    interval: 60      # Check every 60 seconds
    pattern: "*.parquet"  # File pattern to match

freshness:
  warn_after:
    hours: 6
  error_after:
    hours: 24
```

### Python Configuration

```python
from ratatouille.triggers import create_s3_sensor, S3SensorConfig

sensor = create_s3_sensor(
    S3SensorConfig(
        name="sales_landing_sensor",
        bucket="ratatouille-demo",
        prefix="bronze/sales/",
        target_asset="bronze_sales",
        interval_seconds=60,
        file_pattern="*.parquet",
    )
)
```

### How It Works

1. Sensor polls S3 every `interval_seconds`
2. Compares file timestamps against last check
3. If new files found, triggers the target asset
4. Dagster UI shows sensor ticks and history

---

## Schedules

Run pipelines on a recurring basis using cron expressions.

### YAML Configuration

```yaml
triggers:
  - type: schedule
    cron: daily       # Preset: daily at midnight
    timezone: UTC

# Or explicit cron
triggers:
  - type: schedule
    cron: "0 6 * * *"  # Daily at 6 AM
    timezone: America/New_York
```

### Cron Presets

| Preset | Cron Expression | When |
|--------|-----------------|------|
| `hourly` | `0 * * * *` | Every hour |
| `daily` | `0 0 * * *` | Midnight daily |
| `daily_6am` | `0 6 * * *` | 6 AM daily |
| `weekly` | `0 0 * * 0` | Sunday midnight |
| `monthly` | `0 0 1 * *` | 1st of month |
| `every_15min` | `*/15 * * * *` | Every 15 minutes |
| `every_30min` | `*/30 * * * *` | Every 30 minutes |

### Python Configuration

```python
from ratatouille.triggers import create_schedule, ScheduleConfig

schedule = create_schedule(
    ScheduleConfig(
        name="daily_sales_refresh",
        cron="daily_6am",  # Or "0 6 * * *"
        target_asset="gold_sales_summary",
        timezone="UTC",
    )
)
```

---

## Freshness-Based Triggers

Automatically schedule based on SLA requirements.

### YAML Configuration

```yaml
triggers:
  - type: freshness  # Uses freshness config below

freshness:
  warn_after:
    hours: 6
  error_after:
    hours: 24
```

This creates a schedule that runs often enough to meet the SLA:
- 6-hour warn → runs every 3 hours
- 24-hour error → ensures daily refresh

### How Interval Is Calculated

| Warn After | Generated Schedule |
|------------|-------------------|
| 1 hour | Hourly |
| 6 hours | Every 3 hours |
| 12 hours | Twice daily |
| 24+ hours | Daily |

---

## Webhooks

Trigger pipelines from external systems via HTTP.

### Configuration

```python
from ratatouille.triggers.webhooks import WebhookConfig, create_webhook_endpoint

config = WebhookConfig(
    name="sales_webhook",
    endpoint="/webhooks/bronze-sales",
    target_asset="bronze_sales",
    secret="my-shared-secret",  # Optional: for signature verification
)

endpoint = create_webhook_endpoint(config)
```

### Supported Payload Formats

**MinIO Bucket Notification:**

```json
{
  "EventName": "s3:ObjectCreated:Put",
  "Key": "warehouse/bronze/sales/data.parquet"
}
```

**Generic Webhook:**

```json
{
  "source": "airflow",
  "event": "data_ready",
  "bucket": "landing",
  "key": "sales/2024-01-15.csv"
}
```

### Calling the Webhook

```bash
# Simple trigger
curl -X POST http://localhost:3030/webhooks/bronze-sales \
  -H "Content-Type: application/json" \
  -d '{"source": "manual", "event": "trigger"}'

# With signature verification
curl -X POST http://localhost:3030/webhooks/bronze-sales \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=abc123..." \
  -d '{"source": "ci-pipeline", "event": "deploy_complete"}'
```

### MinIO Webhook Setup

Configure MinIO to send notifications:

```bash
# 1. Add webhook endpoint
mc admin config set myminio notify_webhook:ratatouille \
    endpoint="http://dagster:3000/webhooks/bronze-sales" \
    queue_limit="10000"

# 2. Restart MinIO
mc admin service restart myminio

# 3. Add bucket notification
mc event add myminio/landing arn:minio:sqs::ratatouille:webhook \
    --prefix bronze/sales/ \
    --suffix .parquet \
    --event put
```

---

## Combining Triggers

Pipelines can have multiple triggers:

```yaml
triggers:
  # Watch for new files
  - type: s3_sensor
    path: bronze/sales/
    interval: 60

  # Also run daily regardless
  - type: schedule
    cron: daily_6am

  # And maintain freshness SLA
  - type: freshness
```

---

## Viewing Triggers in Dagster

1. Open Dagster UI (http://localhost:3030)
2. Go to **Sensors** tab to see active sensors
3. Go to **Schedules** tab to see scheduled runs
4. Each sensor/schedule shows:
   - Status (running/stopped)
   - Last tick time
   - Recent runs triggered

### Managing Triggers

```bash
# Enable/disable in UI by clicking the toggle

# Or via CLI
docker compose exec dagster dagster sensor start sales_sensor
docker compose exec dagster dagster sensor stop sales_sensor

docker compose exec dagster dagster schedule start daily_refresh
docker compose exec dagster dagster schedule stop daily_refresh
```

---

## Best Practices

### 1. Set Appropriate Intervals

```yaml
# Don't poll too frequently for large directories
triggers:
  - type: s3_sensor
    path: bronze/sales/
    interval: 300  # 5 minutes is reasonable
```

### 2. Use Freshness for SLAs

```yaml
# Instead of arbitrary schedules, define SLAs
freshness:
  warn_after:
    hours: 6
  error_after:
    hours: 24
```

### 3. Combine for Reliability

```yaml
triggers:
  # Primary: Event-driven
  - type: s3_sensor
    path: bronze/sales/

  # Backup: Scheduled catch-all
  - type: schedule
    cron: daily
```

### 4. Use Webhooks for Complex Workflows

When you need integration with:
- CI/CD pipelines
- Airflow/other orchestrators
- External data providers
- Manual triggers

---

## Troubleshooting

### Sensor Not Running

```bash
# Check sensor status in Dagster UI
# Or via logs:
docker compose logs dagster | grep -i sensor
```

### Files Not Detected

```python
# Verify sensor configuration matches your files
# Check path and pattern:
# - path: "bronze/sales/"  (with trailing slash)
# - pattern: "*.parquet"
```

### Schedule Not Triggering

```bash
# Check timezone setting
# Dagster uses UTC by default

# Verify schedule is enabled in UI
```
