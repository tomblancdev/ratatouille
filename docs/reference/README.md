# 📖 Technical Reference

> Complete reference documentation for Ratatouille

---

## Quick Links

| Reference | Description |
|-----------|-------------|
| [SDK](sdk.md) | `rat.*` Python API |
| [CLI](cli.md) | Command-line interface |
| [Environment Variables](environment-variables.md) | All configuration options |
| [Config YAML](config-yaml.md) | Pipeline configuration schema |
| [Workspace YAML](workspace-yaml.md) | Workspace configuration schema |
| [Resource Profiles](resource-profiles.md) | VM sizing presets |
| [Jinja Functions](jinja-functions.md) | `ref()`, `watermark()`, etc. |

---

## SDK Quick Reference

```python
from ratatouille import rat

# === Read ===
rat.df("{bronze.table}")           # Read Iceberg table
rat.query("SELECT * FROM ...")     # SQL query
rat.read("bucket/path.parquet")    # Read Parquet from S3

# === Write ===
rat.ice_ingest(source, target)     # File → Iceberg
rat.transform(sql, target)         # SQL → Iceberg
rat.write(df, path)                # DataFrame → S3

# === Iceberg ===
rat.ice_all()                      # List all tables
rat.ice_history(table)             # Time travel history
rat.ice_drop(table)                # Delete table

# === Dev Mode ===
rat.dev_start(branch)              # Create branch
rat.dev_merge()                    # Merge to main
rat.dev_drop()                     # Abandon branch
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
