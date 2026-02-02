# 🚀 Getting Started

Get Ratatouille running and build your first pipeline in minutes.

---

## Prerequisites

- **Docker** or **Podman** with Docker Compose
- **4GB+ RAM** available for containers
- **Ports available**: 3030, 8123, 8889, 9000, 9001

---

## 1. Start the Platform

```bash
cd ratatouille

# Start all services
make up

# Or manually:
docker compose up -d --build
```

Wait for all services to be healthy (~30 seconds on first run).

### Verify Services

```bash
make status
# or: docker compose ps
```

You should see:
```
ratatouille-clickhouse   running (healthy)
ratatouille-dagster      running
ratatouille-jupyter      running
ratatouille-minio        running (healthy)
ratatouille-minio-init   exited (0)  ← this is normal
```

---

## 2. Access the UIs

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dagster** | http://localhost:3030 | None |
| **Jupyter** | http://localhost:8889 | Token: `ratatouille` |
| **MinIO Console** | http://localhost:9001 | `ratatouille` / `ratatouille123` |
| **ClickHouse** | http://localhost:8123 | `ratatouille` / `ratatouille123` |

---

## 3. Your First Pipeline (Jupyter)

Open **Jupyter** at http://localhost:8889 and create a new notebook.

### Step 1: Import the SDK

```python
from ratatouille import rat

# Verify connection
print(rat.buckets())  # Should show: ['bronze', 'gold', 'landing', 'silver', 'warehouse']
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

# Write to landing zone
rat.write(df, "landing/tutorial/sales.parquet")
print("✅ Sample data created!")
```

### Step 3: Ingest to Bronze (Iceberg)

```python
# Ingest from landing to bronze layer
df_bronze, rows = rat.ice_ingest(
    "landing/tutorial/sales.parquet",
    "bronze.tutorial_sales"
)
print(f"✅ Ingested {rows} rows to bronze.tutorial_sales")

# Verify
print(rat.ice_all())  # Shows all Iceberg tables
```

### Step 4: Transform Bronze → Silver

**Option A: SQL**

```python
# Use SQL with {table} placeholders
result = rat.transform(
    sql="""
        SELECT
            date,
            product,
            quantity,
            price,
            quantity * price AS total,
            _source_file,
            _ingested_at
        FROM {bronze.tutorial_sales}
        WHERE quantity > 0
    """,
    target="silver.tutorial_sales",
    merge_keys=["date", "product"]  # Upsert keys
)

print(f"✅ Transformed: {result}")
```

**Option B: Ibis (Python)** - Same result, Python syntax!

```python
from ibis import _

# Python that compiles to ClickHouse SQL
(rat.t("bronze.tutorial_sales")
    .filter(_.quantity > 0)
    .mutate(total=_.quantity * _.price)
    .to_iceberg("silver.tutorial_sales", merge_keys=["date", "product"]))

print("✅ Transformed with Ibis!")
```

### Step 5: Read and Query

```python
# Read with placeholder syntax
df = rat.df("{silver.tutorial_sales}")
print(df)

# Or use SQL
df = rat.query("""
    SELECT
        product,
        SUM(quantity) as total_qty,
        SUM(total) as revenue
    FROM {silver.tutorial_sales}
    GROUP BY product
""")
print(df)
```

### Step 6: Materialize for BI

```python
# Create ClickHouse table for Power BI / Grafana
rat.materialize(
    "tutorial_sales",
    "silver/tutorial_sales",  # Iceberg location
    order_by="date"
)

# Query directly in ClickHouse
df = rat.query("SELECT * FROM tutorial_sales")
print(df)
```

---

## 4. Your First Pipeline (Dagster)

Now let's make this a proper, scheduled pipeline.

### Create Pipeline File

Create `workspaces/default/pipelines/tutorial_pipeline.py`:

