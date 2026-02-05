# 📖 SDK Reference

Minimal SDK for file-first pipeline development.

---

## Quick Start

```python
from ratatouille import run, workspace, query

# Load workspace and run pipelines
workspace("analytics")
run("silver.sales")

# Quick queries
df = query("SELECT * FROM bronze.sales LIMIT 10")
```

---

## Core Functions

### `run(pipeline, full_refresh)`

Run a pipeline by name.

```python
from ratatouille import run

# Run a pipeline
run("silver.sales")

# Force full refresh (rebuild from scratch)
run("gold.daily_kpis", full_refresh=True)

# Pipeline names can use dot or slash notation
run("silver.sales")      # Same as below
run("silver/sales")      # Same as above
```

**Parameters:**
- `pipeline` (str): Pipeline name (e.g., `"silver.sales"` or `"silver/sales"`)
- `full_refresh` (bool): Force full refresh instead of incremental (default: `False`)

**Returns:** `dict` - Execution result with stats

---

### `workspace(name)`

Load or get current workspace.

```python
from ratatouille import workspace

# Load specific workspace
ws = workspace("analytics")

# Access workspace properties
print(ws.name)          # "analytics"
print(ws.nessie_branch) # Current Nessie branch

# Without argument, uses $RATATOUILLE_WORKSPACE or "default"
ws = workspace()
```

**Parameters:**
- `name` (str, optional): Workspace name. Defaults to `$RATATOUILLE_WORKSPACE` env var or `"default"`

**Returns:** `Workspace` instance

---

### `list_workspaces()`

List all available workspaces.

```python
from ratatouille import list_workspaces

workspaces = list_workspaces()
# ['default', 'analytics', 'demo']
```

**Returns:** `list[str]` - List of workspace names

---

### `query(sql)`

Execute SQL query using DuckDB (for notebooks/exploration).

```python
from ratatouille import query

# Simple query
df = query("SELECT * FROM bronze.sales LIMIT 10")

# Aggregations
df = query("""
    SELECT product, SUM(quantity) as total
    FROM silver.sales
    GROUP BY product
""")

# Show tables
df = query("SHOW TABLES")
```

**Parameters:**
- `sql` (str): SQL query string

**Returns:** `pd.DataFrame` - Query results

---

## Tools Module

For exploration and inspection, use the `tools` module:

```python
from ratatouille import tools

# Workspace info
tools.info()                      # Show workspace info

# List tables and files
tools.tables()                    # List all tables
tools.layers()                    # Show medallion layers

# Inspect tables
tools.schema("silver.sales")      # Get table schema
tools.preview("gold.metrics")     # Preview data (first rows)

# S3 operations
tools.ls("bronze/")               # List files in S3
tools.tree()                      # Show folder structure
tools.s3_uri("silver", "events")  # Get full S3 URI
```

See [Tools Reference](tools.md) for complete documentation.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RATATOUILLE_WORKSPACE` | `default` | Default workspace name |
| `RATATOUILLE_WORKSPACE_PATH` | - | Override workspace path |

---

## CLI Commands

The SDK functions have CLI equivalents:

| SDK | CLI |
|-----|-----|
| `run("silver.sales")` | `rat run silver.sales` |
| `run("silver.sales", full_refresh=True)` | `rat run silver.sales -f` |
| `query("SHOW TABLES")` | `rat query "SHOW TABLES"` |
| `workspace("demo")` | `rat run ... -w demo` |
| `list_workspaces()` | `rat list` |

---

## Migration from v1.x

If you're upgrading from the class-based SDK:

**Before (v1.x):**
```python
from ratatouille import rat

rat.workspace("analytics")
rat.run("silver.sales")
df = rat.query("SELECT * FROM ...")
```

**After (v2.x):**
```python
from ratatouille import run, workspace, query

workspace("analytics")
run("silver.sales")
df = query("SELECT * FROM ...")
```

**Removed functions:**
- `publish()`, `consume()`, `list_products()` - Data products not in file-first architecture
- `read()`, `write()` - Use `tools.preview()` or pipeline files
- `engine()`, `s3_path()`, `info()` - Use `tools` module
- `ws` property, `list_pipelines()`, `create_workspace()` - Use CLI commands
