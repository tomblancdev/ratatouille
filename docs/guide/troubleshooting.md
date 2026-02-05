# 🔧 User Troubleshooting

Solutions for common pipeline and development issues.

---

## SDK Issues

### "Table not found"

```python
from ratatouille import tools

# Check if table exists
tools.tables()

# Check specific layer
tools.tables("bronze")
tools.tables("silver")
```

**Common causes:**
- Table name typo
- Wrong namespace (bronze vs silver)
- Pipeline hasn't been run yet

### "Connection refused"

```python
# Inside Jupyter/Dagster, use internal hostnames:
# - MinIO: minio:9000

# Check workspace info
from ratatouille import tools
tools.info()
```

### Query Fails

```python
from ratatouille import query

# Test simple query first
df = query("SHOW TABLES")

# Then try your query
df = query("""
    SELECT *
    FROM bronze.sales
    LIMIT 10
""")
```

---

## Pipeline Issues

### Pipeline Not Running

1. Check if pipeline file exists:
   ```bash
   ls workspaces/*/pipelines/silver/
   ```

2. Verify YAML config:
   ```bash
   cat workspaces/demo/pipelines/silver/sales.yaml
   ```

3. Run with verbose output:
   ```bash
   rat run silver.sales -v
   ```

### Pipeline Fails

```python
from ratatouille import run

# Run and check result
result = run("silver.sales")
print(result)  # Shows error details
```

Or via CLI:

```bash
rat run silver.sales
# Check Dagster logs for detailed errors
```

### Full Refresh Needed

If incremental logic is broken, force a full refresh:

```python
from ratatouille import run
run("silver.sales", full_refresh=True)
```

```bash
rat run silver.sales -f
```

---

## SQL Pipeline Issues

### SQL Syntax Error

```sql
-- Check your SQL file for common issues:
-- 1. Missing {{ ref() }} for table references
-- 2. Using wrong SQL dialect
-- 3. Column name typos

-- Good:
SELECT * FROM {{ ref('bronze.sales') }}

-- Bad:
SELECT * FROM bronze.sales  -- Missing ref()
```

### Ref Not Found

```yaml
# Ensure the source table exists in pipeline config
# pipelines/silver/sales.yaml
sources:
  - bronze.sales  # This must exist
```

---

## Workspace Issues

### Workspace Not Found

```python
from ratatouille import list_workspaces, workspace

# List available workspaces
print(list_workspaces())

# Load a specific workspace
workspace("demo")
```

### Wrong Workspace

```python
from ratatouille import workspace, tools

# Check current workspace
tools.info()

# Switch workspace
workspace("analytics")
```

---

## Jupyter Issues

### Kernel Dies

**Cause:** Usually memory - loading too much data.

**Solutions:**
1. Use LIMIT in queries:
   ```python
   df = query("SELECT * FROM bronze.big_table LIMIT 10000")
   ```

2. Use preview for exploration:
   ```python
   from ratatouille import tools
   tools.preview("bronze.big_table", limit=100)
   ```

3. Increase Jupyter memory in docker-compose.yml

### Import Error

```python
# If ratatouille not found:
# Make sure you're in the Jupyter container, not local Python

# Check Python path
import sys
print(sys.path)  # Should include /app/src
```

### Notebook Not Saving

```bash
# Check Jupyter logs
docker compose logs jupyter

# Verify volume mount
docker compose exec jupyter ls -la /app/workspaces
```

---

## CLI Issues

### Command Not Found

```bash
# Ensure rat CLI is installed
pip install -e .

# Or run via container
docker compose exec app rat run silver.sales
```

### Wrong Workspace

```bash
# Specify workspace explicitly
rat run silver.sales -w demo
rat run silver.sales -w analytics
```

---

## Getting Help

1. **Check logs:** Dagster UI → Runs → Click run → View stdout/stderr
2. **List tables:** `tools.tables()` to see what's available
3. **Preview data:** `tools.preview("layer.table")` to check contents
4. **Read docs:** See [SDK Reference](../reference/sdk.md) for full API details
