"""🧪 Integration tests for Nessie REST Client.

These tests require Nessie to be running.
Run with: podman compose up -d nessie

Set environment variable:
- NESSIE_URI (default: http://localhost:19120/api/v2)
"""

import os
import uuid

import pytest

from ratatouille.catalog.nessie import (
    BranchExistsError,
    BranchNotFoundError,
    NessieClient,
    NessieError,
)

# Skip all tests if Nessie not available
pytestmark = pytest.mark.skipif(
    not os.getenv("NESSIE_URI"),
    reason="NESSIE_URI not set - Nessie service not available",
)


@pytest.fixture
def nessie():
    """Get NessieClient instance."""
    uri = os.getenv("NESSIE_URI", "http://localhost:19120/api/v2")
    client = NessieClient(uri)
    yield client
    client.close()


@pytest.fixture
def unique_branch_name():
    """Generate a unique branch name for testing."""
    return f"test/branch-{uuid.uuid4().hex[:8]}"


class TestNessieBranchOperations:
    """Test Nessie branch management."""

    def test_get_main_branch(self, nessie):
        """Test getting the main branch."""
        branch = nessie.get_branch("main")

        assert branch.name == "main"
        assert branch.hash is not None
        assert branch.type == "BRANCH"

    def test_list_branches(self, nessie):
        """Test listing branches."""
        branches = nessie.list_branches()

        assert len(branches) >= 1
        assert any(b.name == "main" for b in branches)

    def test_create_and_delete_branch(self, nessie, unique_branch_name):
        """Test creating and deleting a branch."""
        # Create branch
        branch = nessie.create_branch(unique_branch_name, from_branch="main")

        assert branch.name == unique_branch_name
        assert branch.hash is not None

        # Verify it exists
        retrieved = nessie.get_branch(unique_branch_name)
        assert retrieved.name == unique_branch_name

        # Delete it
        nessie.delete_branch(unique_branch_name)

        # Verify it's gone
        with pytest.raises(BranchNotFoundError):
            nessie.get_branch(unique_branch_name)

    def test_create_branch_already_exists(self, nessie, unique_branch_name):
        """Test creating a branch that already exists raises error."""
        # Create branch first
        nessie.create_branch(unique_branch_name)

        try:
            # Try to create again
            with pytest.raises(BranchExistsError):
                nessie.create_branch(unique_branch_name)
        finally:
            # Cleanup
            nessie.delete_branch(unique_branch_name)

    def test_get_nonexistent_branch(self, nessie):
        """Test getting a branch that doesn't exist."""
        with pytest.raises(BranchNotFoundError):
            nessie.get_branch("nonexistent/branch/12345")

    def test_delete_main_branch_fails(self, nessie):
        """Test that deleting main branch raises error."""
        with pytest.raises(NessieError, match="Cannot delete default branch"):
            nessie.delete_branch("main")


class TestNessieBranchWorkflow:
    """Test realistic branch workflows."""

    def test_workspace_branch_workflow(self, nessie, unique_branch_name):
        """Test creating a workspace-style branch."""
        workspace_branch = f"workspace/{unique_branch_name}"

        try:
            # Create workspace branch from main
            branch = nessie.create_branch(workspace_branch, from_branch="main")
            assert branch.name == workspace_branch

            # List branches should include it
            branches = nessie.list_branches()
            assert any(b.name == workspace_branch for b in branches)

        finally:
            # Cleanup
            try:
                nessie.delete_branch(workspace_branch)
            except Exception:
                pass

    def test_branch_isolation(self, nessie):
        """Test that branches are properly isolated."""
        branch_a = f"test/branch-a-{uuid.uuid4().hex[:8]}"
        branch_b = f"test/branch-b-{uuid.uuid4().hex[:8]}"

        try:
            # Create two branches from main
            a = nessie.create_branch(branch_a, from_branch="main")
            b = nessie.create_branch(branch_b, from_branch="main")

            # They should have the same initial hash (same source)
            assert a.hash == b.hash

            # Both should exist
            assert nessie.get_branch(branch_a).name == branch_a
            assert nessie.get_branch(branch_b).name == branch_b

        finally:
            # Cleanup
            for branch in [branch_a, branch_b]:
                try:
                    nessie.delete_branch(branch)
                except Exception:
                    pass


class TestNessieClientContextManager:
    """Test client as context manager."""

    def test_context_manager(self):
        """Test using client as context manager."""
        uri = os.getenv("NESSIE_URI", "http://localhost:19120/api/v2")

        with NessieClient(uri) as nessie:
            branch = nessie.get_branch("main")
            assert branch.name == "main"

        # Client should be closed after context exit
        # (no assertion needed, just verify no exceptions)

    def test_repr(self, nessie):
        """Test string representation."""
        repr_str = repr(nessie)

        assert "NessieClient" in repr_str
        assert "uri=" in repr_str
        assert "default_branch=" in repr_str