```python
"""📚 Tutorial Pipeline - Bronze → Silver → Gold"""

from dagster import asset, AssetExecutionContext, MaterializeResult, MetadataValue
from ratatouille import rat


@asset(
    group_name="tutorial",
    description="Ingest sales data from landing zone",
    compute_kind="python",
)
def tutorial_bronze(context: AssetExecutionContext) -> MaterializeResult:
    """Ingest raw sales data to bronze layer."""

    df, rows = rat.ice_ingest(
        "landing/tutorial/sales.parquet",
        "bronze.tutorial_sales"
    )

    context.log.info(f"Ingested {rows} rows")

    return MaterializeResult(
        metadata={"rows": MetadataValue.int(rows)}
    )


@asset(
    group_name="tutorial",
    deps=[tutorial_bronze],
    description="Clean and calculate totals",
    compute_kind="sql",
)
def tutorial_silver(context: AssetExecutionContext) -> MaterializeResult:
    """Transform bronze to silver with calculations."""

    result = rat.transform(
        sql="""
            SELECT
                toDate(date) AS date,
                product,
                toInt32(quantity) AS quantity,
                toDecimal64(price, 2) AS price,
                toDecimal64(quantity * price, 2) AS total
            FROM {bronze.tutorial_sales}
            WHERE quantity > 0
        """,
        target="silver.tutorial_sales",
        merge_keys=["date", "product"]
    )

    return MaterializeResult(
        metadata={
            "inserted": MetadataValue.int(result.get("inserted", 0)),
            "updated": MetadataValue.int(result.get("updated", 0)),
        }
    )


@asset(
    group_name="tutorial",
    deps=[tutorial_silver],
    description="Daily revenue by product",
    compute_kind="sql",
)
def tutorial_gold(context: AssetExecutionContext) -> MaterializeResult:
    """Aggregate to gold layer."""

    result = rat.transform(
        sql="""
            SELECT
                product,
                SUM(quantity) AS total_quantity,
                SUM(total) AS revenue
            FROM {silver.tutorial_sales}
            GROUP BY product
        """,
        target="gold.tutorial_summary"
    )

    return MaterializeResult(
        metadata={"rows": MetadataValue.int(result.get("rows", 0))}
    )
```

### Restart Dagster

```bash
# Dagster auto-reloads, but you can force it:
docker compose restart dagster
```

### Run in Dagster UI

1. Open http://localhost:3030
2. Go to **Assets** → find `tutorial_bronze`, `tutorial_silver`, `tutorial_gold`
3. Click **Materialize all**
4. Watch the logs!

---

## 5. Useful Commands

### Makefile

```bash
make up        # Start platform
make down      # Stop platform
make logs      # Follow all logs
make status    # Show container status
make query     # Open ClickHouse shell
make clean     # Stop and remove all data
```

### SDK Quick Reference

```python
from ratatouille import rat
from ibis import _

# === Read ===
rat.df("{bronze.table}")           # Read Iceberg table
rat.query("SELECT * FROM ...")     # ClickHouse SQL
rat.read("bucket/path.parquet")    # Read Parquet from S3

# === Write (SQL) ===
rat.ice_ingest("landing/...", "bronze.table")  # File → Iceberg
rat.transform(sql, target, merge_keys)          # SQL → Iceberg
rat.write(df, "bucket/path.parquet")            # DataFrame → S3

# === Write (Ibis/Python) ===
(rat.t("bronze.sales")              # Python transforms
    .filter(_.amount > 0)
    .mutate(total=_.price * _.qty)
    .to_iceberg("silver.sales"))

# === Dev Mode (Branches) ===
rat.dev_start("feature/new")        # Create branch & enter dev mode
rat.dev_diff("silver.sales")        # Compare branch to main
rat.dev_merge()                     # Merge to main
rat.dev_drop()                      # Abandon changes

# === Explore ===
rat.ice_all()                       # All Iceberg tables
rat.buckets()                       # All S3 buckets
rat.ls("bucket/prefix/")            # List files

# === Iceberg ===
rat.ice_history("table")            # Snapshot history
rat.ice_time_travel("table", id)    # Read old version
rat.ice_drop("table")               # Delete table
```

---

## 6. Next Steps

✅ **You've built your first pipeline!**

- 📖 [SDK Reference](sdk-reference.md) - Full API documentation (SQL & Ibis)
- 🔬 [Dev Mode](dev-mode.md) - Isolated development with Iceberg branches
- 🏗️ [Architecture](architecture.md) - Understand the system
- 🔧 [Building Pipelines](pipelines.md) - Production patterns
- 🎯 [Operations](operations.md) - Monitoring & troubleshooting

---

## Troubleshooting

### Services won't start

```bash
# Check logs
docker compose logs -f

# Common issues:
# - Port already in use: stop other services or change ports in docker-compose.yml
# - Not enough memory: increase Docker memory limit
```

### Can't connect to services

```bash
# Make sure containers are healthy
make status

# Test ClickHouse
curl http://localhost:8123/ping

# Test MinIO
curl http://localhost:9000/minio/health/live
```

### SDK connection errors

```python
# Inside Jupyter, services are on internal network:
# - MinIO: minio:9000 (not localhost)
# - ClickHouse: clickhouse:8123

# The SDK handles this automatically via environment variables
```
