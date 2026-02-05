"""🏢 Workspace Management - Isolated multi-tenant workspaces.

Each workspace has:
- Its own Nessie branch for catalog isolation
- Its own S3 prefix for storage isolation
- Its own resource limits
- Its own pipeline definitions
"""

from .config import WorkspaceConfig
from .manager import Workspace, get_workspace, list_workspaces

__all__ = [
    "Workspace",
    "WorkspaceConfig",
    "get_workspace",
    "list_workspaces",
]
