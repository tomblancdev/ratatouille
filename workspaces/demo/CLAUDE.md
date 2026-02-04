# 🐀 Ratatouille Workspace - Claude Guidelines

## ⛔ STRICT SECURITY RULES

### NEVER Read These Files
You are **STRICTLY FORBIDDEN** from reading, viewing, or accessing:

1. **Data Files**
   - `*.parquet` - Data lake files
   - `*.csv`, `*.json`, `*.jsonl` - Raw data
   - `*.duckdb` - Database files
   - `data/` directory - Any content
   - Any file in `bronze/`, `silver/`, `gold/` data directories

2. **Secrets & Credentials**
   - `.env`, `.env.*` - Environment files
   - `*.pem`, `*.key`, `*.crt` - Certificates
   - `credentials.*`, `secrets.*` - Secret files
   - `*_secret*`, `*_key*`, `*_token*` - Named secrets
   - Any file containing API keys, passwords, or tokens

3. **Query Results**
   - Never execute queries that `SELECT *` from tables
   - Never run queries that return actual data rows
   - Never display data previews or samples

### NEVER Execute These Commands
- `cat`, `head`, `tail`, `less` on data files
- `duckdb` CLI with queries on actual data
- `SELECT` queries that return user data
- `aws s3 cp`, `mc cat` or similar to read object storage
- Any command that would expose data content

## ✅ ALLOWED Actions

### You CAN:
- Read and write pipeline definitions (`*.sql`, `*.yaml`, `*.py` in `pipelines/`)
- Read and write `workspace.yaml` configuration
- Read documentation and markdown files
- Write and modify Python code for ingestion scripts
- Run schema/metadata queries:
  ```sql
  -- OK: Schema inspection
  DESCRIBE table_name;
  SHOW TABLES;
  SELECT column_name, data_type FROM information_schema.columns;

  -- OK: Count/aggregate (no actual data)
  SELECT COUNT(*) FROM table_name;
  SELECT device, COUNT(*) FROM events GROUP BY device;
  ```
- Run `make` commands for testing and linting
- Modify `.devcontainer/` configuration
- Create new pipeline files

### Pipeline Development Workflow
1. **Understand requirements** - Ask user what metrics/transformations needed
2. **Write SQL/Python** - Create pipeline in appropriate layer
3. **Write YAML config** - Define schema, tests, freshness
4. **Validate syntax** - Check SQL/Jinja syntax without running
5. **Let user test** - User runs pipeline and validates output

## 🛡️ Security Mindset

- Treat all data as **PII/sensitive** by default
- Never assume data is safe to view
- When in doubt, **ask the user** instead of reading
- Suggest queries/code, let user execute and report back
- Focus on **structure and logic**, not data content

## 📁 Workspace Structure

```
demo/
├── .devcontainer/     # ✅ Can read/write
├── pipelines/
│   ├── bronze/        # ✅ Can read/write code, ⛔ NOT data
│   ├── silver/        # ✅ Can read/write code, ⛔ NOT data
│   └── gold/          # ✅ Can read/write code, ⛔ NOT data
├── data/              # ⛔ NEVER access
├── workspace.yaml     # ✅ Can read/write
├── CLAUDE.md          # ✅ This file
└── README.md          # ✅ Can read/write
```

## 🔧 Safe Commands

```bash
# ✅ OK - Testing
make test
make lint
make typecheck

# ✅ OK - Schema inspection
python -c "from ratatouille import sdk; print(sdk.query('SHOW TABLES'))"

# ✅ OK - Pipeline execution (no data output)
python -c "from ratatouille import sdk; sdk.run('silver.sales')"

# ⛔ FORBIDDEN - Data access
python -c "from ratatouille import sdk; print(sdk.query('SELECT * FROM sales'))"
```

## 💬 When User Asks for Data

If the user asks you to look at data:
1. **Politely decline** - Explain you can't access data directly
2. **Suggest alternatives**:
   - "Could you run this query and share the schema/counts?"
   - "What columns/patterns are you seeing?"
   - "Can you describe the data issue you're encountering?"
3. **Help debug** - Work with metadata, schemas, and user descriptions

## 🔒 Enforcement

This workspace has multiple layers of protection:

1. **CLAUDE.md** - These guidelines (you're reading them)
2. **`.claude/settings.json`** - Permission rules for Read/Edit/Bash
3. **`.claude/hooks/pre-bash.sh`** - Blocks dangerous bash commands

If you attempt a blocked action, you'll receive an error. This is intentional.
