# 📊 Resource Profiles

Predefined configurations for different VM sizes.

---

## Overview

| Profile | Target RAM | Use Case |
|---------|-----------|----------|
| `tiny` | 4GB | Raspberry Pi, minimal VMs |
| `small` | 20GB | Typical self-hosted (default) |
| `medium` | 64GB | Production workloads |
| `large` | 128GB+ | Large-scale processing |

---

## Usage

### Set via Environment

```bash
RAT_PROFILE=medium docker compose up -d
```

### Set via .env

```bash
# .env
RAT_PROFILE=medium
```

### Override in Workspace

```yaml
# workspace.yaml
resources:
  profile: small
  overrides:
    max_memory_mb: 8192
```

---

## Profile Details

### tiny.yaml (4GB RAM)

For Raspberry Pi, small VMs, testing:

```yaml
resources:
  # Container memory limits
  minio_memory: 512M
  nessie_memory: 256M
  nessie_max_heap: 128m
  dagster_memory: 1G
  jupyter_memory: 1G

  # Processing settings
  max_memory_mb: 512
  duckdb_memory_mb: 1024
  chunk_size_rows: 10000
  max_parallel_pipelines: 1
```

**Suitable for:**
- Testing and development
- Very small datasets (<5GB)
- Single-user environments

---

### small.yaml (20GB RAM)

Default profile for typical self-hosted setup:

```yaml
resources:
  # Container memory limits
  minio_memory: 1G
  nessie_memory: 768M
  nessie_max_heap: 512m
  dagster_memory: 2G
  jupyter_memory: 2G

  # Processing settings
  max_memory_mb: 4096
  duckdb_memory_mb: 8192
  chunk_size_rows: 50000
  max_parallel_pipelines: 2
```

**Suitable for:**
- Development environments
- Small to medium datasets (5-20GB)
- Small teams (1-5 users)

---

### medium.yaml (64GB RAM)

For production workloads:

```yaml
resources:
  # Container memory limits
  minio_memory: 2G
  nessie_memory: 1G
  nessie_max_heap: 768m
  dagster_memory: 4G
  jupyter_memory: 4G

  # Processing settings
  max_memory_mb: 16384
  duckdb_memory_mb: 32768
  chunk_size_rows: 200000
  max_parallel_pipelines: 4
```

**Suitable for:**
- Production environments
- Medium datasets (20-100GB)
- Medium teams (5-20 users)

---

### large.yaml (128GB+ RAM)

For large-scale processing:

```yaml
resources:
  # Container memory limits
  minio_memory: 4G
  nessie_memory: 2G
  nessie_max_heap: 1536m
  dagster_memory: 8G
  jupyter_memory: 8G

  # Processing settings
  max_memory_mb: 65536
  duckdb_memory_mb: 98304
  chunk_size_rows: 500000
  max_parallel_pipelines: 8
```

**Suitable for:**
- Heavy production workloads
- Large datasets (100GB+)
- Large teams (20+ users)

---

## Configuration Options

### Container Memory

| Setting | Description |
|---------|-------------|
| `minio_memory` | MinIO container limit |
| `nessie_memory` | Nessie container limit |
| `nessie_max_heap` | Nessie JVM heap size |
| `dagster_memory` | Dagster container limit |
| `jupyter_memory` | Jupyter container limit |

### Processing Settings

| Setting | Description |
|---------|-------------|
| `max_memory_mb` | Max memory per pipeline |
| `duckdb_memory_mb` | DuckDB memory allocation |
| `chunk_size_rows` | Rows per processing chunk |
| `max_parallel_pipelines` | Concurrent pipeline limit |

---

## Choosing a Profile

### Step 1: Check Available Memory

```bash
# Linux
free -h

# Docker
docker system info | grep Memory
```

### Step 2: Select Profile

| Available RAM | Recommended Profile |
|---------------|---------------------|
| <8GB | `tiny` |
| 8-32GB | `small` |
| 32-96GB | `medium` |
| >96GB | `large` |

### Step 3: Monitor and Adjust

```bash
# Watch container memory
docker stats

# If containers OOM, try smaller profile
RAT_PROFILE=tiny make up
```

---

## Custom Profiles

Create custom profile at `config/profiles/custom.yaml`:

```yaml
# config/profiles/custom.yaml
resources:
  minio_memory: 3G
  nessie_memory: 1G
  dagster_memory: 6G
  jupyter_memory: 4G

  max_memory_mb: 8192
  duckdb_memory_mb: 16384
  chunk_size_rows: 100000
  max_parallel_pipelines: 3
```

Use it:

```bash
RAT_PROFILE=custom make up
```

---

## Per-Workspace Overrides

Override profile settings in workspace config:

```yaml
# workspace.yaml
resources:
  profile: small  # Base profile

  # Selective overrides
  overrides:
    max_memory_mb: 8192          # Double the memory
    max_parallel_pipelines: 4    # More parallelism
```

---

## Troubleshooting

### Out of Memory

```bash
# Check which container is using most memory
docker stats --no-stream

# Try smaller profile
RAT_PROFILE=tiny make up
```

### Slow Processing

```bash
# Increase chunk size for faster processing (needs more memory)
# In workspace.yaml:
resources:
  overrides:
    chunk_size_rows: 200000
```

### Pipeline Timeouts

```bash
# Reduce parallelism to give each pipeline more resources
resources:
  overrides:
    max_parallel_pipelines: 1
```
