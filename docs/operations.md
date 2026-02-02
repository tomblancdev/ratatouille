# 🎯 Operations Guide

Running, monitoring, and troubleshooting Ratatouille in production.

---

## Quick Commands

```bash
make up        # Start platform
make down      # Stop platform
make logs      # Follow all logs
make status    # Container status
make query     # ClickHouse shell
make clean     # Stop + delete all data
```

---

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dagster** | http://localhost:3030 | None |
| **Jupyter** | http://localhost:8889 | Token: `ratatouille` |
| **MinIO Console** | http://localhost:9001 | `ratatouille` / `ratatouille123` |
| **ClickHouse HTTP** | http://localhost:8123 | `ratatouille` / `ratatouille123` |
| **ClickHouse Native** | localhost:9440 | `ratatouille` / `ratatouille123` |
| **MinIO S3 API** | http://localhost:9000 | `ratatouille` / `ratatouille123` |

---

## Starting & Stopping

### Start Platform

```bash
# Build and start all services
make up

# Or manually:
docker compose up -d --build

# Watch logs during startup
docker compose logs -f
```

### Stop Platform

```bash
# Stop (keeps data)
make down

# Stop and remove all data
make clean
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart dagster
docker compose restart jupyter
```

---

## Monitoring

### Service Health

```bash
# Container status
make status

# Expected output:
# ratatouille-clickhouse   running (healthy)
# ratatouille-dagster      running
# ratatouille-jupyter      running
# ratatouille-minio        running (healthy)
```

### Check Service Health

```bash
# MinIO
curl http://localhost:9000/minio/health/live

# ClickHouse
curl http://localhost:8123/ping

# Dagster (check if UI loads)
curl -s http://localhost:3030 | head -1
```

### View Logs

```bash
# All services
make logs

# Specific service
docker compose logs -f dagster
docker compose logs -f clickhouse
docker compose logs -f minio

# Last 100 lines
docker compose logs --tail=100 dagster
```

---

## Dagster Operations

### Dagster UI

**Assets Tab:**
- View all assets (Bronze/Silver/Gold)
- See lineage graph
- Materialize assets manually
- View run history

**Runs Tab:**
- View all pipeline runs
- Check logs for failed runs
- Re-run failed jobs

**Sensors Tab:**
- Enable/disable sensors
- View sensor tick history

### CLI Operations

```bash
# List all assets
docker compose exec dagster dagster asset list

# Materialize specific asset
docker compose exec dagster dagster asset materialize --select "my_bronze"

# Materialize asset + downstream
docker compose exec dagster dagster asset materialize --select "my_bronze+"

# Run all assets
docker compose exec dagster dagster asset materialize --select "*"

# Check asset status
docker compose exec dagster dagster asset check
```

### Reload Code

When you modify pipeline code:

```bash
# Dagster auto-reloads, but you can force it:
docker compose restart dagster

# Or use CLI
docker compose exec dagster dagster dev reload
```

---

## ClickHouse Operations

### Interactive Shell

```bash
make query

# Or manually:
docker compose exec clickhouse clickhouse-client \
    --user ratatouille \
    --password ratatouille123
```

### Common Queries

```sql
-- List tables
SHOW TABLES;

-- Table schema
DESCRIBE TABLE gold_sales;

-- Row counts
SELECT count() FROM gold_sales;

-- Query Iceberg data directly
SELECT count(*) FROM s3(
    'http://minio:9000/warehouse/bronze/sales/data/*.parquet',
    'ratatouille', 'ratatouille123', 'Parquet'
);

-- System info
SELECT version();
SELECT * FROM system.metrics;
```

### Create ClickHouse Table

```sql
-- Materialize gold data for BI
CREATE TABLE gold_sales
ENGINE = MergeTree()
ORDER BY (date, product_id)
AS SELECT * FROM s3(
    'http://minio:9000/warehouse/gold/sales/data/*.parquet',
    'ratatouille', 'ratatouille123', 'Parquet'
);
```

### Refresh ClickHouse Table

```sql
-- Drop and recreate with fresh data
DROP TABLE IF EXISTS gold_sales;

CREATE TABLE gold_sales
ENGINE = MergeTree()
ORDER BY (date, product_id)
AS SELECT * FROM s3(...);
```

---

## MinIO Operations

### Web Console

Access http://localhost:9001 with `ratatouille` / `ratatouille123`

- Browse buckets and files
- Upload/download files
- View bucket policies

### CLI (mc)

```bash
# Run mc inside the container
docker compose exec minio mc ls local/

# Or use the init container
docker compose run minio-init mc ls minio/landing/
```

### Common Operations

```bash
# List buckets
docker compose run minio-init mc ls minio/

# List files in bucket
docker compose run minio-init mc ls minio/landing/

# Upload file
docker compose run minio-init mc cp /path/to/file.xlsx minio/landing/

# Download file
docker compose run minio-init mc cp minio/landing/file.xlsx /tmp/

# Delete file
docker compose run minio-init mc rm minio/landing/old_file.xlsx
```

---

## Data Operations

### View Iceberg Tables

```python
from ratatouille import rat

# List all tables
rat.ice_all()

# List tables in namespace
rat.ice_tables("bronze")

# Table history (time travel)
rat.ice_history("bronze.sales")
```

### Reset/Rebuild Tables

```python
# Drop and recreate a table
rat.ice_drop("silver.sales")

# Re-run the pipeline in Dagster UI

# Or use CLI
# docker compose exec dagster dagster asset materialize --select "sales_silver"
```

### Reset File Tracking

