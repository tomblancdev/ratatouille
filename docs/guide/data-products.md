# 📦 Data Products Guide

Data Products enable **cross-workspace data sharing** with versioning, permissions, and SLA tracking.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRODUCT REGISTRY                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │ sales_kpis │  │ inventory  │  │ customers  │                │
│  │ v2.1.0     │  │ v1.0.0     │  │ v3.0.0     │                │
│  │ owner: ws-a│  │ owner: ws-b│  │ owner: ws-a│                │
│  └────────────┘  └────────────┘  └────────────┘                │
└─────────────────────────────────────────────────────────────────┘
         │                  │                   │
    publish ↑          publish ↑            publish ↑
    subscribe ↓        subscribe ↓          subscribe ↓
         │                  │                   │
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  Workspace A   │  │  Workspace B   │  │  Workspace C   │
│  (owner)       │  │  (owner)       │  │  (consumer)    │
└────────────────┘  └────────────────┘  └────────────────┘
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Product** | A versioned dataset published from a workspace |
| **Version** | Immutable snapshot with semver (1.0.0, 2.1.0) |
| **Publisher** | Workspace that owns and publishes the product |
| **Consumer** | Workspace that subscribes to the product |
| **Access Rule** | Permission controlling who can use the product |

## Publishing Products

### Via Code

```python
from ratatouille.workspace import Workspace
from ratatouille.products import publish_product

workspace = Workspace.load("analytics")

result = publish_product(
    workspace=workspace,
    product_name="sales_kpis",
    source_table="gold.daily_sales",
    version="1.0.0",
    description="Daily sales KPIs by store",
    tags=["sales", "kpi", "gold"],
    changelog="Initial release",
)

print(f"Published {result.product_name} v{result.version}")
print(f"Location: {result.s3_location}")
print(f"Rows: {result.row_count}")
```

### Via Workspace Config

Define products in `workspace.yaml`:

```yaml
# workspace.yaml
products:
  - name: daily_sales_kpis
    source: gold.daily_sales
    access:
      - workspace: "*"          # Everyone can read
        level: read
      - workspace: "finance"    # Finance can write
        level: write
    sla:
      freshness_hours: 24
```

Then publish all configured products:

```python
from ratatouille.products import publish_from_config

results = publish_from_config(workspace)
```

## Consuming Products

### Via Code

```python
from ratatouille.workspace import Workspace
from ratatouille.products import consume_product, query_product

workspace = Workspace.load("reporting")

# Option 1: Create a view
consume_product(
    workspace=workspace,
    product_name="sales_kpis",
    version_constraint="^1.0.0",
    local_alias="sales",
)

# Query via view
engine = workspace.get_engine()
df = engine.query("SELECT * FROM products.sales")

# Option 2: Query directly
df = query_product(
    workspace,
    "sales_kpis",
    query="SELECT sale_date, SUM(revenue) FROM product GROUP BY sale_date",
)
```

### Via Workspace Config

Define subscriptions in `workspace.yaml`:

```yaml
# workspace.yaml
subscriptions:
  - product: daily_sales_kpis
    alias: sales              # Available as products.sales
    version_constraint: "^1.0.0"

  - product: store_inventory
    alias: inventory
    version_constraint: "latest"
```

Then consume all subscriptions:

```python
from ratatouille.products import consume_from_config

results = consume_from_config(workspace)
```

### Using Products in Pipelines

Once subscribed, use products in your SQL pipelines:

```sql
-- pipelines/gold/exec_dashboard.sql

SELECT
    s.sale_date,
    s.total_revenue,
    i.stock_level
FROM products.sales s
LEFT JOIN products.inventory i ON s.store_id = i.store_id
```

## Version Constraints

Semver constraints control which versions are consumed:

