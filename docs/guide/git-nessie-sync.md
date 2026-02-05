# 🔄 Git ↔ Nessie Branch Sync

> **Data versioning that follows code versioning** - When you switch Git branches, your data automatically switches too.

---

## The Problem

You're building a data pipeline. You create a Git branch `feature/new-transform` to experiment. But your data changes affect everyone because they're on a shared Nessie branch:

```
❌ Without Git-Nessie Sync:

Git branches:        main ──────────────────────────────────
                            \
                             feature/new-transform
                                    │
                                    │ You write data here
                                    ▼
Nessie branch:       workspace/demo ────────────────────────
                                    │
                                    │ But it affects main too!
                                    ▼
                              😱 Broken production data
```

## The Solution

With Git-Nessie sync, Nessie branches automatically follow Git branches:

```
✅ With Git-Nessie Sync:

Git branches:        main ──────────────────────────────────
                            \
                             feature/new-transform
                                    │
                                    ▼
Nessie branches:     main ──────────────────────────────────
                            \
                             feature/new-transform  (auto-created!)
                                    │
                                    │ Your data is isolated!
                                    ▼
                              ✅ Production safe
```

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                         YOUR WORKFLOW                               │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                         GIT                                  │   │
│  │                                                              │   │
│  │    main ─────●─────●─────●─────●─────●                      │   │
│  │                     \           \                            │   │
│  │                      ●───●       ●───●                       │   │
│  │                    feature/a   feature/b                     │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                              │                                      │
│                              │ workspace.yaml: nessie_branch: auto  │
│                              │                                      │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │                       NESSIE                                 │   │
│  │                                                              │   │
│  │    main ─────●─────●─────●─────●─────●                      │   │
│  │                     \           \                            │   │
│  │                      ●───●       ●───●                       │   │
│  │                    feature/a   feature/b                     │   │
│  │                                                              │   │
│  │              (Mirrors Git - auto-created!)                   │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                              │                                      │
│                              │ Each branch has isolated data        │
│                              │                                      │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │                      MINIO (S3)                              │   │
│  │                                                              │   │
│  │  s3://warehouse/                                             │   │
│  │  ├── bronze/sales/                                          │   │
│  │  │   ├── data/                                              │   │
│  │  │   │   ├── 00001.parquet  (shared - copy-on-write)       │   │
│  │  │   │   ├── 00002.parquet  (shared)                        │   │
│  │  │   │   └── 00003.parquet  (feature/a only)               │   │
│  │  │   └── metadata/                                          │   │
│  │  │       ├── main-v5.json         → [file1, file2]         │   │
│  │  │       └── feature-a-v1.json    → [file1, file2, file3]  │   │
│  │  │                                                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Insight: Zero-Copy Branching

When you create a Nessie branch, **no data is copied**. Only a metadata pointer is created. Data files are shared between branches until you modify them (copy-on-write).

```
Before writing on feature/a:
  main:      metadata → [file1, file2]
  feature/a: metadata → [file1, file2]  (same files!)

After writing on feature/a:
  main:      metadata → [file1, file2]         (unchanged)
  feature/a: metadata → [file1, file2, file3]  (new file only)
```

This means:
- 🚀 **Instant branching** - No waiting for data copy
- 💾 **Space efficient** - Only changed data uses extra space
- 🔒 **Safe isolation** - Changes don't affect other branches

---

## Quick Start

### 1. Enable Git Sync in Your Workspace

```yaml
# workspaces/my-workspace/workspace.yaml
name: my-workspace

isolation:
  nessie_branch: "auto"     # ← This enables Git sync!
  s3_prefix: "my-workspace"
```

### 2. Install Git Hooks (Optional but Recommended)

Git hooks automatically create Nessie branches when you checkout Git branches:

```python
from ratatouille.workspace import install_git_hooks

result = install_git_hooks()
print(result)
# {'post-checkout': 'installed', 'post-merge': 'installed'}
```

Or run manually:
```bash
python -c "from ratatouille.workspace import install_git_hooks; install_git_hooks()"
```

### 3. That's It!

Now when you switch Git branches, your data follows:

```bash
# You're on main, data comes from Nessie "main" branch
git checkout main
python -c "from ratatouille import workspace; print(workspace('demo').nessie_branch)"
# → main

# Switch to feature branch, data comes from Nessie "feature/x" branch
git checkout -b feature/new-pipeline
python -c "from ratatouille import workspace; print(workspace('demo').nessie_branch)"
# → feature/new-pipeline
```

---

## Configuration Options

### Option 1: Auto (Direct Git Branch)

Uses the exact Git branch name as the Nessie branch.

