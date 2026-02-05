# 📈 Scaling

Scale Ratatouille from single node to cluster.

---

## Scaling Path

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: Single Node                                           │
│  docker compose up -d                                           │
│  • 1 VM, 20GB+ RAM                                              │
│  • All services co-located                                       │
│  • Great for development and small datasets                     │
├─────────────────────────────────────────────────────────────────┤
│  Phase 2: Vertical Scaling                                       │
│  RAT_PROFILE=medium                                             │
│  • Bigger VM, 64GB+ RAM                                         │
│  • Same architecture, more resources                             │
│  • Handles medium datasets (10-100GB)                           │
├─────────────────────────────────────────────────────────────────┤
│  Phase 3: K3s/Kubernetes                                         │
│  kubectl apply -f k8s/                                           │
│  • Multi-node cluster                                            │
│  • Service separation                                            │
│  • High availability                                             │
│  • Large datasets (100GB+)                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Vertical Scaling

### Resource Profiles

Use appropriate profile for your VM:

| Profile | RAM | Max Dataset | Use Case |
|---------|-----|-------------|----------|
| `tiny` | 4GB | <5GB | Testing only |
| `small` | 20GB | 5-20GB | Development |
| `medium` | 64GB | 20-100GB | Production |
| `large` | 128GB+ | 100GB+ | Heavy workloads |

```bash
# Switch profiles
RAT_PROFILE=medium docker compose up -d
```

### Increase Specific Services

```yaml
# docker-compose.override.yml
services:
  dagster:
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4'

  minio:
    deploy:
      resources:
        limits:
          memory: 4G
```

---

## Horizontal Scaling

### Worker Pods

Scale Dagster workers for parallel execution:

```yaml
# k8s/dagster-workers.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dagster-worker
spec:
  replicas: 3  # Scale workers
  template:
    spec:
      containers:
        - name: worker
          image: your-registry/ratatouille:latest
          command: ["dagster-daemon", "run"]
```

### MinIO Cluster

For distributed storage:

```bash
# Deploy MinIO in distributed mode
# Requires 4+ nodes for erasure coding

docker run -d \
  minio/minio server \
  http://minio{1...4}/data{1...4}
```

Or use MinIO Operator on Kubernetes:

```bash
kubectl apply -f https://github.com/minio/operator/releases/latest/download/minio-operator.yaml
```

---

## High Availability

### Multi-Node Setup

```
┌─────────────────────────────────────────────────────────────────┐
│                       Load Balancer                              │
│                      ┌──────────┐                                │
│                      │  Traefik │                                │
│                      └────┬─────┘                                │
│                           │                                      │
│         ┌─────────────────┼─────────────────┐                   │
│         │                 │                 │                    │
│         ▼                 ▼                 ▼                    │
│   ┌──────────┐      ┌──────────┐     ┌──────────┐              │
│   │  Node 1  │      │  Node 2  │     │  Node 3  │              │
│   │  MinIO   │      │  Dagster │     │  Jupyter │              │
│   │  Nessie  │      │  Workers │     │          │              │
│   └──────────┘      └──────────┘     └──────────┘              │
│         │                 │                 │                    │
│         └─────────────────┴─────────────────┘                   │
│                           │                                      │
│                    Shared Storage                                │
│                    (NFS or Cloud PV)                             │
└─────────────────────────────────────────────────────────────────┘
```

### Nessie HA

For catalog high availability:

```yaml
# Use external database instead of RocksDB
services:
  nessie:
    environment:
      NESSIE_VERSION_STORE_TYPE: JDBC
      QUARKUS_DATASOURCE_JDBC_URL: jdbc:postgresql://postgres:5432/nessie
```

---

## Storage Scaling

### Local to S3

When outgrowing local storage:

```bash
# Update environment
S3_ENDPOINT=https://s3.amazonaws.com
S3_ACCESS_KEY=your-aws-key
S3_SECRET_KEY=your-aws-secret
ICEBERG_WAREHOUSE=s3://your-bucket/warehouse/
```

### Object Store Options

| Option | Pros | Cons |
|--------|------|------|
| MinIO | Self-hosted, free | Manage yourself |
| AWS S3 | Managed, durable | Cost at scale |
| GCS | Fast, cheap egress | Google ecosystem |
| R2 | No egress fees | Newer service |

---

## Query Scaling

### Add ClickHouse

For faster analytics queries:

```yaml
# docker-compose.override.yml
services:
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    ports:
      - "8123:8123"
    volumes:
      - clickhouse_data:/var/lib/clickhouse
```

### ClickHouse Cluster

For massive query scale:

```yaml
# Deploy ClickHouse Keeper + shards
# See ClickHouse documentation for cluster setup
```

---

## Performance Tuning

### Chunk Size

Adjust for memory vs speed tradeoff:

```yaml
# workspace.yaml
resources:
  chunk_size_rows: 100000  # Smaller = less memory
  max_parallel_pipelines: 4  # More = faster
```

### DuckDB Memory

```yaml
resources:
  duckdb_memory_mb: 16384  # Max DuckDB memory
```

### Parquet File Optimization

For large tables, periodically optimize file sizes:

```bash
# Use DuckDB to rewrite and optimize Parquet files
rat query "COPY (SELECT * FROM bronze.sales) TO 's3://warehouse/bronze/sales/optimized.parquet'"
```

---

## Monitoring at Scale

### Resource Metrics

```bash
# Prometheus metrics
kubectl top pods -n ratatouille

# Container stats
docker stats
```

### Key Metrics to Watch

| Metric | Warning | Critical |
|--------|---------|----------|
| Memory usage | >70% | >90% |
| CPU usage | >80% | >95% |
| Disk usage | >70% | >85% |
| Query latency | >5s | >30s |

---

## Cost Optimization

### Right-size Resources

Don't over-provision:

```bash
# Start small, scale up
RAT_PROFILE=small  # Then monitor
RAT_PROFILE=medium  # If needed
```

### Spot/Preemptible Instances

For worker nodes:

```yaml
# k8s toleration for spot nodes
tolerations:
  - key: "cloud.google.com/gke-preemptible"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
```

### Data Lifecycle

Delete old data:

```yaml
# workspace.yaml
layers:
  bronze:
    retention_days: 30  # Auto-delete after 30 days
```

---

## Migration Checklist

Moving from single node to cluster:

- [ ] Export MinIO data to external storage
- [ ] Migrate Nessie catalog to external DB
- [ ] Update connection strings
- [ ] Deploy to Kubernetes
- [ ] Test all pipelines
- [ ] Update DNS/ingress
- [ ] Monitor for issues
