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
- [Dev Mode](guide/dev-mode.md) - Iceberg branches
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

In Jupyter:

```python
from ratatouille import rat

# Ingest data
df, rows = rat.ice_ingest("landing/data.xlsx", "bronze.sales")

# Transform
rat.transform(
    sql="SELECT *, qty * price AS total FROM {bronze.sales}",
    target="silver.sales",
    merge_keys=["id"]
)

# Query
df = rat.df("{silver.sales}")
```

---

## Reference Documentation

| Reference | Description |
|-----------|-------------|
| [📖 SDK Reference](reference/sdk.md) | `rat.*` Python API |
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

- 🏠 **Medallion Lakehouse** - Bronze → Silver → Gold with Apache Iceberg
- ⚡ **Git-like Versioning** - Time travel, branches, and schema evolution
- 📊 **Orchestration** - Dagster for pipeline management
- 🔬 **Interactive Development** - Jupyter Lab with LSP
- 📦 **S3-Compatible Storage** - MinIO for object storage
- 🦭 **Container-First** - Docker/Podman, scales to Kubernetes

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Storage** | MinIO | S3-compatible object storage |
| **Lakehouse** | Apache Iceberg | Table format with ACID, time travel |
| **Catalog** | Nessie | Git-like versioning for Iceberg |
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
│   ├── sdk.py              # Main API (rat.*)
│   ├── triggers/           # Sensors, schedules
│   ├── testing/            # Test framework
│   └── docs/               # Doc generation
│
├── workspaces/             # User workspace area
│   └── demo/
│       └── pipelines/      # Your pipelines
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
4. **🎯 OLAP-Focused** - Optimized for analytics, not transactions

---

*"Not everyone can become a great data engineer, but a great data platform can come from anywhere."*
