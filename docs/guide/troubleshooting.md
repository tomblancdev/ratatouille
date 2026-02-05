# 🔧 User Troubleshooting

Solutions for common pipeline and development issues.

---

## SDK Issues

### "Table not found"

```python
# Check if table exists
rat.ice_all()

# Verify namespace
rat.ice_tables("bronze")  # List bronze tables
```

**Common causes:**
- Table name typo
- Wrong namespace (bronze vs silver)
- Table hasn't been created yet

### "Connection refused"

```python
# Inside Jupyter/Dagster, use internal hostnames:
# - MinIO: minio:9000
# - Nessie: nessie:19120

# Check environment
import os
print(os.getenv("MINIO_ENDPOINT"))  # Should be http://minio:9000
```

### Transform Fails

```python
# Preview the SQL to debug
expanded = rat.transform_preview("SELECT * FROM {bronze.sales}")
print(expanded)

# Check placeholder syntax
# Correct: {namespace.table}
# Wrong: {namespace}.{table}
```

---

## Iceberg Issues

### "Catalog not available"

```python
# Check Nessie connection
# This should work inside containers:
import os
print(os.getenv("NESSIE_URI"))  # Should be http://nessie:19120/api/v2
```

### Time Travel Not Working

```python
# First, check history exists
history = rat.ice_history("bronze.sales")
print(history)

# Then use a valid snapshot_id from the history
df = rat.ice_time_travel("bronze.sales", snapshot_id=12345)
```

### Schema Evolution Errors

```python
# Check current schema
df = rat.ice_read("bronze.sales")
print(df.dtypes)

# If adding new columns, ensure they're nullable
# or provide defaults
```

---

## Pipeline Issues

### Asset Not Materializing

1. Check Dagster UI → Runs → View logs
2. Look for Python errors:
   ```bash
   docker compose logs dagster | grep -i error
   ```

### Duplicate Data After Re-run

**Use merge keys for idempotent pipelines:**

```python
# ✅ Good - idempotent
rat.transform(sql, target="silver.sales", merge_keys=["id", "date"])

# ❌ Bad - duplicates on re-run
rat.transform(sql, target="silver.sales", mode="append")
```

### File Already Ingested

```python
# Check ingestion history
history = rat.ingestion_history("bronze.sales")
print(history)

# Reset to allow re-ingestion
rat.reset_ingestion("bronze.sales")
```

---

## Transform Issues

### SQL Syntax Error

```python
# Test query separately
df = rat.query("""
    SELECT *
    FROM {bronze.sales}
    LIMIT 10
""")
```

**Common mistakes:**
- Missing `{namespace.table}` braces
- Using DuckDB syntax when ClickHouse is expected
- Column name typos

### Type Mismatch

```python
# Check source types
df = rat.df("{bronze.sales}")
print(df.dtypes)

# Cast in SQL if needed
rat.transform(
    sql="SELECT toInt32(quantity) AS quantity FROM {bronze.sales}",
    target="silver.sales"
)
```

### Ibis Expression Error

```python
from ibis import _

# Debug by viewing SQL
expr = rat.t("bronze.sales").filter(_.quantity > 0)
print(expr.sql())

# Common issue: using Python operators instead of Ibis
# Wrong: t.filter(t.quantity > 0 and t.price > 0)
# Right: t.filter((_.quantity > 0) & (_.price > 0))
```

---

## Dev Mode Issues

### Can't Create Branch

```python
# Check if table exists first
rat.ice_tables("bronze")

# Create branch
rat.dev_start("feature/new", tables=["bronze.sales"])
```

### Branch Changes Not Visible

```python
# Verify you're in dev mode
print(rat.dev_status())
# Should show: {"active": True, "branch": "feature/new"}

# Make sure you're reading the same table you branched
df = rat.df("{bronze.sales}")
```

### Merge Conflicts

Dev mode uses copy-on-write, so there shouldn't be conflicts. If you see issues:

```python
# Check branch differences
rat.dev_diff("bronze.sales")

# If needed, drop branch and start fresh
rat.dev_drop("feature/new")
```

---

## Jupyter Issues

### Kernel Dies

**Cause:** Usually memory - loading too much data.

**Solutions:**
1. Use sampling:
   ```python
   df = rat.query("SELECT * FROM {bronze.big_table} LIMIT 10000")
   ```

2. Use chunked processing:
   ```python
   # Process in batches instead of loading all at once
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

## Data Quality Issues

### Unexpected Nulls

```python
# Check null counts
report = rat.nulls(df)
print(report)

# Clean data
df_clean = rat.clean(df)
```

### Duplicate Records

```python
# Always use merge_keys for upsert behavior
rat.transform(
    sql="SELECT * FROM {bronze.sales}",
    target="silver.sales",
    merge_keys=["id"]  # Primary key for deduplication
)
```

### Type Coercion Issues

```python
# Clean DataFrame before writing
df = rat.clean(df)

# Or handle in SQL
rat.transform(
    sql="""
        SELECT
            CAST(id AS String) AS id,
            toDecimal64(price, 2) AS price
        FROM {bronze.sales}
    """,
    target="silver.sales"
)
```

---

## Getting Help

1. **Check logs:** Dagster UI → Runs → Click run → View stdout/stderr
2. **Debug SQL:** Use `rat.transform_preview()` to see expanded SQL
3. **Inspect data:** Use `rat.df()` to check intermediate results
4. **Read docs:** See [SDK Reference](../reference/sdk.md) for full API details
