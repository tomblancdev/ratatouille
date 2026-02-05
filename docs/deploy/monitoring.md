# 📊 Monitoring

Health checks, logs, and observability.

---

## Service Health

### Quick Status Check

```bash
make status
# or: docker compose ps
```

Expected output:

```
NAME                      STATUS
ratatouille-minio         running (healthy)
ratatouille-nessie        running (healthy)
ratatouille-dagster       running
ratatouille-jupyter       running
ratatouille-minio-init    exited (0)
```

### Health Endpoints

| Service | Endpoint | Expected |
|---------|----------|----------|
| MinIO | `http://localhost:9000/minio/health/live` | OK |
| Nessie | `http://localhost:19120/api/v2/config` | JSON config |
| Dagster | `http://localhost:3030` | UI loads |

### Check Health via curl

```bash
# MinIO
curl http://localhost:9000/minio/health/live

# Nessie
curl http://localhost:19120/api/v2/config

# Dagster (check if UI is up)
curl -s http://localhost:3030 | head -1
```

---

## Viewing Logs

### All Services

```bash
make logs
# or: docker compose logs -f
```

### Specific Service

```bash
docker compose logs -f dagster
docker compose logs -f minio
docker compose logs -f nessie
docker compose logs -f jupyter
```

### Historical Logs

```bash
# Last 100 lines
docker compose logs --tail=100 dagster

# Since a specific time
docker compose logs --since="2024-01-15T10:00:00" dagster

# Include timestamps
docker compose logs -t dagster
```

---

## Dagster Monitoring

### Pipeline Runs

1. Open Dagster UI (http://localhost:3030)
2. Go to **Runs** tab
3. View:
   - Run status (success/failure)
   - Duration
   - Logs
   - Error messages

### Asset Health

1. Go to **Assets** tab
2. Check:
   - Last materialization time
   - Run history
   - Data freshness

### Sensors & Schedules

1. Go to **Sensors** tab
2. Check:
   - Sensor status (running/stopped)
   - Last tick time
   - Skip reasons

3. Go to **Schedules** tab
4. Check:
   - Next scheduled run
   - Recent executions

---

## Resource Monitoring

### Container Stats

```bash
# Real-time stats
docker stats

# Specific containers
docker stats ratatouille-dagster ratatouille-minio
```

Output shows:
- CPU %
- Memory usage
- Network I/O
- Disk I/O

### Memory Usage

```bash
# Check container memory
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}"
```

---

## MinIO Monitoring

### Web Console

Access http://localhost:9001 with `ratatouille` / `ratatouille123`

- **Dashboard:** Storage metrics, bucket stats
- **Buckets:** File counts, sizes
- **Monitoring:** System metrics

### Metrics Endpoint

```bash
# MinIO exposes Prometheus metrics
curl http://localhost:9000/minio/v2/metrics/cluster
```

---

## Nessie Monitoring

### API Health

```bash
curl http://localhost:19120/api/v2/config
```

### List Branches

```bash
curl http://localhost:19120/api/v2/trees
```

---

## Alerting

### Simple Alert Script

```bash
#!/bin/bash
# health-check.sh

SERVICES=("minio:9000" "nessie:19120")

for SERVICE in "${SERVICES[@]}"; do
    NAME=$(echo $SERVICE | cut -d: -f1)
    PORT=$(echo $SERVICE | cut -d: -f2)

    if ! curl -sf "http://localhost:$PORT" > /dev/null; then
        echo "ALERT: $NAME is down!"
        # Send notification (email, Slack, etc.)
    fi
done
```

### Cron-based Monitoring

```bash
# Check every 5 minutes
*/5 * * * * /path/to/health-check.sh >> /var/log/ratatouille-health.log 2>&1
```

---

## Prometheus Integration

### MinIO Metrics

MinIO exposes Prometheus metrics at `/minio/v2/metrics/cluster`.

**Prometheus config:**

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'minio'
    metrics_path: /minio/v2/metrics/cluster
    static_configs:
      - targets: ['localhost:9000']
```

### Dagster Metrics

Dagster can export OpenTelemetry metrics. Configure via environment:

```yaml
services:
  dagster:
    environment:
      DAGSTER_TELEMETRY_ENABLED: "true"
```

---

## Grafana Dashboard

For visual monitoring, deploy Grafana:

```yaml
# Add to docker-compose.override.yml
services:
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  grafana_data:
```

Then create dashboards for:
- MinIO storage metrics
- Container resource usage
- Pipeline run stats

---

## Log Aggregation

### Using Loki

For centralized logging:

```yaml
# docker-compose.override.yml
services:
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"

  dagster:
    logging:
      driver: loki
      options:
        loki-url: "http://localhost:3100/loki/api/v1/push"
```

---

## Debugging Issues

### Check What's Wrong

```bash
# 1. Check container status
docker compose ps

# 2. Check logs
docker compose logs --tail=50 <service>

# 3. Check resources
docker stats --no-stream

# 4. Check health endpoints
curl http://localhost:9000/minio/health/live
```

### Common Issues

| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| Service "unhealthy" | Out of memory | `docker stats` |
| Service "exited" | Startup error | `docker compose logs <service>` |
| Slow queries | Resource limits | Increase memory in profile |
| Connection refused | Service not ready | Wait or restart |

---

## Uptime Monitoring

For external uptime monitoring, expose health endpoints:

| Service | Check URL | Expected Status |
|---------|----------|-----------------|
| MinIO | `/minio/health/live` | 200 |
| Nessie | `/api/v2/config` | 200 |
| Dagster | `/` | 200 |

Use services like:
- UptimeRobot
- Pingdom
- StatusCake
