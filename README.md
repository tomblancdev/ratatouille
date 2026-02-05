# 🐀 Ratatouille

> *"Anyone Can Data!"*

A self-hostable, lightweight data platform for people who refuse to pay Snowflake prices.

## Quick Start

```bash
# Start the platform
make up

# Open the UIs
# Dagster:  http://localhost:3030
# Jupyter:  http://localhost:8889 (token: ratatouille)
# MinIO:    http://localhost:9001 (ratatouille/ratatouille123)
# Nessie:   http://localhost:19120
```

## Usage

### Python SDK

```python
from ratatouille import run, workspace, query, tools

# Load workspace
workspace("demo")

# Run pipelines (defined as SQL/Python files)
run("silver.sales")
run("gold.daily_kpis", full_refresh=True)

# Query data
df = query("SELECT * FROM silver.sales LIMIT 10")

# Explore
tools.tables()                    # List all tables
tools.schema("silver.sales")      # Get schema
tools.preview("gold.metrics")     # Preview data
```

### CLI

```bash
# Create a workspace
rat init my-workspace

# Run pipelines
rat run silver.sales
rat run silver.sales -f  # Full refresh

# Query data
rat query "SELECT * FROM silver.sales LIMIT 10"

# Run tests
rat test
```

## File-First Pipelines

Define pipelines as SQL files (like dbt):

```sql
-- pipelines/silver/sales.sql
SELECT
    date,
    product,
    quantity * price AS total
FROM {{ ref('bronze.sales') }}
WHERE quantity > 0
```

```yaml
# pipelines/silver/sales.yaml
name: sales
layer: silver
materialization: incremental
unique_key: [date, product]
```

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   BRONZE    │───▶│   SILVER    │───▶│    GOLD     │
│  (Raw Data) │    │ (Cleaned)   │    │ (Business)  │
└─────────────┘    └─────────────┘    └─────────────┘
```

**Stack:**
- **Storage**: Parquet + MinIO (S3-compatible)
- **Query**: DuckDB (blazing fast OLAP)
- **Catalog**: Nessie (Git-like versioning)
- **Orchestration**: Dagster
- **Containers**: Podman/Docker

## Development

```bash
make check    # Run all checks (lint, typecheck, test)
make test     # Run tests only
make lint     # Run linter
make format   # Format code
```

## Documentation

📚 Full documentation: [docs/README.md](docs/README.md)

- [Getting Started](docs/guide/getting-started.md)
- [SDK Reference](docs/reference/sdk.md)
- [CLI Reference](docs/reference/cli.md)

## Philosophy

Like Remy the rat proving that "anyone can cook", this project proves that **anyone can build enterprise-grade data pipelines** without enterprise budgets.

---

*"Not everyone can become a great data engineer, but a great data platform can come from anywhere."*
