"""🏢 Workspace Management - Isolated multi-tenant workspaces.

Each workspace has:
- Its own Nessie branch for catalog isolation (auto-syncs with Git!)
- Its own S3 prefix for storage isolation
- Its own resource limits
- Its own pipeline definitions

Git ↔ Nessie Sync:
    # In workspace.yaml, use "auto" to sync with Git branch:
    isolation:
      nessie_branch: "auto"  # Uses current Git branch
      s3_prefix: "myworkspace"

    # Install Git hooks for automatic branch creation:
    from ratatouille.workspace import install_git_hooks
    install_git_hooks()
"""

from .config import WorkspaceConfig
from .git_sync import (
    ensure_nessie_branch_exists,
    get_git_branch,
    get_git_root,
    install_git_hooks,
    is_git_repo,
    resolve_nessie_branch,
    uninstall_git_hooks,
)
from .manager import Workspace, get_workspace, list_workspaces

__all__ = [
    "Workspace",
    "WorkspaceConfig",
    "get_workspace",
    "list_workspaces",
    # Git sync utilities
    "get_git_branch",
    "get_git_root",
    "is_git_repo",
    "resolve_nessie_branch",
    "install_git_hooks",
    "uninstall_git_hooks",
    "ensure_nessie_branch_exists",
]
