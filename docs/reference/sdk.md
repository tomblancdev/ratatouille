# 📖 SDK Reference

Complete API reference for the Ratatouille SDK (`rat.*`).

---

## Quick Start

```python
from ratatouille import rat

# The `rat` object is your interface to everything
rat.df("{bronze.table}")      # Read data
rat.transform(sql, target)    # Transform data
rat.ice_all()                 # List tables
```

---

## Table of Contents

- [Reading Data](#reading-data)
- [Writing Data](#writing-data)
- [Iceberg Operations](#iceberg-operations)
- [Transform (SQL)](#transform-sql)
- [Transform (Ibis/Python)](#transform-ibispython)
- [Dev Mode (Branches)](#dev-mode-branches)
- [Temp Tables](#temp-tables)
- [S3 Operations](#s3-operations)
- [ClickHouse Operations](#clickhouse-operations)
- [Parsers](#parsers)
- [Data Quality](#data-quality)
- [File Tracking](#file-tracking)
- [Layer Management](#layer-management)
- [Raw Clients](#raw-clients)

---

## Reading Data

### `rat.df(table)`

Read an Iceberg or temp table using placeholder syntax.

```python
# Read Iceberg table
df = rat.df("{bronze.sales}")
df = rat.df("{silver.transactions}")
df = rat.df("{gold.summary}")

# Read temp table
df = rat.df("{temp.filtered}")
```

**Parameters:**
- `table` (str): Table reference like `"{namespace.table}"` or `"{temp.name}"`

**Returns:** `pd.DataFrame`

---

### `rat.query(sql)`

Execute SQL on ClickHouse with `{table}` placeholder expansion.

```python
# With placeholders (recommended)
df = rat.query("""
    SELECT product, SUM(qty) as total
    FROM {bronze.sales}
    GROUP BY product
""")

# Join tables
df = rat.query("""
    SELECT s.*, p.category
    FROM {silver.sales} s
    JOIN {silver.products} p ON s.product_id = p.id
""")

# Raw ClickHouse SQL
df = rat.query("SELECT version()")
```

**Parameters:**
- `sql` (str): SQL query. `{namespace.table}` placeholders are expanded to `s3()` functions.

**Returns:** `pd.DataFrame`

**Note:** Placeholders use the pattern `{word.word}` to avoid conflicts with regex like `\d{4}`.

---

### `rat.read(path, where, limit)`

Read Parquet files from S3 via ClickHouse.

```python
# Read single file
df = rat.read("gold/reports/summary.parquet")

# Read with filter
df = rat.read("silver/sales/*.parquet", where="total > 100", limit=1000)

# Full S3 path
df = rat.read("s3://bronze/raw/data.parquet")
```

**Parameters:**
- `path` (str): S3 path (with or without `s3://` prefix)
- `where` (str, optional): WHERE clause (without `WHERE` keyword)
- `limit` (int, optional): Row limit

**Returns:** `pd.DataFrame`

---

### `rat.ice_read(table)`

Read an Iceberg table directly (no SQL).

```python
df = rat.ice_read("bronze.transactions")
df = rat.ice_read("silver.sales")
```

**Parameters:**
- `table` (str): Table name like `"namespace.table"`

**Returns:** `pd.DataFrame`

---

## Writing Data

### `rat.write(df, path)`

Write DataFrame to S3 as Parquet.

```python
rat.write(df, "landing/processed/data.parquet")
rat.write(df, "s3://gold/reports/daily.parquet")
```

**Parameters:**
- `df` (DataFrame): Data to write
- `path` (str): S3 path

**Returns:** `str` - The full S3 path written to

---

### `rat.ice_ingest(source, table, ...)`

Ingest a file to an Iceberg table.

```python
# Basic ingest
df, rows = rat.ice_ingest(
    "landing/data.xlsx",
    "bronze.my_table"
)

# With parser
df, rows = rat.ice_ingest(
    "landing/example_report.xlsx",
    "bronze.sales",
    parser=my_parser
)

# Extract metadata from filename
df, rows = rat.ice_ingest(
    "landing/store_001_2024-01.xlsx",
    "bronze.sales",
    extract_from_filename=r"store_(?P<store_id>\d+)_(?P<period>\d{4}-\d{2})"
)
# Adds columns: store_id="001", period="2024-01"

# Specific Excel sheet
df, rows = rat.ice_ingest(
    "landing/multi_sheet.xlsx",
    "bronze.data",
    sheet="Sheet2"
)
```

**Parameters:**
- `source` (str): S3 path to source file
- `table` (str): Target Iceberg table
- `sheet` (str|int): Excel sheet name or index (default: 0)
- `mode` (str): `"append"` or `"overwrite"` (default: append)
- `extract_from_filename` (str): Regex with named groups
- `parser` (str|callable): Parser name or function

**Returns:** `tuple[DataFrame, int]` - (DataFrame, rows written)

**Auto-added columns:**
- `_source_file` - Original filename
- `_ingested_at` - Ingestion timestamp

---

### `rat.ice_ingest_batch(source_prefix, table, ...)`

Batch ingest multiple files.

```python
# Ingest all files from prefix
df, stats = rat.ice_ingest_batch(
    "landing/sales/",
    "bronze.sales"
)

# With parser and file tracking
df, stats = rat.ice_ingest_batch(
    "landing/sales/",
    "bronze.sales",
    parser=my_parser,
    skip_existing=True  # Production mode - skip already ingested
)

# Filter files
df, stats = rat.ice_ingest_batch(
    "landing/reports/",
    "bronze.reports",
    file_filter=r".*\.xlsx$"  # Only xlsx files
)
```

**Parameters:**
- `source_prefix` (str): S3 prefix to scan
- `table` (str): Target Iceberg table
- `sheet` (str|int): Excel sheet
- `extract_from_filename` (str): Regex pattern
- `file_filter` (str): Regex to filter files
- `parser` (str|callable): Parser
- `skip_existing` (bool): Skip files already in registry

**Returns:** `tuple[DataFrame, dict]` - (combined DataFrame, stats)

**Stats dict:**
```python
{
    "files": 5,            # Files successfully ingested
    "rows": 10000,         # Total rows
    "errors": 1,           # Failed files
    "skipped": [...],      # Error details
    "already_ingested": 2  # Skipped (skip_existing=True)
}
```

---

### `rat.ice_merge(df, table, merge_keys)`

Upsert data into an Iceberg table.

```python
stats = rat.ice_merge(
    df,
    "silver.transactions",
    merge_keys=["date", "store_id", "product_id"]
)
# stats = {"inserted": 100, "updated": 50}
```

**Parameters:**
- `df` (DataFrame): Data with new/updated records
- `table` (str): Target table
- `merge_keys` (list[str]): Columns forming unique key

**Returns:** `dict` with `inserted` and `updated` counts

---

## Iceberg Operations

### `rat.ice_tables(namespace)`

List tables in a namespace.

```python
tables = rat.ice_tables("bronze")  # ["sales", "products", ...]
tables = rat.ice_tables("silver")
tables = rat.ice_tables("gold")
```

---

### `rat.ice_namespaces()`

List all namespaces.

```python
namespaces = rat.ice_namespaces()  # ["bronze", "silver", "gold"]
```

---

### `rat.ice_all()`

List all tables organized by namespace.

```python
all_tables = rat.ice_all()
# {
#     "bronze": ["sales", "products"],
#     "silver": ["clean_sales"],
#     "gold": ["summary"]
# }
```

---

### `rat.ice_drop(table, purge)`

Drop an Iceberg table.

```python
rat.ice_drop("silver.old_table")
rat.ice_drop("bronze.temp", purge=True)  # Also delete S3 files
```

**Parameters:**
- `table` (str): Table to drop
- `purge` (bool): Also delete Parquet files (default: True)

---

### `rat.ice_history(table)`

Get snapshot history (time travel metadata).

```python
history = rat.ice_history("bronze.sales")
# DataFrame with: snapshot_id, timestamp, operation
```

---

### `rat.ice_time_travel(table, snapshot_id)`

Read table at a specific snapshot.

```python
# Get history
history = rat.ice_history("bronze.sales")

# Read old version
old_df = rat.ice_time_travel("bronze.sales", snapshot_id=12345678)
```

---

### `rat.ice_location(table)`

Get S3 location of table's data files.

```python
path = rat.ice_location("bronze.sales")
# "s3://warehouse/bronze/sales/data/*.parquet"
```

---

## Transform (SQL)

### `rat.transform(sql, target, merge_keys, mode)`

Transform data with ClickHouse SQL and write to Iceberg.

```python
# Overwrite (default)
result = rat.transform(
    sql="""
        SELECT
            product,
            SUM(quantity) as total_qty,
            SUM(price * quantity) as revenue
        FROM {bronze.sales}
        GROUP BY product
    """,
    target="gold.product_summary"
)

# Merge/upsert
result = rat.transform(
    sql="SELECT * FROM {bronze.raw} WHERE qty > 0",
    target="silver.clean",
    merge_keys=["id", "date"]
)

# Append
result = rat.transform(
    sql="SELECT * FROM {bronze.new_data}",
    target="silver.all_data",
    mode="append"
)

# Using temp tables
rat.temp("filtered", df)
result = rat.transform(
    sql="SELECT * FROM {temp.filtered} WHERE x > 100",
    target="silver.output"
)
```

**Parameters:**
- `sql` (str): SQL with `{namespace.table}` placeholders
- `target` (str): Target Iceberg table
- `merge_keys` (list[str], optional): Keys for upsert
- `mode` (str): `"overwrite"` (default) or `"append"`

**Returns:** `dict` with stats

---

### `rat.transform_preview(sql)`

Preview expanded SQL without executing.

```python
expanded = rat.transform_preview("SELECT * FROM {bronze.sales}")
print(expanded)
# SELECT * FROM s3('http://minio:9000/warehouse/bronze/sales/data/*.parquet', ...)
```

---

## Transform (Ibis/Python)

Write transforms in Python that compile to ClickHouse SQL. Same performance as raw SQL, but with Python linting and composability.

### `rat.t(table)`

Get an Ibis table expression for Pythonic transforms.

```python
from ibis import _

# Get table as Ibis expression
t = rat.t("bronze.sales")

# Filter, mutate, aggregate - all in Python
result = (
    t.filter(_.amount > 0)
    .mutate(total=_.price * _.qty)
    .group_by("store_id")
    .agg(
        revenue=_.total.sum(),
        items=_.qty.sum()
    )
)

# Execute and get DataFrame
df = result.execute()

# Or write directly to Iceberg
result.to_iceberg("gold.store_revenue")
```

**Parameters:**
- `table` (str): Table reference like `"bronze.sales"` or `"temp.clean"`

**Returns:** `IbisTable` - Enhanced Ibis expression with `.to_iceberg()` method

---

### `.to_iceberg(target, merge_keys, mode)`

Execute Ibis expression and write to Iceberg. Chainable from `rat.t()`.

```python
from ibis import _

# Full pipeline in one chain
(rat.t("bronze.transactions")
    .filter(_.qty > 0)
    .mutate(total=_.price * _.qty)
    .group_by("product_id")
    .agg(
        total_revenue=_.total.sum(),
        items_sold=_.qty.sum()
    )
    .to_iceberg("gold.product_summary", merge_keys=["product_id"]))
```

**Parameters:**
- `target` (str): Target Iceberg table
- `merge_keys` (list[str], optional): Keys for upsert
- `mode` (str): `"overwrite"` (default) or `"append"`

**Returns:** `dict` with stats

---

### `.sql()`

Get the generated ClickHouse SQL for debugging.

```python
expr = rat.t("bronze.sales").filter(_.amount > 100)
print(expr.sql())
# SELECT * FROM s3(...) WHERE amount > 100
```

---

### `.preview(n)`

Quick preview of first N rows.

```python
rat.t("bronze.sales").preview(5)
```

---

### `rat.ibis()`

Get the raw Ibis ClickHouse connection for advanced usage.

```python
con = rat.ibis()

# Use Ibis directly
t = con.table("my_clickhouse_table")
result = t.filter(t.x > 10).execute()
```

---

### SQL vs Ibis Comparison

| SQL | Ibis (Python) |
|-----|---------------|
| `SELECT * FROM {t} WHERE x > 0` | `rat.t("t").filter(_.x > 0)` |
| `SELECT a, SUM(b) FROM {t} GROUP BY a` | `rat.t("t").group_by("a").agg(total=_.b.sum())` |
| `SELECT *, a * b AS c FROM {t}` | `rat.t("t").mutate(c=_.a * _.b)` |
| `SELECT * FROM {t} ORDER BY x LIMIT 10` | `rat.t("t").order_by("x").limit(10)` |

**Benefits of Ibis:**
- ✅ Python linting for method names
- ✅ Composable/reusable transforms
- ✅ Type-safe operations
- ✅ IDE autocomplete for methods
- ✅ Same ClickHouse performance

---

## Dev Mode (Branches)

Develop and test pipeline changes in isolation using Iceberg branches. Zero data duplication (copy-on-write).

See [Dev Mode documentation](dev-mode.md) for full details.

### `rat.dev_start(branch, tables)`

Create a dev branch and enter dev mode.

```python
# Branch all tables
rat.dev_start("feature/new-cleaning")

# Branch specific tables
rat.dev_start("feature/fix", tables=["bronze.sales", "silver.sales"])
```

---

### `rat.dev_status()`

Check current dev mode status.

```python
rat.dev_status()
# {"active": True, "branch": "feature/new-cleaning"}
```

---

### `rat.dev_diff(table)`

Compare branch to main.

```python
rat.dev_diff("silver.sales")
# {"main_rows": 1000, "branch_rows": 1050, "diff": 50}
```

---

### `rat.dev_merge(branch)`

Merge dev branch to main.

```python
rat.dev_merge()  # Merge current branch
rat.dev_merge("feature/done")  # Merge specific branch
```

---

### `rat.dev_drop(branch)`

Drop branch without merging (abandon changes).

```python
rat.dev_drop()  # Drop current branch
rat.dev_drop("feature/abandoned")  # Drop specific branch
```

---

### `rat.dev_branches(table)`

List branches for a table or all tables.

```python
# All tables
rat.dev_branches()
# {"bronze.sales": [...], "silver.sales": [...]}

# Single table
rat.dev_branches("bronze.sales")
# [{"name": "main", ...}, {"name": "feature/x", ...}]
```

---

### `rat.dev_context(branch)`

Context manager for scoped dev mode.

```python
with rat.dev_context("experiment/test"):
    rat.transform(...)  # Uses branch
# Automatically exits dev mode
```

---

## Temp Tables

In-memory tables for multi-step transforms.

### `rat.temp(name, df)`

Save or retrieve a temp table.

```python
# Save
rat.temp("step1", df)

# Retrieve
df = rat.temp("step1")

# Use in transforms
rat.transform("SELECT * FROM {temp.step1} WHERE x > 10", target="silver.out")
```

---

### `rat.temp_list()`

List all temp tables.

```python
tables = rat.temp_list()
# {"step1": 1000, "filtered": 500}  # name: row_count
```

---

### `rat.temp_drop(name)`

Drop temp table(s).

```python
rat.temp_drop("step1")  # Drop one
rat.temp_drop()         # Drop all
```

---

## S3 Operations

### `rat.ls(path)`

List files in S3.

```python
files = rat.ls("landing/")
files = rat.ls("warehouse/bronze/sales/data/")
```

---

### `rat.buckets()`

List all S3 buckets.

```python
buckets = rat.buckets()
# ["bronze", "gold", "landing", "silver", "warehouse"]
```

---

### `rat.read_file(path)`

Read any file from S3.

```python
data, file_type = rat.read_file("landing/report.xlsx")
# data = BytesIO, file_type = "xlsx"

# Use with pandas
if file_type == "xlsx":
    df = pd.read_excel(data)
elif file_type == "csv":
    df = pd.read_csv(data)
```

---

### `rat.ingest(source, dest, sheet)`

Ingest file to S3 as Parquet (without Iceberg).

```python
df, path = rat.ingest("landing/data.xlsx", "bronze/reports/")
# Writes to: s3://bronze/reports/data.parquet
```

---

## ClickHouse Operations

### `rat.tables()`

List ClickHouse tables.

```python
tables = rat.tables()
# ["gold_sales", "gold_products", ...]
```

---

### `rat.materialize(table_name, path, order_by)`

Create ClickHouse table from S3 Parquet.

```python
rat.materialize(
    "gold_sales",
    "gold/reports/sales.parquet",
    order_by="date"
)

# Now query directly
df = rat.query("SELECT * FROM gold_sales WHERE date > '2024-01-01'")
```

**Parameters:**
- `table_name` (str): ClickHouse table name
- `path` (str): S3 path to Parquet
- `order_by` (str): ORDER BY clause (default: `"tuple()"`)

---

### `rat.describe(table_name)`

Get ClickHouse table schema.

```python
schema = rat.describe("gold_sales")
# DataFrame with column info
```

---

### `rat.drop(table_name)`

Drop ClickHouse table.

```python
rat.drop("old_table")
```

---

## Parsers

Handle messy file formats.

### `rat.parsers()`

List available parsers.

```python
parsers = rat.parsers()
# {"my_parser": "Custom format parser"}
```

---

### `rat.register_parser(name, func)`

Register a custom parser.

```python
def my_parser(data: BytesIO, filename: str) -> pd.DataFrame:
    """Custom parser for weird Excel format."""
    df = pd.read_excel(data, skiprows=10, header=[0, 1])
    # ... transform ...
    df["_source_file"] = filename
    df["_ingested_at"] = datetime.utcnow()
    return df

rat.register_parser("my_format", my_parser)

# Use it
rat.ice_ingest("landing/weird.xlsx", "bronze.data", parser="my_format")
```

**Parser function signature:**
```python
def parser(data: BytesIO, filename: str) -> pd.DataFrame:
    ...
```

---

## Data Quality

### `rat.nulls(df)`

Report null values.

```python
report = rat.nulls(df)
# {
#     "total_nulls": 150,
#     "total_cells": 10000,
#     "pct": 1.5,
#     "columns": {"price": 50, "name": 100}
# }
```

---

### `rat.clean(df)`

Clean DataFrame for storage.

```python
df = rat.clean(df)
```

Normalizes:
- String null representations (`"NaN"`, `"NA"`, etc.) → `None`
- Pandas nullable types → numpy types
- Timestamps → microsecond precision

---

## File Tracking

Production features for avoiding re-ingestion.

### `rat.ingestion_history(table)`

Get file ingestion history.

```python
# All history
history = rat.ingestion_history()

# For specific table
history = rat.ingestion_history("bronze.sales")
```

**Returns:** DataFrame with columns:
- `file_path`, `file_hash`, `target_table`, `rows_ingested`, `ingested_at`, `status`

---

### `rat.reset_ingestion(table)`

Reset tracking to allow re-ingestion.

```python
rat.reset_ingestion("bronze.sales")  # Reset one table
rat.reset_ingestion()                     # Reset all
```

---

## Layer Management

Medallion architecture helpers.

### `rat.layer(name)` / `rat.layers()`

```python
# Get current layer
current = rat.layer()  # "bronze"

# Set layer
rat.layer("silver")

# List all layers
layers = rat.layers()
# [
#     {"name": "bronze", "description": "Raw...", "current": False},
#     {"name": "silver", "description": "Cleaned...", "current": True},
#     {"name": "gold", "description": "Business...", "current": False},
# ]
```

### Shortcuts

```python
rat.use_bronze()   # Switch to bronze
rat.use_silver()   # Switch to silver
rat.use_gold()     # Switch to gold

# Workflow helpers
rat.workflow_ingest()     # → bronze
rat.workflow_transform()  # → silver
rat.workflow_publish()    # → gold
```

---

## Raw Clients

Direct access to underlying clients.

### `rat.clickhouse()`

```python
client = rat.clickhouse()
result = client.query("SELECT version()")
```

### `rat.s3()`

```python
s3 = rat.s3()
s3.download_file("landing", "data.xlsx", "/tmp/data.xlsx")
```

---

## Environment Variables

The SDK reads these from the environment:

| Variable | Default | Description |
|----------|---------|-------------|
| `S3_ENDPOINT` | `http://localhost:9000` | MinIO/S3 endpoint |
| `S3_ACCESS_KEY` | `ratatouille` | S3 access key |
| `S3_SECRET_KEY` | `ratatouille123` | S3 secret key |
| `CLICKHOUSE_HOST` | `localhost` | ClickHouse host |
| `CLICKHOUSE_PORT` | `8123` | ClickHouse HTTP port |
| `CLICKHOUSE_USER` | `ratatouille` | ClickHouse user |
| `CLICKHOUSE_PASSWORD` | `ratatouille123` | ClickHouse password |
| `ICEBERG_WAREHOUSE` | `s3://warehouse/` | Iceberg warehouse path |
| `ICEBERG_CATALOG_PATH` | `/app/workspaces/.iceberg` | SQLite catalog location |

Inside Docker containers, these are set automatically by `docker-compose.yml`.
