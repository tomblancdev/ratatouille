# 🔧 Operator Troubleshooting

Solutions for common platform issues.

---

## Services Won't Start

### Check Logs

```bash
docker compose logs -f
```

### Port Conflicts

```bash
# Check what's using ports
lsof -i :3030  # Dagster
lsof -i :8889  # Jupyter
lsof -i :9000  # MinIO S3
lsof -i :9001  # MinIO Console
lsof -i :19120 # Nessie
```

**Solution:** Stop conflicting services or change ports in `docker-compose.override.yml`.

### Not Enough Memory

```bash
# Check Docker resource limits
docker system info | grep -i memory
```

**Solution:** Increase Docker Desktop memory limit or use a smaller profile:

```bash
RAT_PROFILE=tiny docker compose up -d
```

---

## MinIO Issues

### Connection Errors

```bash
# Check MinIO is healthy
curl http://localhost:9000/minio/health/live

# Expected: OK
```

### Buckets Not Created

```bash
# Check minio-init completed
docker compose logs minio-init

# Manually create buckets
docker compose run minio-init mc mb minio/warehouse
docker compose run minio-init mc mb minio/products
docker compose run minio-init mc mb minio/landing
```

### List Buckets

```bash
docker compose run minio-init mc ls minio/
```

---

## Nessie Issues

### Catalog Not Responding

```bash
# Check Nessie health
curl http://localhost:19120/api/v2/config

# Check logs
docker compose logs nessie
```

### Reset Catalog (Nuclear Option)

```bash
# Stop services
make down

# Delete Nessie data
docker volume rm ratatouille_nessie_data

# Restart
make up
```

---

## Dagster Issues

### Code Not Reloading

```bash
# Force restart
docker compose restart dagster

# Check for Python errors
docker compose logs dagster | grep -i error
```

### UI Not Loading

```bash
# Check Dagster is running
docker compose ps dagster

# Check logs
docker compose logs -f dagster
```

### Pipeline Failures

1. **Check Dagster UI** → Runs → Click failed run → View logs

2. **Check specific logs:**
   ```bash
   docker compose logs dagster | grep -i "asset_name"
   ```

3. **Common issues:**
   - Source file not found → Check MinIO
   - Catalog error → Check Nessie
   - Memory error → Increase limits

---

## Jupyter Issues

### Can't Connect

```bash
# Check Jupyter is running
docker compose ps jupyter

# Get token
docker compose logs jupyter | grep token
```

### Wrong Token

Default token: `ratatouille`

Or set custom token:

```bash
JUPYTER_TOKEN=mytoken docker compose up -d
```

### Kernel Dies

Usually caused by loading too much data into memory.

**Solutions:**
- Use smaller data samples
- Increase Jupyter memory limit
- Use streaming/chunked processing

---

## Memory Issues

### ClickHouse Out of Memory

If you're using ClickHouse for queries:

```bash
# Check container stats
docker stats ratatouille-clickhouse

# Increase memory in docker-compose.yml:
# clickhouse:
#   deploy:
#     resources:
#       limits:
#         memory: 4g
```

### General Memory Pressure

```bash
# Check all container memory
docker stats --no-stream

# Use smaller profile
RAT_PROFILE=tiny make up
```

---

## Network Issues

### Services Can't Communicate

Inside containers, use internal hostnames:
- `minio:9000` (not `localhost:9000`)
- `nessie:19120` (not `localhost:19120`)

### DNS Resolution Issues

```bash
# Check Docker network
docker network ls
docker network inspect ratatouille_default
```

---

## Data Recovery

### Backup Volumes

```bash
# Backup MinIO data
docker run --rm -v ratatouille_minio_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/minio-backup.tar.gz /data

# Backup Nessie catalog
docker run --rm -v ratatouille_nessie_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/nessie-backup.tar.gz /data
```

### Restore Volumes

```bash
# Restore MinIO
docker volume create ratatouille_minio_data
docker run --rm -v ratatouille_minio_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/minio-backup.tar.gz -C /

# Similar for Nessie...
```

---

## Getting Help

1. **Check logs first:** `docker compose logs -f`
2. **Verify health:** `make status`
3. **Review [Configuration](configuration.md)** for correct settings
4. **Check [GitHub Issues](https://github.com/ratatouille/ratatouille/issues)** for known problems