| Constraint | Meaning | Example Match |
|------------|---------|---------------|
| `latest` | Most recent version | 2.3.1 |
| `1.2.3` | Exact version | 1.2.3 only |
| `^1.2.0` | Compatible (same major) | 1.2.0, 1.3.0, 1.9.9 |
| `~1.2.0` | Patch only (same minor) | 1.2.0, 1.2.1, 1.2.9 |
| `1.x` | Any 1.x version | 1.0.0, 1.5.2, 1.9.9 |
| `>=1.2.0` | At least this version | 1.2.0, 2.0.0, 3.0.0 |

### Examples

```yaml
subscriptions:
  # Always get latest (may have breaking changes)
  - product: experimental_data
    version_constraint: "latest"

  # Stay on 1.x (compatible updates only)
  - product: stable_api
    version_constraint: "^1.0.0"

  # Lock to exact version (maximum stability)
  - product: critical_data
    version_constraint: "2.1.0"
```

## Access Control

### Granting Access

```python
from ratatouille.products import PermissionManager

pm = PermissionManager()

# Grant read to everyone
pm.grant("sales_kpis", "*", "read")

# Grant read to team prefix
pm.grant("sales_kpis", "analytics-*", "read")

# Grant write to specific workspace
pm.grant("sales_kpis", "finance", "write")

# Grant admin (full control)
pm.grant("sales_kpis", "platform-admin", "admin")
```

### Access Levels

| Level | Permissions |
|-------|-------------|
| `read` | Query data, subscribe |
| `write` | Read + update product metadata |
| `admin` | Write + manage access rules |

### Pattern Matching

| Pattern | Matches |
|---------|---------|
| `*` | All workspaces |
| `analytics-*` | analytics-bi, analytics-reporting, etc. |
| `finance` | Only "finance" workspace |

### Checking Access

```python
pm = PermissionManager()

# Simple checks
if pm.can_read("analytics-bi", "sales_kpis"):
    print("Can read!")

if pm.can_write("finance", "sales_kpis"):
    print("Can write!")

# Detailed check
check = pm.check("analytics-bi", "sales_kpis", "read")
print(f"Granted: {check.granted}")
print(f"Matching rule: {check.matching_rule}")
print(f"Effective level: {check.effective_level}")
```

## Best Practices

### 1. Use Semantic Versioning

```
MAJOR.MINOR.PATCH

1.0.0 → Initial release
1.1.0 → New columns added (backwards compatible)
1.1.1 → Bug fix
2.0.0 → Breaking change (columns removed/renamed)
```

### 2. Document Changes

```python
publish_product(
    ...,
    version="1.1.0",
    changelog="Added store_region column for regional analysis",
)
```

### 3. Set SLAs

```yaml
products:
  - name: critical_metrics
    sla:
      freshness_hours: 1  # Alert if >1 hour stale
```

### 4. Use Appropriate Constraints

```yaml
# Development: Use latest for flexibility
subscriptions:
  - product: experimental
    version_constraint: "latest"

# Production: Lock to compatible versions
subscriptions:
  - product: production_data
    version_constraint: "^1.0.0"
```

### 5. Grant Minimal Access

Start with read-only, add write/admin as needed:

```python
# Default: Read for all
pm.grant("my_product", "*", "read")

# Specific teams get more access
pm.grant("my_product", "data-team", "admin")
```

## Troubleshooting

### "Permission Denied" Error

```python
# Check what access you have
pm = PermissionManager()
check = pm.check("my-workspace", "the-product", "read")
print(check.reason)

# List available products
from ratatouille.products import list_available_products
products = list_available_products(workspace)
```

### "Version Not Found" Error

```python
# List available versions
from ratatouille.products import ProductRegistry
registry = ProductRegistry()
versions = registry.list_versions("the-product")
for v in versions:
    print(f"{v.version} ({v.published_at})")
```

### Refresh Subscriptions

```python
# Re-resolve all version constraints
from ratatouille.products import refresh_subscriptions
refresh_subscriptions(workspace)
```
