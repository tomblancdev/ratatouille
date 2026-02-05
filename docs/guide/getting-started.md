# 🚀 Getting Started

Build your first data pipeline in minutes.

> **Prerequisite:** Ratatouille platform must be running. See [Quick Start](../deploy/quick-start.md) for setup.

---

## Access the UIs

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dagster** | http://localhost:3030 | None |
| **Jupyter** | http://localhost:8889 | Token: `ratatouille` |
| **MinIO Console** | http://localhost:9001 | `ratatouille` / `ratatouille123` |

---

## Your First Pipeline (Jupyter)

Open **Jupyter** at http://localhost:8889 and create a new notebook.

### Step 1: Import the SDK

```python
from ratatouille import run, workspace, query, tools

# Check workspace info
tools.info()
```

### Step 2: Create Sample Data

```python
import pandas as pd

# Create sample sales data
df = pd.DataFrame({
    "date": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"],
    "product": ["Widget", "Gadget", "Widget", "Gadget"],
    "quantity": [10, 5, 15, 8],
    "price": [9.99, 19.99, 9.99, 19.99],
})

# Save to a file (pipelines read from files)
df.to_parquet("/app/workspaces/default/data/sample_sales.parquet")
print("✅ Sample data created!")
```

### Step 3: Create a Pipeline

Create a SQL pipeline file at `workspaces/default/pipelines/silver/sales.sql`:

```sql
-- silver/sales.sql
-- Transform raw sales data

SELECT
    date,
    product,
    quantity,
    price,
    quantity * price AS total
FROM bronze.sales
WHERE quantity > 0
```

And its config at `workspaces/default/pipelines/silver/sales.yaml`:

```yaml
name: sales
layer: silver
materialization: table
description: Cleaned sales with calculated totals
```

### Step 4: Run the Pipeline

```python
from ratatouille import run

# Run the pipeline
result = run("silver.sales")
print(f"✅ Pipeline completed: {result}")

# With full refresh
result = run("silver.sales", full_refresh=True)
```

### Step 5: Query the Results

```python
from ratatouille import query

# Query the transformed data
df = query("""
    SELECT
        product,
        SUM(quantity) as total_qty,
        SUM(total) as revenue
    FROM silver.sales
    GROUP BY product
""")
print(df)
```

---

## Your First Pipeline (CLI)

You can also run everything from the command line:

```bash
# Initialize a new workspace
rat init my-project
cd my-project

# Run a pipeline
rat run silver.sales

# Force full refresh
rat run silver.sales -f

# Execute ad-hoc queries
rat query "SELECT * FROM silver.sales LIMIT 10"

# Run tests
rat test
```

---

## SDK Quick Reference

```python
from ratatouille import run, workspace, query, tools

# === Core Functions ===
workspace("analytics")            # Load workspace
run("silver.sales")               # Run pipeline
run("gold.kpis", full_refresh=True)  # Full refresh
df = query("SELECT * FROM ...")   # Execute SQL

# === Exploration (tools) ===
tools.info()                      # Workspace info
tools.tables()                    # List all tables
tools.layers()                    # Show medallion layers
tools.schema("silver.sales")      # Table schema
tools.preview("gold.metrics")     # Preview data

# === S3 Operations (tools) ===
tools.ls("bronze/")               # List files
tools.tree()                      # Folder structure
tools.s3_uri("silver", "events")  # Get S3 URI
```

---

## File-First Architecture

Ratatouille follows a **file-first** approach like dbt:

```
workspaces/
└── my-workspace/
    ├── workspace.yaml           # Workspace config
    ├── pipelines/
    │   ├── bronze/              # Raw data ingestion
    │   │   └── sales.sql
    │   ├── silver/              # Cleaned/transformed
    │   │   └── sales.sql
    │   └── gold/                # Business-ready
    │       └── daily_kpis.sql
    └── tests/
        └── quality/             # Data quality tests
```

**Pipeline files** = SQL or Python + YAML config
**SDK** = Run pipelines, explore data
**CLI** = Same operations from terminal

---

## Next Steps

✅ **You've built your first pipeline!**

- 📖 **[SDK Reference](../reference/sdk.md)** - Full API documentation
- 🔧 **[SQL Pipelines](pipelines-sql.md)** - dbt-style SQL pipelines
- 🐍 **[Python Pipelines](pipelines-python.md)** - Complex transformations
- ✅ **[Testing](testing.md)** - Quality tests and validation
- 📂 **[Workspaces](workspaces.md)** - Organize projects

---

## Troubleshooting

### SDK connection errors

```python
# Inside containers, services use internal network names
# The SDK handles this via environment variables
# Check your workspace config:
tools.info()
```

### Can't find tables

```python
from ratatouille import tools

# List all tables
tools.tables()

# Check layers
tools.layers()
```

### Pipeline fails

```bash
# Check pipeline syntax and config
rat run silver.sales -v  # Verbose output

# Or from Python
from ratatouille import run
result = run("silver.sales")
print(result)  # Shows error details
```