```yaml
isolation:
  nessie_branch: "auto"
```

| Git Branch | Nessie Branch |
|------------|---------------|
| `main` | `main` |
| `feature/new-pipeline` | `feature/new-pipeline` |
| `dev` | `dev` |

### Option 2: Git with Prefix

Adds a prefix to the Git branch name. Useful for namespacing.

```yaml
isolation:
  nessie_branch: "git:workspace/"
```

| Git Branch | Nessie Branch |
|------------|---------------|
| `main` | `workspace/main` |
| `feature/new-pipeline` | `workspace/feature/new-pipeline` |
| `dev` | `workspace/dev` |

### Option 3: Fixed Branch (No Sync)

Traditional mode - always uses the same Nessie branch regardless of Git.

```yaml
isolation:
  nessie_branch: "workspace/my-workspace"
```

| Git Branch | Nessie Branch |
|------------|---------------|
| `main` | `workspace/my-workspace` |
| `feature/new-pipeline` | `workspace/my-workspace` |
| `dev` | `workspace/my-workspace` |

---

## Git Hooks

### What They Do

| Hook | When It Runs | What It Does |
|------|--------------|--------------|
| `post-checkout` | After `git checkout` or `git switch` | Creates Nessie branch if it doesn't exist |
| `post-merge` | After `git merge` | Reminds you to merge Nessie branches too |

### Installing Hooks

```python
from ratatouille.workspace import install_git_hooks

# Install hooks
result = install_git_hooks()
# {'post-checkout': 'installed', 'post-merge': 'installed'}

# Force overwrite existing hooks
result = install_git_hooks(force=True)

# Uninstall hooks
from ratatouille.workspace import uninstall_git_hooks
uninstall_git_hooks()
```

### Hook Behavior

**post-checkout hook:**
```bash
$ git checkout -b feature/new-thing
Switched to a new branch 'feature/new-thing'
🌳 Nessie branch ready: feature/new-thing
```

**post-merge hook:**
```bash
$ git merge feature/done
Merge made by the 'recursive' strategy.
 ...

💡 Don't forget to merge your Nessie data branch too:
   nessie.merge_branch('feature/done', 'main')
```

### Automatic Setup in Containers

If you're using the workspace devcontainer, hooks are installed automatically on container start via the `workspace-init` script.

---

## Common Workflows

### Feature Branch Development

```bash
# 1. Create feature branch (Git + Nessie)
git checkout -b feature/new-transform
# 🌳 Nessie branch ready: feature/new-transform

# 2. Develop and test - data is isolated
python -c "
from ratatouille import workspace, run

ws = workspace('demo')
print(f'Working on Nessie branch: {ws.nessie_branch}')
# → feature/new-transform

run('silver.sales')  # Writes to feature branch only!
"

# 3. Verify isolation - main is unchanged
git checkout main
python -c "
from ratatouille import workspace, query

ws = workspace('demo')
print(f'Now on: {ws.nessie_branch}')  # → main
# Data from feature branch is NOT visible here
"

# 4. Merge when ready
git checkout main
git merge feature/new-transform

# 5. Merge data too
python -c "
from ratatouille.catalog import NessieClient

nessie = NessieClient('http://localhost:19120/api/v2')
nessie.merge_branch('feature/new-transform', 'main')
print('✅ Data merged!')
"
```

### Parallel Development

Multiple developers can work on different features simultaneously:

```
Developer A (feature/pipeline-a):
  - Writes to bronze.sales
  - Changes schema
  - Only visible on feature/pipeline-a branch

Developer B (feature/pipeline-b):
  - Also writes to bronze.sales
  - Different changes
  - Only visible on feature/pipeline-b branch

Main branch:
  - Unchanged
  - Still has production data
  - Safe!
```

### Experimentation Without Fear

```python
# Create experimental branch
git checkout -b experiment/crazy-idea

# Go wild - nothing can break!
from ratatouille import workspace

ws = workspace('demo')
catalog = ws.get_catalog()

# Drop and recreate tables
catalog.drop_table('silver.sales')
catalog.create_table('silver.sales', my_crazy_schema)

# Didn't work? Just delete the branch
git checkout main
git branch -D experiment/crazy-idea

# Nessie branch can be cleaned up too
from ratatouille.catalog import NessieClient
nessie = NessieClient('http://localhost:19120/api/v2')
nessie.delete_branch('experiment/crazy-idea')
```

---

## API Reference

### Workspace Git Sync Functions

