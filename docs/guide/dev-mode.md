# Dev Mode - Iceberg Branches

Dev mode provides git-like branching for your data, so you can develop and test pipeline changes in isolation without affecting production data.

## How It Works

Dev mode uses **native Iceberg branches** which means:

- **Zero data duplication** - Branches are metadata-only until you write
- **Copy-on-write** - Only modified data is duplicated
- **Fast-forward merge** - Merge is just a metadata update
- **Time travel still works** - Both branches have snapshot history

## Quick Start

### In Jupyter Notebooks

```python
from ratatouille import rat

# Start dev mode - all writes go to a branch
rat.dev_start("feature/new-cleaning")

# Work on your transforms
rat.transform(
    sql="SELECT * FROM {bronze.sales} WHERE amount > 0",
    target="silver.sales"
)

# Check what changed
rat.dev_diff("silver.sales")
# → {"main_rows": 1000, "branch_rows": 1050, "diff": 50}

# Happy with changes? Merge to main
rat.dev_merge()

# Or abandon changes
# rat.dev_drop()
```

### Using Context Manager

```python
with rat.dev_context("experiment/crazy-idea"):
    # Everything here uses the branch
    rat.transform(sql1, target="silver.sales")
    rat.transform(sql2, target="gold.summary")

    # Test it
    df = rat.df("{gold.summary}")
    assert len(df) > 0

# Outside context: back to main
# Branch still exists, can merge later
rat.dev_merge("experiment/crazy-idea")
```

### Using Makefile

```bash
# Start dev session
make dev BRANCH=feature/fix-nulls

# Merge when ready
make dev-merge BRANCH=feature/fix-nulls

# Or drop it
make dev-drop BRANCH=feature/fix-nulls

# Check status
make dev-status
make dev-branches
```

## API Reference

### `rat.dev(branch_name)`

Enter or exit dev mode.

```python
rat.dev("feature/new")  # Enter dev mode
rat.dev(None)           # Exit dev mode
```

### `rat.dev_start(branch_name, tables=None)`

Create a new branch on specified tables and enter dev mode.

```python
# Branch all tables
rat.dev_start("feature/new")

# Branch specific tables
rat.dev_start("feature/new", tables=["bronze.sales", "silver.sales"])
```

### `rat.dev_status()`

Get current dev mode status.

```python
rat.dev_status()
# → {"active": True, "branch": "feature/new"}
```

### `rat.dev_merge(branch_name=None)`

Merge branch to main. Fast-forward merge (metadata-only).

```python
rat.dev_merge()              # Merge current branch
rat.dev_merge("feature/x")   # Merge specific branch
```

### `rat.dev_drop(branch_name=None)`

Drop a branch without merging.

```python
rat.dev_drop()               # Drop current branch
rat.dev_drop("feature/x")    # Drop specific branch
```

### `rat.dev_diff(table, branch_name=None)`

Compare branch to main.

```python
rat.dev_diff("silver.sales")
# → {"main_rows": 1000, "branch_rows": 1050, "diff": 50}
```

### `rat.dev_branches(table=None)`

List branches for tables.

```python
# All tables
rat.dev_branches()
# → {"bronze.sales": [...], "silver.sales": [...]}

# Single table
rat.dev_branches("bronze.sales")
# → [{"name": "main", "type": "branch"}, ...]
```

### `rat.dev_context(branch_name)`

Context manager for dev mode.

```python
with rat.dev_context("feature/test"):
    rat.transform(...)  # Uses branch
# Back to previous state
```

## Workflow Examples

### 1. Feature Development

```python
# Start feature branch
rat.dev_start("feature/new-cleaning")

# Develop your transforms
rat.transform(
    sql="SELECT *, COALESCE(amount, 0) as amount FROM {bronze.sales}",
    target="silver.sales"
)

# Test the results
df = rat.df("{silver.sales}")
assert df["amount"].isna().sum() == 0

# Merge to production
rat.dev_merge()
```

### 2. Safe Experiments

```python
# Try something risky
rat.dev_start("experiment/aggressive-dedup")

# Make aggressive changes
rat.transform(
    sql="SELECT DISTINCT * FROM {bronze.sales}",
    target="bronze.sales",
    mode="overwrite"
)

# Oops, that was too aggressive
rat.dev_drop()

# Main is unaffected!
df = rat.ice_read("bronze.sales")  # Original data still there
```

### 3. A/B Testing Transforms

```python
# Version A
with rat.dev_context("experiment/version-a"):
    rat.transform(sql_version_a, target="gold.metrics")
    metrics_a = rat.df("{gold.metrics}")

# Version B
with rat.dev_context("experiment/version-b"):
    rat.transform(sql_version_b, target="gold.metrics")
    metrics_b = rat.df("{gold.metrics}")

# Compare and pick winner
if metrics_a["accuracy"].mean() > metrics_b["accuracy"].mean():
    rat.dev_merge("experiment/version-a")
    rat.dev_drop("experiment/version-b")
else:
    rat.dev_merge("experiment/version-b")
    rat.dev_drop("experiment/version-a")
```

## Notes

- Branches are per-table, not global
- Reading from a branch falls back to main if data doesn't exist on branch
- Multiple developers can work on different branches simultaneously
- Branch names can use `/` for organization (e.g., `feature/x`, `experiment/y`)
