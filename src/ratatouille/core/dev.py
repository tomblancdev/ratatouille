"""🔬 Dev Mode - Isolated development with Iceberg branches.

Provides git-like branching for data development so engineers can work
on pipelines without affecting production data. Uses native Iceberg
branch support for zero data duplication (copy-on-write).

Usage:
    from ratatouille import rat

    # Start dev mode
    rat.dev_start("feature/new-cleaning")

    # All writes go to the branch
    rat.transform(sql, target="silver.sales")

    # Check what changed
    rat.dev_diff("silver.sales")

    # Merge to main when ready
    rat.dev_merge()

    # Or abandon changes
    rat.dev_drop()
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

# Thread-local storage for dev state
_dev_state = threading.local()


def _get_dev_branch() -> str | None:
    """Get current dev branch name, or None if not in dev mode."""
    return getattr(_dev_state, "branch", None)


def _set_dev_branch(branch: str | None) -> None:
    """Set current dev branch."""
    _dev_state.branch = branch


def is_dev_mode() -> bool:
    """Check if currently in dev mode.

    Returns:
        True if in dev mode, False otherwise

    Example:
        if is_dev_mode():
            print("Working on branch:", get_effective_branch())
    """
    return _get_dev_branch() is not None


def get_effective_branch() -> str:
    """Get the branch to use for operations (dev branch or 'main').

    Returns:
        Branch name - either the dev branch or "main"

    Example:
        branch = get_effective_branch()
        # → "feature/new-cleaning" if in dev mode
        # → "main" if not in dev mode
    """
    return _get_dev_branch() or "main"


@contextmanager
def dev_mode(branch_name: str):
    """Context manager for dev mode.

    All operations within the context will use the specified branch
    instead of main. The previous state is restored on exit.

    Args:
        branch_name: Name of the branch to use

    Yields:
        The branch name

    Example:
        with dev_mode("feature/new-cleaning"):
            rat.transform(...)  # Writes to branch
        # Outside context: writes to main
    """
    previous = _get_dev_branch()
    _set_dev_branch(branch_name)
    try:
        yield branch_name
    finally:
        _set_dev_branch(previous)


def enter_dev(branch_name: str) -> str:
    """Enter dev mode (without context manager).

    Use this when you want to stay in dev mode across multiple cells
    in a Jupyter notebook.

    Args:
        branch_name: Name of the branch to use

    Returns:
        The branch name

    Example:
        enter_dev("feature/new-cleaning")
        # ... multiple operations ...
        exit_dev()
    """
    _set_dev_branch(branch_name)
    return branch_name


def exit_dev() -> None:
    """Exit dev mode.

    After calling this, all operations will use the main branch again.

    Example:
        exit_dev()
        # Now back to main branch
    """
    _set_dev_branch(None)