```python
from ratatouille.workspace import (
    get_git_branch,
    get_git_root,
    is_git_repo,
    resolve_nessie_branch,
    install_git_hooks,
    uninstall_git_hooks,
    ensure_nessie_branch_exists,
)

# Get current Git branch
branch = get_git_branch()  # → "main", "feature/x", or None

# Get Git repository root
root = get_git_root()  # → Path("/home/user/project") or None

# Check if in a Git repo
if is_git_repo():
    print("We're in a Git repo!")

# Resolve configured branch to actual branch
actual = resolve_nessie_branch(
    configured_branch="auto",      # From workspace.yaml
    workspace_name="demo",         # Fallback if not in Git
)
# → "feature/current-branch" or "workspace/demo"

# Install/uninstall hooks
install_git_hooks()
uninstall_git_hooks()

# Ensure a Nessie branch exists
ensure_nessie_branch_exists("feature/new-branch")
```

### NessieClient Branch Operations

```python
from ratatouille.catalog import NessieClient

nessie = NessieClient("http://localhost:19120/api/v2")

# Create branch
nessie.create_branch("feature/new", from_branch="main")

# List branches
for branch in nessie.list_branches():
    print(f"{branch.name}: {branch.hash}")

# Merge branches
nessie.merge_branch("feature/done", "main")

# Delete branch
nessie.delete_branch("feature/old")

# Get branch info
info = nessie.get_branch("main")
print(f"Hash: {info.hash}")
```

---

## Troubleshooting

### "Nessie branch not found"

The Nessie branch doesn't exist yet. Create it:

```python
from ratatouille.workspace import ensure_nessie_branch_exists
ensure_nessie_branch_exists("your-branch-name")
```

Or install Git hooks to auto-create branches:

```python
from ratatouille.workspace import install_git_hooks
install_git_hooks()
```

### "Not a Git repository"

Git sync only works inside Git repositories. Either:

1. Initialize a Git repo: `git init`
2. Use a fixed Nessie branch instead:
   ```yaml
   isolation:
     nessie_branch: "workspace/my-workspace"  # Fixed, no Git sync
   ```

### Hooks not working

Check if hooks are installed:

```bash
ls -la .git/hooks/post-checkout
```

If not, install them:

```python
from ratatouille.workspace import install_git_hooks
install_git_hooks(force=True)
```

### Merging data after Git merge

Git merge doesn't automatically merge Nessie data. After `git merge`, also merge data:

```python
from ratatouille.catalog import NessieClient

nessie = NessieClient("http://localhost:19120/api/v2")
nessie.merge_branch("feature/done", "main")
```

---

## Best Practices

### 1. Always Install Git Hooks

Hooks ensure Nessie branches exist before you try to use them:

```python
# Add to your project setup
from ratatouille.workspace import install_git_hooks
install_git_hooks()
```

### 2. Match Git and Nessie Merges

When you merge a Git branch, also merge the Nessie branch:

```bash
# Git merge
git checkout main
git merge feature/done

# Nessie merge
python -c "
from ratatouille.catalog import NessieClient
NessieClient('http://localhost:19120/api/v2').merge_branch('feature/done', 'main')
"
```

### 3. Clean Up Old Branches

Delete Nessie branches when you delete Git branches:

```bash
# Delete Git branch
git branch -d feature/old

# Delete Nessie branch
python -c "
from ratatouille.catalog import NessieClient
NessieClient('http://localhost:19120/api/v2').delete_branch('feature/old')
"
```

### 4. Use Prefixes for Shared Repos

If multiple workspaces share a Nessie server, use prefixes to avoid conflicts:

```yaml
# Team A's workspace
isolation:
  nessie_branch: "git:team-a/"

# Team B's workspace
isolation:
  nessie_branch: "git:team-b/"
```

---

## FAQ

### Does this copy all my data when I create a branch?

**No!** Nessie uses copy-on-write. Creating a branch only creates a metadata pointer. Data files are shared until you modify them.

### What happens if Nessie is down?

If Nessie is unavailable:
- Git operations still work (Git doesn't depend on Nessie)
- Data operations will fail with connection errors
- The `workspace-init` script will show a warning but continue

### Can I use this without Git?

Yes! Use a fixed Nessie branch:

```yaml
isolation:
  nessie_branch: "my-fixed-branch"
```

### Does this work with GitHub Actions / CI?

Yes! In CI, the Git branch is determined by the checkout. Just ensure:
1. Nessie is accessible from CI
2. The branch exists (or hooks create it)

```yaml
# GitHub Actions example
- name: Setup Nessie branch
  run: |
    python -c "
    from ratatouille.workspace import ensure_nessie_branch_exists
    ensure_nessie_branch_exists('${{ github.head_ref }}')"
```
