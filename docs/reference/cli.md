# 🖥️ CLI Reference

Command-line interface for Ratatouille.

---

## Installation

The `rat` CLI is available inside the Dagster container:

```bash
docker compose exec dagster rat --help
```

Or run directly:

```bash
docker compose exec dagster rat <command>
```

---

## Commands Overview

| Command | Description |
|---------|-------------|
| `rat init <name>` | Create a new workspace |
| `rat run <pipeline>` | Run a pipeline |
| `rat query <sql>` | Execute SQL query |
| `rat test` | Run pipeline tests |
| `rat docs generate` | Generate documentation |
| `rat docs check` | Validate documentation |

---

## rat init

Create a new workspace with scaffold files.

```bash
rat init <name> [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `name` | Workspace name |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Parent directory (default: current directory) |

### Examples

```bash
# Create workspace in current directory
rat init my-project

# Create in specific location
rat init analytics --path /home/user/projects
```

### Generated Structure

```
my-project/
├── workspace.yaml
├── pipelines/
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── schemas/
├── macros/
└── notebooks/
```

---

## rat run

Run a specific pipeline.

```bash
rat run <pipeline> [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `pipeline` | Pipeline name (e.g., `silver.events`) |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--full-refresh` | `-f` | Full refresh (rebuild all data) |

### Examples

```bash
# Run incrementally
rat run silver.events

# Full refresh
rat run silver.events --full-refresh
```

---

## rat query

Execute a SQL query and display results.

```bash
rat query "<sql>"
```

### Arguments

| Argument | Description |
|----------|-------------|
| `sql` | SQL query to execute |

### Examples

```bash
# List tables
rat query "SHOW TABLES"

# Query data
rat query "SELECT * FROM {bronze.sales} LIMIT 10"

# Aggregation
rat query "SELECT product, SUM(qty) FROM {silver.sales} GROUP BY product"
```

---

## rat test

Run pipeline tests.

```bash
rat test [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--workspace` | `-w` | Workspace name or path |
| `--pipeline` | `-p` | Filter by pipeline name |
| `--layer` | `-l` | Filter by layer (bronze, silver, gold) |
| `--type` | `-t` | Filter by test type (quality, unit) |
| `--output` | `-o` | Output format: console (default) or json |
| `--verbose` | `-v` | Show verbose output with data samples |
| `--fail-fast` | `-x` | Stop on first failure |

### Examples

```bash
# Run all tests in workspace
rat test -w demo

# Run tests for specific pipeline
rat test -p silver/sales

# Run only quality tests
rat test -t quality

# Run silver layer tests with verbose output
rat test -l silver -v

# JSON output for CI/CD
rat test -w demo -o json | jq '.summary'

# Stop on first failure
rat test -x
```

### Test Output

**Console Output:**

```
🐀 Running tests for workspace: demo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 silver/sales
  ✅ unique_transaction_ids           16ms
     → No violations
  ❌ positive_amounts                 15ms
     → 2 violations found

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Summary: 4 tests | 2 passed ✅ | 1 failed ❌ | 1 warned ⚠️
```

**JSON Output:**

```json
{
  "workspace": "demo",
  "summary": {
    "total": 4,
    "passed": 2,
    "failed": 1,
    "warned": 1
  }
}
```

---

## rat docs

Documentation commands.

### rat docs generate

Generate documentation for pipelines.

```bash
rat docs generate [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--workspace` | `-w` | Workspace name or path |
| `--pipeline` | `-p` | Generate for specific pipeline only |

#### Examples

```bash
# Generate docs for entire workspace
rat docs generate -w demo

# Generate docs for a single pipeline
rat docs generate -w demo -p silver/sales
```

### rat docs check

Validate documentation completeness.

```bash
rat docs check [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--workspace` | `-w` | Workspace name or path |
| `--strict` | | Treat warnings as errors |
| `--verbose` | `-v` | Show all pipelines, not just failures |

#### Examples

```bash
# Check completeness
rat docs check -w demo

# Strict mode for CI/CD
rat docs check -w demo --strict

# Verbose output
rat docs check -w demo -v
```

---

## Environment Variables

The CLI respects these environment variables:

| Variable | Description |
|----------|-------------|
| `RATATOUILLE_WORKSPACE` | Default workspace name |
| `RATATOUILLE_WORKSPACE_PATH` | Explicit workspace path |
| `RAT_PROFILE` | Resource profile (tiny, small, medium, large) |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error or test failure |

---

## Workspace Discovery

When `--workspace` is not specified, the CLI looks for a workspace in this order:

1. `RATATOUILLE_WORKSPACE_PATH` environment variable
2. Current directory if it contains `pipelines/` or `workspace.yaml`
3. Parent directories with `pipelines/` or `workspace.yaml`

---

## CI/CD Examples

### GitHub Actions

```yaml
- name: Run tests
  run: |
    docker compose exec -T dagster rat test -w demo -o json > results.json

- name: Check documentation
  run: |
    docker compose exec -T dagster rat docs check -w demo --strict
```

### GitLab CI

```yaml
test:
  script:
    - docker compose exec -T dagster rat test -w demo
    - docker compose exec -T dagster rat docs check -w demo --strict
```
