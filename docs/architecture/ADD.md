# 🐀 Ratatouille - Architecture Design Document

> **Status:** Draft
> **Last Updated:** 2026-01-29

---

## 1. Overview

### 1.1 Vision
*"Anyone Can Data!"* - A self-hostable, all-in-one data platform for people who refuse to pay Snowflake prices.

### 1.2 Mission
Provide a complete data platform in a single, easy-to-deploy package that handles storage, pipelines, querying, and visualization.

### 1.3 Target Users

| Persona | Description | Needs |
|---------|-------------|-------|
| **Homelab Hero** | Self-hoster, privacy-focused, technical | Full control, no vendor lock-in, runs on own hardware |
| **SMB Data Lead** | 10-50 person company, growing pains | Outgrew spreadsheets, needs structure, limited budget |

### 1.4 Design Principles

1. **All-in-One** - One platform, not 10 tools glued together
2. **Self-Hosted First** - Your data, your servers, your control
3. **Simple to Start** - 5 minutes from zero to working pipeline
4. **Scale When Needed** - Single node → cluster without rewrite

---

## 2. Requirements

### 2.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | Ingest data from APIs, databases, files | Must |
| F2 | Transform data (ETL pipelines) | Must |
| F3 | Store data in queryable format | Must |
| F4 | Query data via SQL | Must |
| F5 | Expose data via API | Must |
| F6 | Web UI for management | Must |
| F7 | Schedule and monitor pipelines | Must |
| F8 | Host data apps (Streamlit, etc.) | Should |
| F9 | Data quality checks | Should |
| F10 | User authentication | Should |

### 2.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NF1 | Data volume | 10-500 GB |
| NF2 | Deployment | Single `docker compose up` |
| NF3 | Memory footprint | < 4 GB idle |
| NF4 | Query latency | < 5s for typical analytics |
| NF5 | Startup time | < 60 seconds |

### 2.3 Out of Scope (MVP)

- Real-time streaming
- Multi-tenant SaaS
- Complex RBAC
- Distributed compute
- Sub-second latency

---

## 3. Architecture

### 3.1 High-Level Design

```
┌──────────────────────────────────────────────────────────────────┐
│                         RATATOUILLE                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      WEB UI                               │   │
│  │  (Pipeline management, monitoring, data exploration)     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌───────────────┬───────────┴───────────┬────────────────┐     │
│  │               │                       │                │     │
│  │   PIPELINES   │        API            │   DATA APPS    │     │
│  │  (ETL/ELT)    │    (REST/GraphQL)     │  (Streamlit)   │     │
│  │               │                       │                │     │
│  └───────┬───────┴───────────┬───────────┴───────┬────────┘     │
│          │                   │                   │              │
│  ┌───────┴───────────────────┴───────────────────┴───────┐      │
│  │                    QUERY ENGINE                        │      │
│  │                  (SQL interface)                       │      │
│  └────────────────────────┬──────────────────────────────┘      │
│                           │                                      │
│  ┌────────────────────────┴──────────────────────────────┐      │
│  │                      STORAGE                           │      │
│  │     ┌─────────┐    ┌─────────┐    ┌─────────┐         │      │
│  │     │ BRONZE  │───▶│ SILVER  │───▶│  GOLD   │         │      │
│  │     │  (Raw)  │    │(Cleaned)│    │(Business)│        │      │
│  │     └─────────┘    └─────────┘    └─────────┘         │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Overview

| Component | Responsibility | Candidates |
|-----------|---------------|------------|
| **Storage** | Persist data in lakehouse format | MinIO, Local FS |
| **Format** | Data file format | Parquet, Delta Lake, Iceberg |
| **Query Engine** | SQL analytics | DuckDB, ClickHouse, Polars |
| **Pipelines** | ETL orchestration | Dagster, Prefect, Hamilton |
| **API** | Data access layer | FastAPI, GraphQL |
| **UI** | Management interface | Custom, Streamlit |
| **Data Apps** | User-built apps | Streamlit, Gradio |

### 3.3 Data Flow

```
                    INGESTION
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
    ▼                   ▼                   ▼
┌───────┐          ┌─────────┐         ┌────────┐
│  API  │          │Database │         │ Files  │
│Sources│          │  CDC    │         │Uploads │
└───┬───┘          └────┬────┘         └───┬────┘
    │                   │                  │
    └───────────────────┼──────────────────┘
                        ▼
                  ┌───────────┐
                  │  LANDING  │  (Raw, as-received)
                  └─────┬─────┘
                        │
                        ▼
                  ┌───────────┐
                  │  BRONZE   │  (Structured, partitioned)
                  └─────┬─────┘
                        │ Transform & Validate
                        ▼
                  ┌───────────┐
                  │  SILVER   │  (Cleaned, deduplicated)
                  └─────┬─────┘
                        │ Aggregate & Model
                        ▼
                  ┌───────────┐
                  │   GOLD    │  (Business-ready)
                  └─────┬─────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
      ┌───────┐    ┌─────────┐   ┌─────────┐
      │  API  │    │   BI    │   │   ML    │
      │Access │    │Dashboard│   │Training │
      └───────┘    └─────────┘   └─────────┘
```

---

## 4. Technology Decisions

See [ADRs](./adr/) for detailed decision records.

| Decision | Status | ADR |
|----------|--------|-----|
| Query Engine | Pending | - |
| Storage Backend | Pending | - |
| Orchestration | Pending | - |
| API Framework | Pending | - |
| UI Approach | Pending | - |

---

## 5. Deployment

### 5.1 Single Command Start

```bash
curl -sSL https://ratatouille.dev/install | sh
# or
docker compose up -d
```

### 5.2 Container Architecture

```yaml
services:
  ratatouille:
    image: ratatouille/ratatouille:latest
    ports:
      - "3000:3000"  # Web UI
      - "8000:8000"  # API
    volumes:
      - ./data:/data
```

---

## 6. Open Questions

1. **Build vs Integrate?** - Custom components or wrap existing tools?
2. **How opinionated?** - Convention over configuration vs flexibility?
3. **Upgrade path?** - How do users upgrade without data loss?
4. **Plugin system?** - Allow community extensions?

---

## 7. References

- [Journal](./journal/) - Development notes
- [ADRs](./adr/) - Decision records
- [CLAUDE.md](../../CLAUDE.md) - Project guidelines
