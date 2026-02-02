# 🐀 Ratatouille User Guide

> *"Anyone Can Data!"* - From zero to production-ready pipelines

---

## 📋 Table of Contents

1. [Quick Start](#-quick-start)
2. [Understanding the Platform](#-understanding-the-platform)
3. [Creating a Workspace](#-creating-a-workspace)
4. [Creating Notebooks](#-creating-notebooks)
5. [Building Pipelines](#-building-pipelines)
6. [Running & Monitoring](#-running--monitoring)
7. [Querying Your Data](#-querying-your-data)
8. [Best Practices](#-best-practices)

---

## 🚀 Quick Start

### Start the Platform
```bash
make up
```

### Access the Services
| Service | URL | Credentials |
|---------|-----|-------------|
| **Dagster** (Pipelines) | http://localhost:3030 | - |
| **Jupyter** (Notebooks) | http://localhost:8889 | Token: `ratatouille` |
| **MinIO** (Storage) | http://localhost:9001 | `ratatouille` / `ratatouille123` |

### Run Sample Pipeline
1. Open Dagster UI → Assets → **Materialize all**
2. Open Jupyter → `01_getting_started.ipynb` → Run all cells

---

## 🏗️ Understanding the Platform

### Medallion Architecture
Your data flows through layers:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   LANDING   │───▶│   BRONZE    │───▶│   SILVER    │───▶  GOLD
│  (Raw CSV)  │    │(+ Metadata) │    │ (Cleaned)   │    (Aggregated)
└─────────────┘    └─────────────┘    └─────────────┘
```

| Layer | Purpose | Example |
|-------|---------|---------|
| **Landing** | Raw data as-is | CSV uploads, API responses |
| **Bronze** | Raw + metadata | Add `_ingested_at`, `_source` |
| **Silver** | Cleaned & typed | Remove nulls, fix types, dedupe |
| **Gold** | Business-ready | Aggregations, KPIs, reports |

### Storage (MinIO/S3)
Data is stored as Parquet files in S3 buckets:
- `s3://landing/` - Raw incoming data
- `s3://bronze/` - Ingested with metadata
- `s3://silver/` - Cleaned data
- `s3://gold/` - Business aggregations

---

## 📁 Creating a Workspace

Workspaces isolate projects. Each workspace has its own notebooks and pipelines.

### Step 1: Create Workspace Folder

```bash
# From the project root
mkdir -p workspaces/my_project/notebooks
mkdir -p workspaces/my_project/pipelines
```

Or structure it like this:
```
workspaces/
├── default/              # Sample workspace
│   └── notebooks/
│       └── 01_getting_started.ipynb
└── my_project/           # Your new workspace
    ├── notebooks/        # Jupyter notebooks
    │   └── exploration.ipynb
    └── pipelines/        # Pipeline definitions (optional)
```

### Step 2: Access in Jupyter

1. Open http://localhost:8889
2. Enter token: `ratatouille`
3. Navigate to `workspaces/my_project/notebooks/`
4. Click **New** → **Python 3** to create a notebook

---

## 📓 Creating Notebooks

### Step 1: Create a New Notebook

In Jupyter:
1. Navigate to your workspace folder
2. Click **New** → **Notebook** → **Python 3**
3. Rename it (click on "Untitled")

### Step 2: Connect to DuckDB + S3

Always start your notebook with this cell:

```python
# 🔌 Connect to the data platform
import sys
sys.path.insert(0, '/app/src')

from ratatouille.core import get_duckdb, s3_path

con = get_duckdb()
print("✅ Connected to DuckDB + S3!")
```

### Step 3: Explore Data

```python
# List files in a bucket
con.sql("SELECT * FROM glob('s3://gold/**/*.parquet')").df()
```

```python
# Query parquet files directly
con.sql("""
    SELECT *
    FROM read_parquet('s3://gold/pos/sales_by_product.parquet')
    ORDER BY total_revenue DESC
    LIMIT 10
""").df()
```

### Step 4: Write Data

```python
import pandas as pd
from ratatouille.core import write_parquet, s3_path

# Create a DataFrame
df = pd.DataFrame({
    'product': ['A', 'B', 'C'],
    'sales': [100, 200, 150]
})

# Write to S3
path = s3_path('gold', 'my_project', 'summary.parquet')
write_parquet(df, path, con)
print(f"✅ Written to {path}")
```

### Step 5: Close Connection

```python
con.close()
print("✅ Done!")
```

---

## 🔧 Building Pipelines

Pipelines transform data through the medallion layers using **Dagster assets**.

### Step 1: Create a Pipeline File

Create `src/ratatouille/pipelines/my_pipeline.py`:

```python
"""🐀 My Custom Pipeline."""

from dagster import asset, AssetExecutionContext
import pandas as pd
from ratatouille.core import get_duckdb, s3_path, write_parquet

# ============================================
# LANDING: Generate or Ingest Raw Data
# ============================================

@asset(
    group_name="my_project",
    compute_kind="python",
)
def landing_my_data(context: AssetExecutionContext) -> str:
    """Generate sample data for my project."""
    con = get_duckdb()

    # Create sample data (or fetch from API, read CSV, etc.)
    df = pd.DataFrame({
        'id': range(1, 101),
        'name': [f'Item {i}' for i in range(1, 101)],
        'value': [i * 10.5 for i in range(1, 101)],
    })

    # Write to landing
    path = s3_path('landing', 'my_project', 'raw_data.parquet')
    write_parquet(df, path, con)

    context.log.info(f"✅ Generated {len(df)} rows")
    con.close()
    return path


# ============================================
# BRONZE: Add Metadata
# ============================================

@asset(
    group_name="my_project",
    compute_kind="duckdb",
    deps=["landing_my_data"],  # Depends on landing
)
def bronze_my_data(context: AssetExecutionContext) -> str:
    """Ingest raw data with metadata."""
    con = get_duckdb()

    # Read from landing, add metadata
    df = con.sql("""
        SELECT
            *,
            CURRENT_TIMESTAMP as _ingested_at,
            'my_project' as _source
        FROM read_parquet('s3://landing/my_project/raw_data.parquet')
    """).df()

    # Write to bronze
    path = s3_path('bronze', 'my_project', 'data.parquet')
    write_parquet(df, path, con)

    context.log.info(f"✅ Ingested {len(df)} rows to Bronze")
    con.close()
    return path


# ============================================
# SILVER: Clean & Transform
# ============================================

@asset(
    group_name="my_project",
    compute_kind="duckdb",
    deps=["bronze_my_data"],
)
def silver_my_data(context: AssetExecutionContext) -> str:
    """Clean and transform data."""
    con = get_duckdb()

    df = con.sql("""
        SELECT
            id,
            TRIM(UPPER(name)) as name,  -- Standardize
            ROUND(value, 2) as value,
            _ingested_at
        FROM read_parquet('s3://bronze/my_project/data.parquet')
        WHERE value > 0  -- Filter invalid
    """).df()

    path = s3_path('silver', 'my_project', 'data.parquet')
    write_parquet(df, path, con)

    context.log.info(f"✅ Cleaned {len(df)} rows to Silver")
    con.close()
    return path


# ============================================
# GOLD: Business Aggregations
# ============================================

@asset(
    group_name="my_project",
    compute_kind="duckdb",
    deps=["silver_my_data"],
)
def gold_my_summary(context: AssetExecutionContext) -> str:
    """Create business summary."""
    con = get_duckdb()

    df = con.sql("""
        SELECT
            COUNT(*) as total_items,
            ROUND(SUM(value), 2) as total_value,
            ROUND(AVG(value), 2) as avg_value,
            MIN(value) as min_value,
            MAX(value) as max_value
        FROM read_parquet('s3://silver/my_project/data.parquet')
    """).df()

    path = s3_path('gold', 'my_project', 'summary.parquet')
    write_parquet(df, path, con)

    context.log.info(f"✅ Summary written to Gold")
    con.close()
    return path
```

### Step 2: Register the Pipeline

Edit `src/ratatouille/definitions.py`:

```python
"""🐀 Dagster Definitions - Ratatouille Data Platform."""

from dagster import Definitions, load_assets_from_modules

from ratatouille.pipelines import pos_sales, my_pipeline  # Add your pipeline

# Load all assets
pos_assets = load_assets_from_modules([pos_sales])
my_assets = load_assets_from_modules([my_pipeline])  # Add this

# Dagster Definitions
defs = Definitions(
    assets=[*pos_assets, *my_assets],  # Combine all
)

print("🐀 Ratatouille loaded!")
```

### Step 3: Restart Dagster

```bash
make down && make up
```

Or just restart the dagster container:
```bash
docker compose restart dagster
```

### Step 4: Run Your Pipeline

1. Open Dagster UI (http://localhost:3030)
2. Go to **Assets**
3. Find your assets (filter by `my_project` group)
4. Click **Materialize all** or select specific assets

---

## ▶️ Running & Monitoring

### From Dagster UI (Recommended)

1. **Assets View**: See all assets, their status, and lineage
2. **Materialize**: Click to run assets
3. **Runs**: Monitor execution, view logs
4. **Asset Graph**: Visual DAG of dependencies

### From Command Line

```bash
# Run all assets
make run

# Run specific assets
docker compose exec dagster dagster asset materialize \
    --select "landing_my_data" \
    --select "bronze_my_data"

# Run asset and all downstream
docker compose exec dagster dagster asset materialize \
    --select "landing_my_data*"
```

### View Logs

```bash
# All services
make logs

# Just Dagster
docker compose logs -f dagster
```

---

## 🔍 Querying Your Data

### In Jupyter Notebooks

```python
from ratatouille.core import get_duckdb
con = get_duckdb()

# Query any layer
df = con.sql("""
    SELECT * FROM read_parquet('s3://gold/my_project/summary.parquet')
""").df()

df
```

### Interactive DuckDB Shell

```bash
make query
```

Then in Python:
```python
con.sql("SELECT * FROM read_parquet('s3://gold/**/*.parquet')").df()
```

### In MinIO Console

1. Open http://localhost:9001
2. Login: `ratatouille` / `ratatouille123`
3. Browse buckets: `landing`, `bronze`, `silver`, `gold`
4. Download files to inspect locally

---

## ✨ Best Practices

### 📁 Naming Conventions

| Item | Convention | Example |
|------|------------|---------|
| Workspace | `snake_case` | `sales_analytics` |
| Pipeline file | `snake_case.py` | `customer_pipeline.py` |
| Asset name | `{layer}_{domain}_{entity}` | `silver_sales_transactions` |
| S3 path | `s3://{layer}/{domain}/{file}.parquet` | `s3://gold/sales/daily.parquet` |

### 🔄 Pipeline Design

1. **One asset per transformation** - Keep it simple
2. **Always specify `deps`** - Make dependencies explicit
3. **Use `group_name`** - Organize related assets
4. **Log row counts** - Track data volume
5. **Handle errors gracefully** - Log and re-raise

### 📊 Data Quality

Add asset checks to validate data:

```python
from dagster import asset_check, AssetCheckResult

@asset_check(asset=silver_my_data)
def check_no_nulls(context):
    con = get_duckdb()
    result = con.sql("""
        SELECT COUNT(*) as nulls
        FROM read_parquet('s3://silver/my_project/data.parquet')
        WHERE id IS NULL
    """).fetchone()[0]
    con.close()

    return AssetCheckResult(
        passed=result == 0,
        metadata={"null_count": result}
    )
```

### 🗂️ File Organization

```
workspaces/
└── my_project/
    ├── notebooks/
    │   ├── 01_exploration.ipynb    # Data exploration
    │   ├── 02_analysis.ipynb       # Deep dives
    │   └── 03_reporting.ipynb      # Final reports
    └── README.md                   # Project docs

src/ratatouille/pipelines/
├── pos_sales.py                    # POS demo pipeline
└── my_pipeline.py                  # Your pipeline
```

---

## 🆘 Troubleshooting

### "Connection refused" to MinIO
```bash
# Check MinIO is running
docker compose ps minio

# Restart if needed
docker compose restart minio
```

### "Asset not found" in Dagster
```bash
# Restart Dagster to reload definitions
docker compose restart dagster
```

### "Permission denied" writing to S3
```bash
# Check bucket exists
docker compose exec minio mc ls local/
```

### View detailed logs
```bash
docker compose logs -f dagster 2>&1 | grep -i error
```

---

## 🎓 Learning Path

1. ✅ **Start here**: Run the sample POS pipeline
2. ✅ **Explore**: Query data in Jupyter notebooks
3. 🔧 **Build**: Create your first custom pipeline
4. 📊 **Validate**: Add asset checks
5. 🚀 **Scale**: Add more data sources

---

## 📚 Resources

- [Dagster Docs](https://docs.dagster.io/) - Asset-based orchestration
- [DuckDB Docs](https://duckdb.org/docs/) - SQL analytics engine
- [MinIO Docs](https://min.io/docs/) - S3-compatible storage

---

*🐀 "In the end, anyone can data. But only those who dare to build, truly will."*
