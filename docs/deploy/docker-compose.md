# 🐳 Docker Compose Setup

Detailed configuration for running Ratatouille with Docker/Podman.

---

## Services Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network                           │
│                                                             │
│  ┌─────────────┐         ┌─────────────┐                   │
│  │   Dagster   │ ──────▶ │   Nessie    │                   │
│  │   :3000     │         │   :19120    │                   │
│  └──────┬──────┘         └──────┬──────┘                   │
│         │                       │                           │
│         │ S3 API                │ Catalog API               │
│         ▼                       ▼                           │
│  ┌─────────────────────────────────────┐                   │
│  │              MinIO                   │                   │
│  │              :9000                   │                   │
│  └─────────────────────────────────────┘                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
              │              │              │
              ▼              ▼              ▼
         localhost:     localhost:     localhost:
            3030         9000/9001       19120
          (Dagster)       (MinIO)       (Nessie)
```

---

## Service Details

### MinIO (S3 Storage)

| Setting | Value |
|---------|-------|
| S3 API | `http://localhost:9000` |
| Console | `http://localhost:9001` |
| Credentials | `ratatouille` / `ratatouille123` |
| Memory | 1GB (configurable) |

```yaml
minio:
  image: minio/minio:latest
  ports:
    - "9000:9000"   # S3 API
    - "9001:9001"   # Console
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER:-ratatouille}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-ratatouille123}
```

### Nessie (Iceberg Catalog)

| Setting | Value |
|---------|-------|
| API | `http://localhost:19120/api/v2` |
| Storage | RocksDB (persistent) |
| Memory | 768MB (configurable) |

```yaml
nessie:
  image: ghcr.io/projectnessie/nessie:latest
  ports:
    - "19120:19120"
  environment:
    NESSIE_VERSION_STORE_TYPE: ROCKSDB
```

### Dagster (Orchestration)

| Setting | Value |
|---------|-------|
| UI | `http://localhost:3030` |
| Memory | 2GB (configurable) |
| Workspace | Configurable via env |

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
docker compose restart nessie
```

---

## Volumes

Data is persisted in Docker volumes:

| Volume | Purpose |
|--------|---------|
| `minio_data` | S3 object storage |
| `nessie_data` | Iceberg catalog |
| `dagster_storage` | Dagster run storage |

### View Volumes

```bash
docker volume ls | grep ratatouille
```

### Remove Volumes (Data Loss!)

```bash
make clean
# or: docker compose down -v
```

---

## Port Customization

If default ports conflict with other services:

```yaml
# docker-compose.override.yml
services:
  dagster:
    ports:
      - "3031:3000"  # Use 3031 instead of 3030

  minio:
    ports:
      - "9002:9000"  # Use 9002 instead of 9000
```

---

## Resource Limits

Memory limits are configurable via environment variables:

```bash
# .env file
MINIO_MEMORY=2G
NESSIE_MEMORY=1G
DAGSTER_MEMORY=4G
```

Or use resource profiles:

```bash
RAT_PROFILE=medium docker compose up -d
```

---

## Next Steps

- ⚙️ **[Configuration](configuration.md)** - Environment variables and profiles
- 🔒 **[Security](security.md)** - Production hardening
- 📊 **[Monitoring](monitoring.md)** - Health checks and logs
