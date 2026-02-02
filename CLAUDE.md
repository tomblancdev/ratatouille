# 🐀 Ratatouille - "Anyone Can Data!"

> *A self-hostable, lightweight data platform for people who refuse to pay Snowflake prices.*

## 🎯 Project Philosophy

Like Remy the rat proving that "anyone can cook", this project proves that **anyone can build enterprise-grade data pipelines** without enterprise budgets. We take the power from expensive cloud platforms and give it to self-hosters.

**Core Principles:**
- 💸 Low cost, low resources
- 🦭 Podman-first (rootless, daemonless, K8s-compatible)
- 📦 Start single-node, scale to cluster seamlessly
- 🎯 OLAP-focused with transaction capabilities

---

## 🏗️ Architecture Overview

### Medallion Lakehouse Architecture
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   BRONZE    │───▶│   SILVER    │───▶│    GOLD     │
│  (Raw Data) │    │ (Cleaned)   │    │ (Business)  │
└─────────────┘    └─────────────┘    └─────────────┘
     ▲                                       │
     │                                       ▼
┌─────────────┐                      ┌─────────────┐
│  INGESTION  │                      │  REST API   │
│   Sources   │                      │  + Jobs UI  │
└─────────────┘                      └─────────────┘
```

### Data Parallelism with Podman Pods
```
┌─────────────────── Pod: ratatouille-workers ───────────────────┐
│  ┌────────────┐  ┌────────────┐  ┌────────────┐               │
│  │  Worker 1  │  │  Worker 2  │  │  Worker N  │   Parallel    │
│  │ Partition A│  │ Partition B│  │ Partition N│   Processing  │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘               │
│        └───────────────┼───────────────┘                       │
│               Shared Volume (Parquet/MinIO)                    │
└────────────────────────────────────────────────────────────────┘
         │
         │ Same YAML
         ▼
┌─────────────────── K3s Cluster (Scale Out) ───────────────────┐
│   Node 1          Node 2          Node 3                       │
│  ┌────────┐      ┌────────┐      ┌────────┐                   │
│  │Workers │      │Workers │      │Workers │                   │
│  └────────┘      └────────┘      └────────┘                   │
└────────────────────────────────────────────────────────────────┘
```

**Key Insight**: Podman pod specs are K8s-compatible! Dev locally → Deploy to K3s with zero rewrite.

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **Storage** | Parquet + MinIO | S3-compatible, cloud-ready |
| **Query Engine** | DuckDB | Blazing OLAP, ~50MB, multi-threaded |
| **API** | FastAPI | Async, swappable if needed |
| **Jobs/Queue** | TBD (Redis + RQ / Dramatiq) | Lightweight task distribution |
| **Containers** | Podman (Docker-compatible) | Rootless, daemonless, K8s-ready |
| **Orchestration** | Podman → K3s | Same specs, seamless scale-out |

---

## 📊 Target Specs

- **Volume**: 10-500GB (medium scale)
- **Sources**: Mixed (APIs, CDC, Files)
- **Query Pattern**: OLAP-focused (analytics, aggregations)
- **Parallelism**: Multi-container pods on single machine
- **Scale Path**: Single node → K3s cluster

---

## 🧑‍💻 Development Guidelines

### Podman First (Docker-Compatible)
- **NEVER install services directly on the host machine**
- All services run in Podman containers/pods
- Use standard `Dockerfile` and `docker-compose.yml` (Podman-compatible)
- Run with `podman compose` or `podman play kube`

### Code Style
- Python 3.11+ with type hints
- Async-first where beneficial
- Minimal dependencies (resource-conscious!)
- Type everything, test everything

### Data Conventions
| Layer | Purpose | Partitioning | Format |
|-------|---------|--------------|--------|
| Bronze | Raw, immutable | Ingestion date | Parquet |
| Silver | Cleaned, deduplicated | Source + date | Parquet |
| Gold | Business-ready | Business keys | Parquet |

### API Design
- REST endpoints for queries and job management
- Simple, extensible (GraphQL later if needed)
- OpenAPI/Swagger documentation
- Health checks for orchestration

---

## 📁 Project Structure

```
ratatouille/
├── k8s/                        # Pod/K8s YAML definitions
│   ├── ratatouille-api.yaml
│   ├── ratatouille-workers.yaml
│   └── ratatouille-storage.yaml
├── src/
│   ├── ingestion/              # Data source connectors
│   │   ├── api_sources/
│   │   ├── file_sources/
│   │   └── cdc_sources/
│   ├── transforms/             # Bronze → Silver → Gold
│   ├── api/                    # FastAPI application
│   ├── workers/                # Parallel job workers
│   └── core/                   # Shared utilities, DuckDB wrapper
├── data/                       # Local data (gitignored)
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── tests/
├── docs/
├── Dockerfile                  # Container build (Podman-compatible)
└── docker-compose.yml          # Local dev stack (Podman-compatible)
```

---

## 🚀 Roadmap

### Phase 1: Foundation (Current)
- [ ] Basic project structure
- [ ] DuckDB + Parquet medallion layers
- [ ] Simple REST API
- [ ] Single worker pod

### Phase 2: Parallelism
- [ ] Multi-worker pod setup
- [ ] Job queue (Redis + workers)
- [ ] Partition-aware processing

### Phase 3: Scale Out
- [ ] K3s deployment manifests
- [ ] MinIO for distributed storage
- [ ] Multi-node testing

### Phase 4: Polish
- [ ] Web UI for job management
- [ ] Data exploration interface
- [ ] CDC connectors
- [ ] dbt integration

---

## ⚠️ Non-Goals (For Now)

- Real-time streaming (batch-first)
- Multi-tenant SaaS features
- Complex RBAC (simple auth first)
- Vendor lock-in

---

## 🐀 The Ratatouille Promise

*"Not everyone can become a great data engineer, but a great data platform can come from anywhere."*

This project exists because:
- Snowflake costs too much 💸
- Databricks costs too much 💸
- But you still deserve great data infrastructure 🎯

---

*"In many ways, the work of a data engineer is easy. We risk very little, yet enjoy a position over those who offer up their data and infrastructure to our judgment. But the bitter truth we data engineers must face is that in the grand scheme of things, the average piece of Parquet is probably more meaningful than our criticism designating it."*

— Anton Ego, probably 🍷
