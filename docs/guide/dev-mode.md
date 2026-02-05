# Dev Mode - Development Branches

> **Note:** Dev mode with Iceberg branches has been replaced with a simpler file-first approach in v2.0.

## File-First Development

In the file-first architecture, development isolation is handled through:

1. **Workspaces** - Each project/team has its own workspace
2. **Git branches** - Pipeline code changes are version controlled
3. **Environment separation** - Dev vs prod workspaces

## Development Workflow

### 1. Create a Dev Workspace

```bash
# Create a new workspace for development
rat init my-feature-dev
cd my-feature-dev
```

### 2. Edit Pipeline Files

```sql
-- pipelines/silver/sales.sql
-- Make your changes here
SELECT
    date,
    product,
    quantity * price AS total,
    -- New field being developed
    discount_pct
FROM {{ ref('bronze.sales') }}
WHERE quantity > 0
```

### 3. Test Locally

```python
from ratatouille import run, query, workspace

# Use dev workspace
workspace("my-feature-dev")

# Run the pipeline
run("silver.sales")

# Check results
df = query("SELECT * FROM silver.sales LIMIT 10")
print(df)
```

### 4. Run Tests

```bash
rat test -w my-feature-dev
```

### 5. Commit and Deploy

```bash
# When ready, commit your changes
git add pipelines/silver/sales.sql
git commit -m "Add discount_pct to silver.sales"
git push

# Deploy to production workspace
# (via CI/CD or manual deployment)
```

## Environment Separation

### Using Environment Variables

```bash
# Development
RATATOUILLE_WORKSPACE=dev rat run silver.sales

# Production
RATATOUILLE_WORKSPACE=prod rat run silver.sales
```

### Using Workspace Configs

```yaml
# workspaces/dev/workspace.yaml
name: dev
s3_prefix: s3://dev-warehouse/

# workspaces/prod/workspace.yaml
name: prod
s3_prefix: s3://prod-warehouse/
```

## Comparing Results

```python
from ratatouille import workspace, query

# Query dev
workspace("dev")
dev_df = query("SELECT COUNT(*) as cnt FROM silver.sales")

# Query prod
workspace("prod")
prod_df = query("SELECT COUNT(*) as cnt FROM silver.sales")

# Compare
print(f"Dev: {dev_df['cnt'][0]}, Prod: {prod_df['cnt'][0]}")
```

## Best Practices

1. **Use separate workspaces** for dev, staging, and prod
2. **Version control** all pipeline files
3. **Run tests** before deploying to production
4. **Use CI/CD** for automated deployments

## Migration from v1.x

If you were using `rat.dev_start()`, `rat.dev_merge()`, etc., migrate to the workspace-based approach:

| Old (v1.x) | New (v2.x) |
|------------|------------|
| `rat.dev_start("feature/x")` | Create separate workspace |
| `rat.dev_merge()` | Git merge + deploy |
| `rat.dev_drop()` | Delete workspace |
| `rat.dev_diff("table")` | Compare queries across workspaces |