```python
# Allow re-ingesting all files for a table
rat.reset_ingestion("bronze.sales")

# Reset all tracking
rat.reset_ingestion()
```

### Time Travel

```python
# View history
history = rat.ice_history("bronze.sales")
print(history)

# Read old version
old_df = rat.ice_time_travel("bronze.sales", snapshot_id=12345)
```

---

## Troubleshooting

### Services Won't Start

**Check logs:**
```bash
docker compose logs -f
```

**Port conflicts:**
```bash
# Check what's using ports
lsof -i :3030  # Dagster
lsof -i :8123  # ClickHouse
lsof -i :8889  # Jupyter
lsof -i :9000  # MinIO S3
lsof -i :9001  # MinIO Console
```

**Not enough memory:**
```bash
# Check Docker resource limits
docker system info | grep -i memory

# Increase in Docker Desktop settings
```

### ClickHouse Connection Errors

**From Jupyter/Dagster:**
```python
# Services use internal hostnames
# minio:9000, clickhouse:8123

# Check env vars
import os
print(os.getenv("CLICKHOUSE_HOST"))  # Should be "clickhouse"
```

**From host machine:**
```bash
# Use localhost
curl http://localhost:8123/ping
```

### MinIO Connection Errors

**Check MinIO is healthy:**
```bash
curl http://localhost:9000/minio/health/live
```

**Check buckets exist:**
```bash
docker compose run minio-init mc ls minio/
# Should show: bronze, gold, landing, silver, warehouse
```

### Iceberg Catalog Issues

**Catalog location:**
```
/app/workspaces/.iceberg/catalog.db
```

**Reset catalog (nuclear option):**
```bash
# Stop services
make down

# Delete catalog
rm -rf workspaces/.iceberg/

# Restart
make up
```

### Dagster Code Not Reloading

```bash
# Force restart
docker compose restart dagster

# Check for Python errors
docker compose logs dagster | grep -i error
```

### Pipeline Failures

1. **Check Dagster UI** → Runs → Click failed run → View logs

2. **Check specific asset logs:**
   ```bash
   docker compose logs dagster | grep -i "asset_name"
   ```

3. **Common issues:**
   - Source file not found → Check MinIO
   - Parser error → Check file format matches parser
   - ClickHouse error → Check SQL syntax

### Memory Issues

**ClickHouse out of memory:**
```bash
# Check container stats
docker stats ratatouille-clickhouse

# Increase memory limit in docker-compose.yml:
# clickhouse:
#   mem_limit: 4g
```

**Jupyter kernel dies:**
- Loading too much data into memory
- Use ClickHouse queries instead of loading full DataFrames

---

## Backup & Recovery

### Backup MinIO Data

```bash
# Export all data
docker compose run minio-init mc mirror minio/ /backup/

# Or use S3 sync
aws s3 sync s3://warehouse /backup/warehouse --endpoint-url http://localhost:9000
```

### Backup Iceberg Catalog

```bash
# Copy SQLite database
cp workspaces/.iceberg/catalog.db /backup/
```

### Backup ClickHouse

```bash
# Export table
docker compose exec clickhouse clickhouse-client \
    --user ratatouille --password ratatouille123 \
    --query "SELECT * FROM gold_sales FORMAT Parquet" > /backup/gold_sales.parquet
```

### Restore from Backup

```bash
# Restore MinIO data
docker compose run minio-init mc mirror /backup/ minio/

# Restore catalog
cp /backup/catalog.db workspaces/.iceberg/

# Restart
docker compose restart
```

---

## Performance Tuning

### ClickHouse

**For large queries:**
```sql
-- Increase memory limit
SET max_memory_usage = 10000000000;  -- 10GB

-- Parallel reading
SET max_threads = 8;
```

**Create indexes:**
```sql
-- Add index to materialized table
ALTER TABLE gold_sales ADD INDEX idx_date date TYPE minmax GRANULARITY 1;
```

### Dagster

**Concurrency:**
```yaml
# dagster.yaml (mount in container)
run_coordinator:
  config:
    max_concurrent_runs: 5
```

### MinIO

**For high throughput:**
```bash
# Increase container limits
# docker-compose.yml:
# minio:
#   mem_limit: 2g
#   cpus: 2
```

---

## Connecting BI Tools

### Power BI

1. Install ClickHouse ODBC driver
2. Connection string:
   ```
   Driver={ClickHouse ODBC Driver};
   Host=localhost;
   Port=8123;
   User=ratatouille;
   Password=ratatouille123;
   Database=default;
   ```

### Grafana

1. Add ClickHouse data source
2. Settings:
   - URL: `http://localhost:8123`
   - User: `ratatouille`
   - Password: `ratatouille123`

### Metabase

1. Add ClickHouse database
2. Settings:
   - Host: `localhost`
   - Port: `8123`
   - User: `ratatouille`
   - Password: `ratatouille123`

### Direct HTTP API

```bash
# Query via HTTP
curl 'http://localhost:8123/?user=ratatouille&password=ratatouille123' \
    --data-binary "SELECT * FROM gold_sales LIMIT 10 FORMAT JSON"
```

---

## Security Checklist

⚠️ **Before going to production:**

- [ ] Change all default passwords in `docker-compose.yml`
- [ ] Change Jupyter token
- [ ] Enable TLS/HTTPS
- [ ] Restrict network access (firewall rules)
- [ ] Use Docker secrets instead of env vars
- [ ] Enable ClickHouse user management
- [ ] Set up MinIO bucket policies
- [ ] Regular backups
- [ ] Log aggregation (ELK, Loki)
- [ ] Monitoring alerts (Prometheus, Grafana)
