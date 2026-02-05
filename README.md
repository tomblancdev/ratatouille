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

## Create a Workspace

```bash
# Using the CLI
pip install -e .
rat init my-workspace

# Or use an existing workspace
cd workspaces/demo
code .  # Open in VS Code, then "Reopen in Container"
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

## Philosophy

Like Remy the rat proving that "anyone can cook", this project proves that **anyone can build enterprise-grade data pipelines** without enterprise budgets.

---

*"Not everyone can become a great data engineer, but a great data platform can come from anywhere."*
