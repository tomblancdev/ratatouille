# 📋 Workspace YAML Schema

Complete reference for `workspace.yaml` configuration.

---

## Basic Structure

```yaml
# workspace.yaml
name: my-workspace
version: "1.0"
description: "Workspace description"

isolation:
  nessie_branch: "workspace/my-workspace"
  s3_prefix: "my-workspace"

resources:
  profile: small
  overrides:
    max_memory_mb: 4096

layers:
  bronze:
    retention_days: 90
  silver:
    retention_days: 365
  gold:
    retention_days: null

products:
  - name: my_data_product
    source: gold.metrics

subscriptions:
  - product: other_product
    alias: metrics
```

---

## Root Fields

### name

Required. Workspace identifier.

```yaml
name: analytics
```

### version

Workspace configuration version.

```yaml
version: "1.0"
```

### description

Human-readable description.

```yaml
description: |
  Analytics team workspace for BI and reporting.

  Key pipelines:
  - daily_sales: Daily sales KPIs
  - customer_segments: Customer segmentation

  Contact: analytics-team@company.com
```

---

## Isolation

Workspace isolation settings:

```yaml
isolation:
  nessie_branch: "workspace/analytics"  # Catalog branch
  s3_prefix: "analytics"                 # S3 path prefix
```

| Field | Description |
|-------|-------------|
| `nessie_branch` | Dedicated Nessie catalog branch |
| `s3_prefix` | S3 path prefix for workspace data |

---

## Resources

Resource limits and profile selection:

```yaml
resources:
  profile: small  # Use predefined profile

  # Override specific settings
  overrides:
    max_memory_mb: 8192
    max_parallel_pipelines: 4
    chunk_size_rows: 100000
    duckdb_memory_mb: 4096
```

### Available Profiles

| Profile | RAM | Use Case |
|---------|-----|----------|
| `tiny` | 4GB | Raspberry Pi, minimal VMs |
| `small` | 20GB | Typical self-hosted (default) |
| `medium` | 64GB | Production workloads |
| `large` | 128GB+ | Large-scale processing |

### Override Options

| Option | Description |
|--------|-------------|
| `max_memory_mb` | Maximum memory per pipeline |
| `max_parallel_pipelines` | Concurrent pipeline limit |
| `chunk_size_rows` | Rows per processing chunk |
| `duckdb_memory_mb` | DuckDB memory allocation |

---

## Layers

Medallion layer settings:

```yaml
layers:
  bronze:
    retention_days: 90          # Auto-delete after 90 days
    partition_by: [_ingested_date]

  silver:
    retention_days: 365
    partition_by: [_date]

  gold:
    retention_days: null        # Keep forever
```

### Layer Options

| Option | Description |
|--------|-------------|
| `retention_days` | Days to keep data (`null` = forever) |
| `partition_by` | Default partition columns |

---

## Products

Data products published by this workspace:

```yaml
products:
  - name: daily_sales_kpis
    source: gold.daily_sales
    access:
      - workspace: "*"         # Everyone can read
        level: read
      - workspace: "finance"   # Finance can write
        level: write
    sla:
      freshness_hours: 24
```

### Product Fields

| Field | Description |
|-------|-------------|
| `name` | Product identifier |
| `source` | Source table (layer.table) |
| `access` | Access control rules |
| `sla` | Service level agreement |

### Access Levels

| Level | Permissions |
|-------|-------------|
| `read` | Query data, subscribe |
| `write` | Read + update metadata |
| `admin` | Write + manage access |

---

## Subscriptions

Data products consumed from other workspaces:

```yaml
subscriptions:
  - product: daily_sales_kpis
    alias: sales                # Available as products.sales
    version_constraint: "^1.0.0"

  - product: inventory_levels
    alias: inventory
    version_constraint: "latest"
```

### Subscription Fields

| Field | Description |
|-------|-------------|
| `product` | Product name to subscribe to |
| `alias` | Local alias for the product |
| `version_constraint` | Semver constraint |

### Version Constraints

| Constraint | Meaning |
|------------|---------|
| `latest` | Most recent version |
| `1.2.3` | Exact version |
| `^1.2.0` | Compatible (same major) |
| `~1.2.0` | Patch only (same minor) |
| `1.x` | Any 1.x version |
| `>=1.2.0` | At least this version |

---

## Full Example

```yaml
# workspace.yaml - Analytics Team

name: analytics
version: "1.0"
description: |
  Analytics team workspace for BI and reporting.

  Key pipelines:
  - daily_sales: Daily sales KPIs
  - customer_segments: Customer segmentation

  Contact: analytics-team@company.com

# Isolation settings
isolation:
  nessie_branch: "workspace/analytics"
  s3_prefix: "analytics"

# Resource limits
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
    partition_by: [_date]
  gold:
    retention_days: null

# Data products published
products:
  - name: daily_sales_kpis
    source: gold.daily_sales
    access:
      - workspace: "*"
        level: read
    sla:
      freshness_hours: 24

# Data products consumed
subscriptions:
  - product: company/inventory_levels
    alias: inventory
    version_constraint: "^1.0.0"
```
