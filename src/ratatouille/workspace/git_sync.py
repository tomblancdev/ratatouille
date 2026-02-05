"""🔄 Git ↔ Nessie Branch Synchronization.

Automatically sync Nessie branches with Git branches for seamless
data versioning that follows code versioning.

Features:
- Auto-detect Git branch at runtime
- Git hooks for automatic Nessie branch creation
- Branch name mapping (Git → Nessie)
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def get_git_branch(repo_path: Path | str | None = None) -> str | None:
    """Get the current Git branch name.

    Args:
        repo_path: Path to Git repository (default: current directory)

    Returns:
        Branch name or None if not in a Git repo

    Example:
        branch = get_git_branch()
        # → "main", "feature/new-pipeline", etc.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            # HEAD means detached state
            return None if branch == "HEAD" else branch
        return None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def get_git_root(start_path: Path | str | None = None) -> Path | None:
    """Get the Git repository root directory.

    Args:
        start_path: Starting path to search from

    Returns:
        Path to Git root or None if not in a repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=start_path,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
        return None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def is_git_repo(path: Path | str | None = None) -> bool:
    """Check if path is inside a Git repository."""
    return get_git_root(path) is not None


def git_branch_to_nessie(git_branch: str, prefix: str = "") -> str:
    """Convert Git branch name to Nessie branch name.

    Handles special characters and applies optional prefix.

    Args:
        git_branch: Git branch name
        prefix: Optional prefix (e.g., "workspace/")

    Returns:
        Nessie-compatible branch name

    Examples:
        git_branch_to_nessie("main") → "main"
        git_branch_to_nessie("feature/new-thing") → "feature/new-thing"
        git_branch_to_nessie("main", prefix="ws/") → "ws/main"
    """
    # Nessie allows most characters that Git does
    # Just apply prefix if provided
    if prefix and not git_branch.startswith(prefix):
        return f"{prefix}{git_branch}"
    return git_branch


def resolve_nessie_branch(
    configured_branch: str,
    workspace_name: str | None = None,
    repo_path: Path | str | None = None,
) -> str:
    """Resolve the actual Nessie branch name from configuration.

    Handles special values:
    - "auto" or "git": Use current Git branch
    - "git:prefix/": Use Git branch with prefix
    - Any other value: Use as-is

    Args:
        configured_branch: Value from workspace.yaml isolation.nessie_branch
        workspace_name: Workspace name (for fallback)
        repo_path: Path to Git repository

    Returns:
        Resolved Nessie branch name

    Examples:
        resolve_nessie_branch("auto") → "feature/my-branch" (current Git branch)
        resolve_nessie_branch("git") → "feature/my-branch"
        resolve_nessie_branch("git:workspace/") → "workspace/feature/my-branch"
        resolve_nessie_branch("workspace/acme") → "workspace/acme" (literal)
    """
    # Check for auto/git modes
    if configured_branch in ("auto", "git"):
        git_branch = get_git_branch(repo_path)
        if git_branch:
            return git_branch
        # Fallback if not in Git repo
        if workspace_name:
            return f"workspace/{workspace_name}"
        return "main"

    # Check for git: prefix mode (e.g., "git:workspace/")
    if configured_branch.startswith("git:"):
        prefix = configured_branch[4:]  # Remove "git:"
        git_branch = get_git_branch(repo_path)
        if git_branch:
            return git_branch_to_nessie(git_branch, prefix=prefix)
        # Fallback
        if workspace_name:
            return f"{prefix}{workspace_name}"
        return "main"

    # Literal branch name
    return configured_branch


# =============================================================================
# Git Hooks
# =============================================================================

POST_CHECKOUT_HOOK = '''#!/bin/bash
# 🐀 Ratatouille: Auto-create Nessie branch on Git checkout
#
# This hook runs after `git checkout` or `git switch`
# It creates a matching Nessie branch if it doesn't exist

# Only run if we actually switched branches (flag $3 = 1)
if [ "$3" != "1" ]; then
    exit 0
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "HEAD" ]; then
    # Detached HEAD, skip
    exit 0
fi

NESSIE_URI="${NESSIE_URI:-http://localhost:19120/api/v2}"

# Check if we can reach Nessie
if ! curl -s --connect-timeout 2 "$NESSIE_URI/trees" > /dev/null 2>&1; then
    # Nessie not available, skip silently
    exit 0
fi

# Try to create branch (will fail silently if exists)
curl -s -X POST "$NESSIE_URI/trees/branch/$BRANCH" \\
    -H "Content-Type: application/json" \\
    -d "{\\\"type\\\": \\\"BRANCH\\\", \\\"hash\\\": \\\"$(curl -s $NESSIE_URI/trees/main | jq -r '.hash')\\\"}" \\
    > /dev/null 2>&1

# Print status
if curl -s "$NESSIE_URI/trees/$BRANCH" > /dev/null 2>&1; then
    echo "🌳 Nessie branch ready: $BRANCH"
fi
'''

POST_MERGE_HOOK = '''#!/bin/bash
# 🐀 Ratatouille: Reminder to merge Nessie branches
#
# This hook runs after `git merge`
# It reminds you to also merge the Nessie branch if needed

BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo ""
echo "💡 Don't forget to merge your Nessie data branch too:"
echo "   python -c \\"from ratatouille.catalog import NessieClient; NessieClient('$NESSIE_URI').merge_branch('SOURCE_BRANCH', '$BRANCH')\\""
echo ""
'''


def install_git_hooks(repo_path: Path | str | None = None, force: bool = False) -> dict:
    """Install Git hooks for Nessie branch synchronization.

    Args:
        repo_path: Path to Git repository
        force: Overwrite existing hooks

    Returns:
        Dict with installation results

    Example:
        install_git_hooks()
        # → {"post-checkout": "installed", "post-merge": "installed"}
    """
    git_root = get_git_root(repo_path)
    if not git_root:
        return {"error": "Not a Git repository"}

    hooks_dir = git_root / ".git" / "hooks"
    results = {}

    hooks = {
        "post-checkout": POST_CHECKOUT_HOOK,
        "post-merge": POST_MERGE_HOOK,
    }

    for hook_name, hook_content in hooks.items():
        hook_path = hooks_dir / hook_name

        if hook_path.exists() and not force:
            # Check if it's our hook
            existing = hook_path.read_text()
            if "Ratatouille" in existing:
                results[hook_name] = "already installed"
            else:
                results[hook_name] = "skipped (existing hook)"
            continue

        hook_path.write_text(hook_content)
        hook_path.chmod(0o755)
        results[hook_name] = "installed"

    return results


def uninstall_git_hooks(repo_path: Path | str | None = None) -> dict:
    """Remove Ratatouille Git hooks.

    Args:
        repo_path: Path to Git repository

    Returns:
        Dict with uninstallation results
    """
    git_root = get_git_root(repo_path)
    if not git_root:
        return {"error": "Not a Git repository"}

    hooks_dir = git_root / ".git" / "hooks"
    results = {}

    for hook_name in ["post-checkout", "post-merge"]:
        hook_path = hooks_dir / hook_name

        if not hook_path.exists():
            results[hook_name] = "not found"
            continue

        content = hook_path.read_text()
        if "Ratatouille" not in content:
            results[hook_name] = "skipped (not our hook)"
            continue

        hook_path.unlink()
        results[hook_name] = "removed"

    return results


def ensure_nessie_branch_exists(
    branch: str,
    nessie_uri: str | None = None,
    from_branch: str = "main",
) -> bool:
    """Ensure a Nessie branch exists, creating it if needed.

    Args:
        branch: Branch name to ensure exists
        nessie_uri: Nessie API URI
        from_branch: Branch to create from if creating

    Returns:
        True if branch exists (or was created), False on error
    """
    nessie_uri = nessie_uri or os.getenv("NESSIE_URI", "http://localhost:19120/api/v2")

    try:
        from ratatouille.catalog.nessie import BranchExistsError, NessieClient

        with NessieClient(nessie_uri) as nessie:
            try:
                nessie.create_branch(branch, from_branch=from_branch)
                print(f"🌳 Created Nessie branch: {branch}")
            except BranchExistsError:
                pass  # Already exists, that's fine
            except Exception as e:
                print(f"⚠️ Could not create Nessie branch: {e}")
                return False
        return True
    except ImportError:
        return False
