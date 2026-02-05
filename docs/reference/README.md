# 📖 Technical Reference

> Complete reference documentation for Ratatouille

---

## Quick Links

| Reference | Description |
|-----------|-------------|
| [SDK](sdk.md) | Python API (`run`, `workspace`, `query`) |
| [Tools](tools.md) | Exploration functions (`tools.*`) |
| [CLI](cli.md) | Command-line interface |
| [Environment Variables](environment-variables.md) | All configuration options |
| [Config YAML](config-yaml.md) | Pipeline configuration schema |
| [Workspace YAML](workspace-yaml.md) | Workspace configuration schema |
| [Resource Profiles](resource-profiles.md) | VM sizing presets |
| [Jinja Functions](jinja-functions.md) | `ref()`, `watermark()`, etc. |

---

## SDK Quick Reference

```python
from ratatouille import run, workspace, query, tools

# === Core Functions ===
workspace("analytics")            # Load workspace
run("silver.sales")               # Run pipeline
run("gold.kpis", full_refresh=True)  # Full refresh
df = query("SELECT * FROM ...")   # Execute SQL

# === Exploration (tools) ===
tools.info()                      # Workspace info
tools.tables()                    # List all tables
tools.layers()                    # Show medallion layers
tools.schema("silver.sales")      # Table schema
tools.preview("gold.metrics")     # Preview data

# === S3 Operations (tools) ===
tools.ls("bronze/")               # List files
tools.tree()                      # Folder structure
tools.s3_uri("silver", "events")  # Get S3 URI
```

See [SDK Reference](sdk.md) for complete documentation.

---

## CLI Quick Reference

```bash
rat init <name>           # Create workspace
rat run <pipeline>        # Run pipeline
rat query "<sql>"         # Execute SQL
rat test                  # Run tests
rat docs generate         # Generate docs
rat docs check            # Validate docs
```

See [CLI Reference](cli.md) for complete documentation.

---

## Configuration Files

### workspace.yaml

```yaml
name: my-workspace
resources:
  profile: small
layers:
  bronze:
    retention_days: 90
```

### config.yaml (Pipeline)

```yaml
description: Clean sales data
owner: data-team@company.com
columns:
  - name: txn_id
    type: string
    tests: [not_null, unique]
```

---

## Environment Variables

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ROOT_USER` | `ratatouille` | S3 access key |
| `MINIO_ROOT_PASSWORD` | `ratatouille123` | S3 secret key |
| `RAT_PROFILE` | `small` | Resource profile |
| `RATATOUILLE_WORKSPACE` | `demo` | Default workspace |

See [Environment Variables](environment-variables.md) for complete list.

---

## Jinja Functions

Available in SQL pipelines:

| Function | Description |
|----------|-------------|
| `{{ ref('layer.table') }}` | Reference another table |
| `{% if is_incremental() %}` | Incremental mode check |
| `{{ watermark('column') }}` | Last processed value |
| `{{ this }}` | Current table reference |

See [Jinja Functions](jinja-functions.md) for examples.
