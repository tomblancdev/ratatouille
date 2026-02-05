# 💾 Backup & Recovery

Protecting your data with backups.

---

## What to Backup

| Component | Location | Contents |
|-----------|----------|----------|
| **MinIO** | `minio_data` volume | All Parquet files, landing data |
| **Nessie** | `nessie_data` volume | Iceberg catalog metadata |
| **Dagster** | `dagster_storage` volume | Run history, schedules |

---

## Backup MinIO Data

### Using MinIO Client

```bash
# Export all data to local folder
docker compose run minio-init mc mirror minio/ /backup/

# Or export specific bucket
docker compose run minio-init mc mirror minio/warehouse /backup/warehouse/
```

### Using S3 CLI

```bash
# If you have AWS CLI configured
aws s3 sync s3://warehouse /backup/warehouse \
  --endpoint-url http://localhost:9000
```

### Volume Backup

```bash
# Stop services first
docker compose stop

# Backup volume
docker run --rm \
  -v ratatouille_minio_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/minio-backup-$(date +%Y%m%d).tar.gz /data

# Restart
docker compose start
```

---

## Backup Nessie Catalog

The Nessie catalog stores all Iceberg table metadata.

```bash
# Stop services first (recommended)
docker compose stop

# Backup volume
docker run --rm \
  -v ratatouille_nessie_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/nessie-backup-$(date +%Y%m%d).tar.gz /data

# Restart
docker compose start
```

---

## Backup Dagster State

Optional - mostly for preserving run history:

```bash
docker run --rm \
  -v ratatouille_dagster_storage:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/dagster-backup-$(date +%Y%m%d).tar.gz /data
```

---

## Restore from Backup

### Restore MinIO

```bash
# Stop services
docker compose down

# Remove old volume
docker volume rm ratatouille_minio_data

# Create fresh volume
docker volume create ratatouille_minio_data

# Restore from backup
docker run --rm \
  -v ratatouille_minio_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/minio-backup-20240115.tar.gz -C /

# Restart
docker compose up -d
```

### Restore Nessie

```bash
docker volume rm ratatouille_nessie_data
docker volume create ratatouille_nessie_data

docker run --rm \
  -v ratatouille_nessie_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/nessie-backup-20240115.tar.gz -C /

docker compose up -d
```

---

## Automated Backups

### Cron Script

Create `/etc/cron.daily/ratatouille-backup`:

```bash
#!/bin/bash
BACKUP_DIR=/var/backups/ratatouille
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR

# Backup MinIO (hot backup)
docker compose -f /path/to/ratatouille/docker-compose.yml \
  run --rm minio-init mc mirror minio/ /backup/

# Keep 7 days of backups
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

### With Docker Labels

Add labels for backup tools like `docker-backup`:

```yaml
# docker-compose.yml
services:
  minio:
    labels:
      - "backup.enable=true"
      - "backup.schedule=0 2 * * *"
```

---

## Disaster Recovery Checklist

1. **Stop services:** `make down`
2. **Restore volumes** from latest backup
3. **Start services:** `make up`
4. **Verify:**
   - MinIO buckets exist: `docker compose run minio-init mc ls minio/`
   - Nessie responds: `curl http://localhost:19120/api/v2/config`
   - Dagster loads assets: Check UI
5. **Test a query** in Jupyter

---

## Point-in-Time Recovery

DuckDB with Parquet provides file-level recovery through MinIO versioning:

```bash
# Check MinIO versioning (if enabled)
mc ls --versions minio/warehouse/bronze/sales/

# Restore a specific version
mc cp --version-id=<version> minio/warehouse/bronze/sales/data.parquet ./restored.parquet
```

Or query data as of a specific time using file timestamps.

---

## External Storage Backup

For production, consider backing up to external S3:

```bash
# Sync to external S3 bucket
aws s3 sync s3://warehouse s3://my-backup-bucket/ratatouille/warehouse \
  --endpoint-url http://localhost:9000 \
  --source-region us-east-1
```
