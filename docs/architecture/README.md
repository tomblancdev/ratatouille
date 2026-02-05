# 📐 Architecture Documentation

> Internal technical documentation

---

## Overview

- **[System Overview](overview.md)** - High-level architecture and design

---

## ADRs (Architecture Decision Records)

Records of significant architectural decisions:

| ADR | Title |
|-----|-------|
| [0001](adr/0001-tech-stack-mvp.md) | Tech Stack for MVP |

**Template:** [0000-template.md](adr/0000-template.md)

---

## Development Journal

Chronological notes on development progress:

| Date | Topic |
|------|-------|
| [2026-01-29](journal/2026-01-29.md) | Initial notes |

**Historical Documents:**

- [MVP.md](journal/MVP.md) - Original MVP planning
- [CONCEPT.md](journal/CONCEPT.md) - Early concepts
- [REWORK.md](journal/REWORK.md) - Architecture rework notes

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                     RATATOUILLE PLATFORM                         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Data Layers                            │  │
│  │      Bronze    →    Silver    →    Gold                  │  │
│  │     (Raw)         (Cleaned)      (Business)              │  │
│  │                                                           │  │
│  │              Apache Iceberg (Table Format)                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                               │                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Core Services                          │  │
│  │   ┌────────────┐    ┌────────────┐    ┌────────────┐    │  │
│  │   │   MinIO    │    │   Nessie   │    │  Dagster   │    │  │
│  │   │  (Storage) │    │  (Catalog) │    │  (Orch)    │    │  │
│  │   └────────────┘    └────────────┘    └────────────┘    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

1. **Iceberg + Nessie** - Git-like versioning for data
2. **MinIO** - Self-hosted S3-compatible storage
3. **Dagster** - Asset-based orchestration
4. **Podman/Docker** - Container-first deployment
5. **Medallion Architecture** - Bronze → Silver → Gold

See [overview.md](overview.md) for detailed architecture documentation.
