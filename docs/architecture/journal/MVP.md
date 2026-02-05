# 🐀 Ratatouille - MVP Scope

> **Goal:** End-to-end demo in 1 week
> **Target:** Deliver the "aha!" moment

---

## The Demo Story

### User Journey

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE "AHA!" MOMENT                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. START                                                       │
│     $ ratatouille init my-project                               │
│     ✨ Created project from template                            │
│                                                                 │
│  2. EXPLORE (Guided)                                            │
│     → Open Jupyter notebook                                     │
│     → Sample CSV data already there                             │
│     → Step-by-step guide in notebook                            │
│                                                                 │
│  3. BUILD (In notebook)                                         │
│     → Ingest CSV → Bronze                                       │
│     → Clean & transform → Silver                                │
│     → Aggregate → Gold                                          │
│                                                                 │
│  4. QUERY                                                       │
│     → SQL query on Gold data                                    │
│     → See results instantly                                     │
│                                                                 │
│  5. "WOW"                                                       │
│     "I just built a data pipeline in 15 minutes!"               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## MVP Features

### ✅ Must Have (Week 1)

| Feature | Description |
|---------|-------------|
| **Project template** | `ratatouille init` creates working starter |
| **Sample data** | Generated CSV with realistic fake data |
| **Guided notebook** | Step-by-step tutorial in Jupyter |
| **Storage layer** | Bronze/Silver/Gold with Parquet |
| **Query engine** | DuckDB for SQL queries |
| **Single command start** | `docker compose up` runs everything |

### ⏳ Nice to Have (If time permits)

| Feature | Description |
|---------|-------------|
| Simple CLI | Commands for common operations |
| Basic API | REST endpoint to query Gold data |
| Web UI | Simple dashboard showing pipeline status |

### ❌ Not in MVP

| Feature | Reason |
|---------|--------|
| Multiple data sources | Start with CSV only |
| Scheduling | Manual runs first |
| Authentication | Single user for now |
| Streaming | Batch only |
| Production hardening | Demo quality is fine |

---

## Technical Scope

### Stack (Tentative)

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Storage | Local FS + Parquet | Simplest, no MinIO needed |
| Query | DuckDB | Fast, embedded, great DX |
| Notebooks | Jupyter | Standard, familiar |
| Container | Single Docker image | Simple deployment |
| Orchestration | None (MVP) | Run notebooks manually |

### Project Structure

```
my-project/
├── docker-compose.yml      # One command start
├── notebooks/
│   └── 01_getting_started.ipynb  # Guided tutorial
├── data/
│   ├── landing/            # Raw uploads
│   ├── bronze/             # Structured raw
│   ├── silver/             # Cleaned
│   └── gold/               # Business-ready
└── src/
    └── ratatouille/        # Core library
```

---

## Success Criteria

### Demo Must Show

1. ✅ **Zero to running** in < 2 minutes
2. ✅ **Guided experience** - user doesn't get lost
3. ✅ **Real transformation** - not just copying files
4. ✅ **Query results** - SQL on processed data
5. ✅ **"I could use this"** reaction

### Quality Bar

- Works on Mac, Linux, Windows (Docker)
- No crashes during demo
- Clear error messages
- Documentation for each step

---

## 1-Week Sprint Plan

### Day 1-2: Foundation
- [ ] Project template generator
- [ ] Docker setup (Jupyter + DuckDB)
- [ ] Sample data generator

### Day 3-4: Core Pipeline
- [ ] Storage helpers (read/write Parquet)
- [ ] Guided notebook (Bronze → Silver → Gold)
- [ ] Query interface

### Day 5-6: Polish
- [ ] End-to-end testing
- [ ] Documentation
- [ ] README with quickstart

### Day 7: Demo
- [ ] Record demo video
- [ ] Final testing
- [ ] Release v0.1.0-alpha

---

## Decisions Made

| Question | Decision |
|----------|----------|
| **Data theme** | Point of Sale (POS) sales data |
| **Entry point** | `docker compose` + `Makefile` |
| **Viz** | Basic charts in notebook (nice to have) |

---

## Definition of Done

MVP is complete when:

> A new user can run `docker compose up`, open a notebook,
> follow the guide, and query their Gold layer data
> in under 15 minutes.
