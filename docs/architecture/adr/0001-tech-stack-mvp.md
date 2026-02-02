# ADR-0001: Technology Stack for MVP

## Status
**Proposed**

## Context

We need to choose technologies for the Ratatouille MVP that:
- Enable the "aha!" moment (notebook → pipeline → query)
- Are simple to deploy (single `docker compose up`)
- Work for 10-500 GB data scale
- Are self-hostable with no external dependencies

### Constraints
- 1 week timeline
- Single-node deployment (no distributed systems)
- Power user audience (technical, comfortable with code)

---

## Decision

### Storage Layer

| Component | Choice | Alternatives Considered |
|-----------|--------|------------------------|
| **File Format** | Parquet | CSV, JSON, Avro |
| **Storage Backend** | MinIO (S3-compatible) | Local filesystem |
| **Table Format** | Plain Parquet | Delta Lake, Iceberg |

**Rationale:**
- Parquet: Columnar, compressed, great for analytics, DuckDB native support
- MinIO: S3-compatible, self-hosted, production-ready from day 1
- Plain Parquet: Simpler than Delta/Iceberg for MVP, upgradeable later

---

### Query Engine

| Component | Choice | Alternatives Considered |
|-----------|--------|------------------------|
| **Query Engine** | DuckDB | ClickHouse, Polars, SQLite |

**Rationale:**
- **DuckDB wins because:**
  - Embedded (no separate server)
  - Blazing fast OLAP queries
  - Excellent Parquet support
  - ~50MB footprint
  - Great Python/Jupyter integration
  - Active development, growing ecosystem

- **Why not ClickHouse:** Overkill for MVP, requires separate server
- **Why not Polars:** No SQL interface, less familiar
- **Why not SQLite:** Not optimized for analytics

---

### Development Environment

| Component | Choice | Alternatives Considered |
|-----------|--------|------------------------|
| **Notebooks** | JupyterLab | VS Code, Marimo |
| **Language** | Python 3.11+ | - |
| **Package Manager** | pip + requirements.txt | Poetry, uv |

**Rationale:**
- JupyterLab: Industry standard, users know it
- Python: Best data ecosystem
- pip: Simple, no learning curve

---

### Containerization

| Component | Choice | Alternatives Considered |
|-----------|--------|------------------------|
| **Container Runtime** | Docker/Podman | - |
| **Composition** | docker-compose.yml | Kubernetes |
| **Base Image** | python:3.11-slim | Alpine, Debian |

**Rationale:**
- Docker Compose: Single file, simple, works with Podman too
- python:3.11-slim: Good balance of size and compatibility

---

### Orchestration

| Component | Choice | Alternatives Considered |
|-----------|--------|------------------------|
| **Pipeline Orchestration** | Dagster | Prefect, Airflow, None |

**Rationale:**
- **Dagster wins because:**
  - Asset-based (fits lakehouse model perfectly)
  - Great UI out of the box
  - Notebook support via dagstermill
  - Built-in data quality checks
  - Modern Python-native API
- **Why not Airflow:** Complex, overkill, DAG-based not asset-based
- **Why not Prefect:** Good but less mature asset model

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE STACK                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│   │   Dagster   │    │  Jupyter    │    │   MinIO     │    │
│   │   (UI+Orch) │    │  (Dev)      │    │   (S3)      │    │
│   │   :3000     │    │  :8888      │    │   :9000     │    │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    │
│          │                  │                  │            │
│          └──────────────────┼──────────────────┘            │
│                             │                               │
│                    ┌────────▼────────┐                      │
│                    │  Python + DuckDB │                      │
│                    │  (Query Engine)  │                      │
│                    └────────┬────────┘                      │
│                             │                               │
│                    ┌────────▼────────┐                      │
│                    │  S3 Buckets     │                      │
│                    │  bronze/silver/ │                      │
│                    │  gold (Parquet) │                      │
│                    └─────────────────┘                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Consequences

### Positive
- ✅ Production-ready from day 1 (S3, orchestration)
- ✅ Fast queries on medium data (DuckDB)
- ✅ Great UI (Dagster + Jupyter)
- ✅ Familiar tools (SQL, Parquet, S3)
- ✅ Asset-based pipelines fit lakehouse model

### Negative
- ❌ More containers to manage (3 services)
- ❌ Single-node only (can't scale horizontally yet)
- ❌ No real-time (batch only)

### Neutral
- S3 storage means data is easily portable
- Dagster adds learning curve but great DX
- Memory-bound for very large queries

---

## References

- [DuckDB Documentation](https://duckdb.org/docs/)
- [Parquet Format](https://parquet.apache.org/)
- [JupyterLab](https://jupyter.org/)
