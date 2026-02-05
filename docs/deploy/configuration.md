# ⚙️ Configuration

Customize Ratatouille for your environment.

---

## Configuration Methods

| Method | Use Case |
|--------|----------|
| Environment variables | Container runtime settings |
| `.env` file | Local development defaults |
| `docker-compose.override.yml` | Custom Docker settings |
| Resource profiles | VM-size presets |
| `workspace.yaml` | Per-workspace settings |

---

## Environment Variables

### Quick Setup

Create a `.env` file in your project root:

```bash
# .env
MINIO_ROOT_USER=myuser
MINIO_ROOT_PASSWORD=mysecretpassword
RAT_PROFILE=medium
JUPYTER_TOKEN=mysecrettoken
```

Docker Compose automatically loads this file.

### Key Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ROOT_USER` | `ratatouille` | S3 access key |
| `MINIO_ROOT_PASSWORD` | `ratatouille123` | S3 secret key |
| `RAT_PROFILE` | `small` | Resource profile |
| `JUPYTER_TOKEN` | `ratatouille` | Jupyter access token |
| `RATATOUILLE_WORKSPACE` | `demo` | Default workspace |

See [Environment Variables Reference](../reference/environment-variables.md) for complete list.

---

## Resource Profiles

Predefined configurations for different VM sizes:

| Profile | RAM | Use Case |
|---------|-----|----------|
| `tiny` | 4GB | Raspberry Pi, minimal VMs |
| `small` | 20GB | Typical self-hosted (default) |
| `medium` | 64GB | Production workloads |
| `large` | 128GB+ | Large-scale processing |

### Using Profiles

```bash
# Set profile
RAT_PROFILE=medium docker compose up -d

# Or in .env
RAT_PROFILE=medium
```

### Profile Settings

**tiny (4GB VM):**
```yaml
resources:
  minio_memory: 512M
  nessie_memory: 256M
  dagster_memory: 1G
  jupyter_memory: 1G
  duckdb_memory_mb: 1024
  chunk_size_rows: 10000
  max_parallel_pipelines: 1
```

**small (20GB VM) - Default:**
```yaml
resources:
  minio_memory: 1G
  nessie_memory: 768M
  dagster_memory: 2G
  jupyter_memory: 2G
  duckdb_memory_mb: 4096
  chunk_size_rows: 50000
  max_parallel_pipelines: 2
```

**medium (64GB VM):**
```yaml
resources:
  minio_memory: 2G
  nessie_memory: 1G
  dagster_memory: 4G
  jupyter_memory: 4G
  duckdb_memory_mb: 16384
  chunk_size_rows: 200000
  max_parallel_pipelines: 4
```

**large (128GB+ VM):**
```yaml
resources:
  minio_memory: 4G
  nessie_memory: 2G
  dagster_memory: 8G
  jupyter_memory: 8G
  duckdb_memory_mb: 65536
  chunk_size_rows: 500000
  max_parallel_pipelines: 8
```

---

## Docker Compose Customization

### Override File

Create `docker-compose.override.yml` for local customizations:

```yaml
# docker-compose.override.yml
services:
  dagster:
    ports:
      - "3031:3000"  # Different port
    volumes:
      - /external/path:/app/workspaces/external

  jupyter:
    ports:
      - "8890:8888"
```

### Additional Mounts

Mount external workspaces:

```yaml
services:
  dagster:
    volumes:
      - /home/user/projects/analytics:/app/workspaces/analytics

  jupyter:
    volumes:
      - /home/user/projects/analytics:/app/workspaces/analytics
```

---

## Workspace Configuration

Each workspace has a `workspace.yaml`:

```yaml
# workspace.yaml
name: analytics
version: "1.0"
description: "Analytics team workspace"

# Isolation settings
isolation:
  nessie_branch: "workspace/analytics"
  s3_prefix: "analytics"

# Resource limits (override profile)
resources:
  profile: small
  overrides:
    max_memory_mb: 8192
    max_parallel_pipelines: 4

# Medallion layer settings
layers:
  bronze:
    retention_days: 90
    partition_by: [_ingested_date]
  silver:
    retention_days: 365
  gold:
    retention_days: null  # Keep forever
```

---

## Port Mapping

Default ports:

| Service | Container Port | Host Port |
|---------|---------------|-----------|
| Dagster | 3000 | 3030 |
| Jupyter | 8888 | 8889 |
| MinIO S3 | 9000 | 9000 |
| MinIO Console | 9001 | 9001 |
| Nessie | 19120 | 19120 |

Change host ports in `docker-compose.override.yml` if conflicts occur.

---

## Network Configuration

### Internal Hostnames

Inside containers, use internal names:

| Service | Internal URL |
|---------|-------------|
| MinIO | `http://minio:9000` |
| Nessie | `http://nessie:19120` |
| Dagster | `http://dagster:3000` |

### MTU Settings

For VPN environments:

```yaml
# docker-compose.yml already includes
networks:
  default:
    driver: bridge
    driver_opts:
      com.docker.network.driver.mtu: "1370"
```

---

## Logging Configuration

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f dagster

# Last 100 lines
docker compose logs --tail=100 dagster
```

### Log Levels

Set via environment:

```yaml
services:
  dagster:
    environment:
      DAGSTER_LOG_LEVEL: DEBUG  # INFO, WARNING, ERROR
```

---

## Health Checks

Built-in health checks ensure services are ready:

```yaml
# MinIO
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
  interval: 5s

# Nessie
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:19120/api/v2/config"]
  interval: 10s
```

---

## Production Checklist

Before deploying to production:

- [ ] Change all default passwords
- [ ] Set appropriate resource profile
- [ ] Configure TLS/HTTPS (see [Security](security.md))
- [ ] Set up backups (see [Backup & Recovery](backup-recovery.md))
- [ ] Configure monitoring (see [Monitoring](monitoring.md))
- [ ] Review network access/firewall rules
