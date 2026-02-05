"""🎯 Workspace Context - Thread-local workspace state.

Allows setting the "current" workspace for operations that don't
explicitly specify one.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import Workspace

# Thread-local storage for current workspace
_context = threading.local()


def get_current_workspace() -> Workspace | None:
    """Get the current workspace (if set)."""
    return getattr(_context, "workspace", None)


def set_current_workspace(workspace: Workspace | None) -> None:
    """Set the current workspace."""
    _context.workspace = workspace


@contextmanager
def workspace_context(workspace: Workspace):
    """Context manager to temporarily set the current workspace.

    Example:
        with workspace_context(my_workspace):
            # All operations use my_workspace
            rat.query("SELECT * FROM bronze.sales")

        # Back to previous workspace
    """
    previous = get_current_workspace()
    set_current_workspace(workspace)
    try:
        yield workspace
    finally:
        set_current_workspace(previous)


def require_workspace() -> Workspace:
    """Get the current workspace or raise an error.

    Use this in functions that require a workspace context.
    """
    workspace = get_current_workspace()
    if workspace is None:
        raise RuntimeError(
            "No workspace context. Either:\n"
            "  1. Use `with workspace_context(ws):` to set one\n"
            "  2. Pass workspace explicitly to the function\n"
            "  3. Call `rat.use_workspace('name')` to set a default"
        )
    return workspace
