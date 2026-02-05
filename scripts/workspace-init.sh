#!/bin/bash
# 🐀 Ratatouille Workspace Initialization
# Runs at container startup to set up Git hooks and verify connections

set -e

echo "🐀 Initializing Ratatouille workspace..."

# Install Git hooks if we're in a Git repo
if [ -d ".git" ] || git rev-parse --git-dir > /dev/null 2>&1; then
    echo "📦 Installing Git hooks for Nessie sync..."
    python -c "
from ratatouille.workspace import install_git_hooks
result = install_git_hooks()
for hook, status in result.items():
    print(f'   {hook}: {status}')
" 2>/dev/null || echo "   ⚠️ Could not install hooks (ratatouille not available)"
else
    echo "   ℹ️ Not a Git repo, skipping hooks"
fi

# Ensure current Git branch has a Nessie branch
if [ -d ".git" ] || git rev-parse --git-dir > /dev/null 2>&1; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    if [ -n "$BRANCH" ] && [ "$BRANCH" != "HEAD" ]; then
        echo "🌳 Ensuring Nessie branch exists: $BRANCH"
        python -c "
from ratatouille.workspace import ensure_nessie_branch_exists
ensure_nessie_branch_exists('$BRANCH')
" 2>/dev/null || echo "   ⚠️ Could not create Nessie branch (Nessie not available)"
    fi
fi

# Check connections
echo "🔌 Checking connections..."
python -c "from ratatouille import tools; tools.connections()" 2>/dev/null || echo "   ⚠️ Services not available (run 'make up' first)"

echo ""
echo "🐀 Workspace ready!"
