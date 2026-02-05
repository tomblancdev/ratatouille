# 🐀 Ratatouille Documentation

> *"Anyone Can Data!"* - A self-hostable, lightweight data platform for people who refuse to pay Snowflake prices.

---

## Choose Your Path

<table>
<tr>
<td width="50%" valign="top">

### 🛠️ Platform Operators

*Setting up and running Ratatouille*

**[→ Deployment Guide](deploy/README.md)**

- [Quick Start](deploy/quick-start.md) - Get running in 5 minutes
- [Docker Setup](deploy/docker-compose.md) - Container configuration
- [Configuration](deploy/configuration.md) - Environment & profiles
- [Security](deploy/security.md) - Production hardening
- [Monitoring](deploy/monitoring.md) - Health & logs
- [Kubernetes](deploy/kubernetes.md) - K3s/K8s deployment

</td>
<td width="50%" valign="top">

### 📊 Data Engineers

*Building and managing pipelines*

**[→ User Guide](guide/README.md)**

- [Getting Started](guide/getting-started.md) - First pipeline tutorial
- [Workspaces](guide/workspaces.md) - Project organization
- [SQL Pipelines](guide/pipelines-sql.md) - dbt-style pipelines
- [Python Pipelines](guide/pipelines-python.md) - Dagster assets
- [Testing](guide/testing.md) - Quality checks

</td>
</tr>
</table>

---

## Quick Start

```bash
# Start the platform
make up

# Access the UIs
# Dagster:    http://localhost:3030
# Jupyter:    http://localhost:8889 (token: ratatouille)
# MinIO:      http://localhost:9001 (ratatouille/ratatouille123)
```

In Jupyter or your Python code:

```python
from ratatouille import run, workspace, query, tools

# Load workspace
workspace("demo")

# Run a pipeline (defined as SQL/Python files)
run("silver.sales")

# Query results
df = query("SELECT * FROM silver.sales LIMIT 10")

# Explore
tools.tables()           # List all tables
tools.preview("gold.metrics")  # Preview data
```

Or use the CLI:

```bash
# Run pipelines
rat run silver.sales

# Query data
rat query "SELECT * FROM silver.sales LIMIT 10"

# Run tests
rat test
```

---

## Reference Documentation

| Reference | Description |
|-----------|-------------|
| [📖 SDK Reference](reference/sdk.md) | Python API (`run`, `workspace`, `query`, `tools`) |
| [🖥️ CLI Reference](reference/cli.md) | Command-line interface |
| [🔧 Environment Variables](reference/environment-variables.md) | All configuration options |

---

## Architecture

| Document | Description |
|----------|-------------|
| [📐 Overview](architecture/overview.md) | System design |
| [📋 ADRs](architecture/README.md) | Decision records |

---

## What is Ratatouille?

A **self-hosted data platform** providing:

- 🏠 **Medallion Lakehouse** - Bronze → Silver → Gold with DuckDB + Parquet
- ⚡ **File-First Pipelines** - Define pipelines as SQL/Python files (like dbt)
- 📊 **Orchestration** - Dagster for pipeline management
- 🔬 **Interactive Development** - Jupyter Lab with LSP
- 📦 **S3-Compatible Storage** - MinIO for object storage
- 🦭 **Container-First** - Docker/Podman, scales to Kubernetes

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Storage** | MinIO | S3-compatible object storage |
| **Query Engine** | DuckDB | Fast OLAP analytics |
| **Format** | Parquet | Columnar storage |
| **Orchestration** | Dagster | Pipeline management & scheduling |
| **Development** | Jupyter Lab | Interactive notebooks |
| **SDK** | Python | Unified data operations API |

---

## Project Structure

```
ratatouille/
├── docker-compose.yml      # Platform services
├── Makefile                # make up/down/logs
├── Dockerfile              # App container
│
├── src/ratatouille/        # Core SDK
│   ├── sdk.py              # Main API (run, workspace, query)
│   ├── tools/              # Exploration tools
│   ├── pipeline/           # Pipeline execution
│   └── workspace/          # Workspace management
│
├── workspaces/             # User workspace area
│   └── demo/
│       └── pipelines/      # Your pipelines (SQL/Python)
│
└── docs/                   # This documentation
    ├── deploy/             # Operator docs
    ├── guide/              # User docs
    ├── reference/          # API reference
    └── architecture/       # Technical design
```

---

## Philosophy

**Why "Ratatouille"?**

Like Remy the rat proving that "anyone can cook", this project proves that **anyone can build enterprise-grade data pipelines** without enterprise budgets.

**Core Principles:**

1. **💸 Low Cost** - Run on a single machine, scale when needed
2. **🦭 Container-First** - Everything in Docker/Podman, nothing on host
3. **📦 Batteries Included** - SDK, UI, notebooks all pre-configured
4. **🎯 File-First** - Pipelines as code, version controlled

---

*"Not everyone can become a great data engineer, but a great data platform can come from anywhere."*
