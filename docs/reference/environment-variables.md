# 🔧 Environment Variables

Complete reference for all environment variables.

---

## Quick Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ROOT_USER` | `ratatouille` | MinIO access key |
| `MINIO_ROOT_PASSWORD` | `ratatouille123` | MinIO secret key |
| `NESSIE_URI` | `http://nessie:19120/api/v2` | Nessie catalog URL |
| `ICEBERG_WAREHOUSE` | `s3://warehouse/` | Iceberg warehouse path |
| `RAT_PROFILE` | `small` | Resource profile |
| `RATATOUILLE_WORKSPACE` | `demo` | Default workspace |

---

## S3/MinIO

### Access Credentials

```bash
# Used by all services
MINIO_ROOT_USER=ratatouille
MINIO_ROOT_PASSWORD=ratatouille123

# SDK naming (same values)
S3_ACCESS_KEY=ratatouille
S3_SECRET_KEY=ratatouille123
```

### Endpoint

```bash
# Internal (container-to-container)
S3_ENDPOINT=http://minio:9000
MINIO_ENDPOINT=http://minio:9000

# External (from host machine)
S3_ENDPOINT=http://localhost:9000
```

### Memory Limit

```bash
MINIO_MEMORY=1G  # Default: 1GB
```

---

## Nessie (Iceberg Catalog)

### Connection

```bash
# API endpoint
NESSIE_URI=http://nessie:19120/api/v2

# Default branch
NESSIE_DEFAULT_BRANCH=main
```

### Memory Settings

```bash
NESSIE_MEMORY=768M      # Container limit
NESSIE_MAX_HEAP=512m    # Java heap size
```

---

## Iceberg

### Warehouse Location

```bash
ICEBERG_WAREHOUSE=s3://warehouse/
```

This is where all Iceberg table data is stored in MinIO.

---

## Workspace

### Configuration

```bash
# Default workspace name
RATATOUILLE_WORKSPACE=demo

# Workspaces directory
RATATOUILLE_WORKSPACES_DIR=/app/workspaces

# Explicit workspace path (overrides name)
RATATOUILLE_WORKSPACE_PATH=/app/workspaces/my-project
```

---

## Resource Profiles

### Profile Selection

```bash
RAT_PROFILE=small  # Options: tiny, small, medium, large
```

### Profile Descriptions

| Profile | RAM | Use Case |
|---------|-----|----------|
| `tiny` | 4GB | Raspberry Pi, minimal VMs |
| `small` | 20GB | Typical self-hosted (default) |
| `medium` | 64GB | Production workloads |
| `large` | 128GB+ | Large-scale processing |

### Service Memory Limits

```bash
# Set via profile or override individually
MINIO_MEMORY=1G
NESSIE_MEMORY=768M
DAGSTER_MEMORY=2G
```

---

## Dagster

### Configuration

```bash
# Storage location
DAGSTER_HOME=/app

# Memory limit
DAGSTER_MEMORY=2G
```

---

## Using .env Files

Create a `.env` file in your project root:

```bash
# .env
MINIO_ROOT_USER=myuser
MINIO_ROOT_PASSWORD=mysecretpassword
RAT_PROFILE=medium
```

Docker Compose automatically loads `.env` files.

---

## Profile-Specific Settings

### tiny.yaml (4GB RAM)

```bash
MINIO_MEMORY=512M
NESSIE_MEMORY=256M
NESSIE_MAX_HEAP=128m
DAGSTER_MEMORY=1G
```

### small.yaml (20GB RAM) - Default

```bash
MINIO_MEMORY=1G
NESSIE_MEMORY=768M
NESSIE_MAX_HEAP=512m
DAGSTER_MEMORY=2G
```

### medium.yaml (64GB RAM)

```bash
MINIO_MEMORY=2G
NESSIE_MEMORY=1G
NESSIE_MAX_HEAP=768m
DAGSTER_MEMORY=4G
```

### large.yaml (128GB+ RAM)

```bash
MINIO_MEMORY=4G
NESSIE_MEMORY=2G
NESSIE_MAX_HEAP=1536m
DAGSTER_MEMORY=8G
```

---

## SDK Environment Variables

These are read by the Python SDK inside containers:

```python
import os

# S3/MinIO
os.getenv("S3_ENDPOINT")      # http://minio:9000
os.getenv("S3_ACCESS_KEY")    # ratatouille
os.getenv("S3_SECRET_KEY")    # ratatouille123

# Nessie
os.getenv("NESSIE_URI")       # http://nessie:19120/api/v2

# Iceberg
os.getenv("ICEBERG_WAREHOUSE")  # s3://warehouse/

# Workspace
os.getenv("RATATOUILLE_WORKSPACE")  # demo
```

---

## Production Recommendations

### Security

```bash
# Change all default passwords!
MINIO_ROOT_USER=secure_user_name
MINIO_ROOT_PASSWORD=very_long_secure_password_here
```

### Resource Limits

```bash
# Match your VM resources
RAT_PROFILE=medium

# Or set explicitly
DAGSTER_MEMORY=8G
```

### External Access

```bash
# For production, consider:
# - Using real S3 instead of MinIO
# - Setting up TLS/HTTPS
# - Using secret management (Docker secrets, Vault)
```

---

## Debugging

### Check Current Values

```bash
# Inside container
docker compose exec dagster env | grep -E "(MINIO|NESSIE|S3|RAT)"

# Or in Python
from ratatouille import tools
tools.info()  # Shows workspace and environment info
```

### Override for Testing

```bash
# Temporary override
RATATOUILLE_WORKSPACE=test rat run silver.sales
```
