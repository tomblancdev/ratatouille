"""🌳 Nessie REST Client - Git-like versioning for data.

Nessie provides:
- Branch management (create, merge, delete)
- Commit history for data changes
- Table metadata location retrieval for DuckDB reads
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class BranchInfo:
    """Information about a Nessie branch."""

    name: str
    hash: str
    type: str = "BRANCH"


class NessieError(Exception):
    """Base exception for Nessie operations."""

    pass


class BranchNotFoundError(NessieError):
    """Branch does not exist."""

    pass


class BranchExistsError(NessieError):
    """Branch already exists."""

    pass


class TableNotFoundError(NessieError):
    """Table not found on branch."""

    pass


class NessieClient:
    """Client for Nessie REST API v2.

    Handles branch management and table metadata retrieval.

    Example:
        nessie = NessieClient("http://localhost:19120/api/v2")

        # Branch operations
        nessie.create_branch("workspace/acme", from_branch="main")
        branches = nessie.list_branches()
        nessie.merge_branch("workspace/acme", "main")
        nessie.delete_branch("workspace/acme")

        # Get metadata location for DuckDB reads
        metadata_path = nessie.get_table_metadata_location("bronze.sales", "main")
        # → "s3://warehouse/bronze/sales/metadata/00001-xxx.metadata.json"
    """

    def __init__(
        self,
        uri: str,
        default_branch: str = "main",
        timeout: float = 30.0,
    ):
        """Initialize Nessie client.

        Args:
            uri: Nessie API v2 URI (e.g., "http://localhost:19120/api/v2")
            default_branch: Default branch name
            timeout: Request timeout in seconds
        """
        self.uri = uri.rstrip("/")
        self.default_branch = default_branch
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> NessieClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict[str, Any] | None:
        """Make an HTTP request to Nessie API.

        Args:
            method: HTTP method
            path: API path (without base URI)
            **kwargs: Additional httpx request arguments

        Returns:
            JSON response or None for 204

        Raises:
            NessieError: On API errors
        """
        url = f"{self.uri}/{path.lstrip('/')}"
        response = self._client.request(method, url, **kwargs)

        if response.status_code == 204:
            return None

        if response.status_code >= 400:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("message", error_msg)
            except Exception:
                pass

            if response.status_code == 404:
                if "branch" in error_msg.lower() or "reference" in error_msg.lower():
                    raise BranchNotFoundError(error_msg)
                if "table" in error_msg.lower() or "content" in error_msg.lower():
                    raise TableNotFoundError(error_msg)

            if response.status_code == 409:
                if "already exists" in error_msg.lower():
                    raise BranchExistsError(error_msg)

            raise NessieError(f"Nessie API error ({response.status_code}): {error_msg}")

        return response.json() if response.content else None

    # =========================================================================
    # Branch Operations
    # =========================================================================

    def create_branch(
        self,
        name: str,
        from_branch: str | None = None,
    ) -> BranchInfo:
        """Create a new branch.

        Args:
            name: Name for the new branch
            from_branch: Branch to create from (default: main)

        Returns:
            BranchInfo for the new branch

        Raises:
            BranchExistsError: If branch already exists
            BranchNotFoundError: If source branch doesn't exist

        Example:
            nessie.create_branch("workspace/acme", from_branch="main")
        """
        from_branch = from_branch or self.default_branch

        # Get the source branch hash
        source = self.get_branch(from_branch)

        # Create new branch from that hash
        data = self._request(
            "POST",
            f"trees/branch/{name}",
            params={"name": name, "type": "BRANCH"},
            json={
                "type": "BRANCH",
                "hash": source.hash,
            },
        )

        return BranchInfo(
            name=data["name"],
            hash=data["hash"],
            type=data.get("type", "BRANCH"),
        )

    def get_branch(self, name: str | None = None) -> BranchInfo:
        """Get branch information.

        Args:
            name: Branch name (default: default_branch)

        Returns:
            BranchInfo

        Raises:
            BranchNotFoundError: If branch doesn't exist
        """
        name = name or self.default_branch
        data = self._request("GET", f"trees/{name}")

        return BranchInfo(
            name=data["name"],
            hash=data["hash"],
            type=data.get("type", "BRANCH"),
        )

    def list_branches(self) -> list[BranchInfo]:
        """List all branches.

        Returns:
            List of BranchInfo for all branches

        Example:
            for branch in nessie.list_branches():
                print(f"{branch.name}: {branch.hash}")
        """
        data = self._request("GET", "trees", params={"filter": "refType == 'BRANCH'"})

        return [
            BranchInfo(
                name=ref["name"],
                hash=ref["hash"],
                type=ref.get("type", "BRANCH"),
            )
            for ref in data.get("references", [])
        ]

    def delete_branch(self, name: str) -> None:
        """Delete a branch.

        Args:
            name: Branch to delete

        Raises:
            BranchNotFoundError: If branch doesn't exist
            NessieError: If trying to delete the default branch

        Example:
            nessie.delete_branch("workspace/old")
        """
        if name == self.default_branch:
            raise NessieError(f"Cannot delete default branch '{name}'")

        # Get current hash for the delete operation
        branch = self.get_branch(name)

        self._request(
            "DELETE",
            f"trees/{name}",
            headers={"If-Match": branch.hash},
        )

    def merge_branch(
        self,
        source: str,
        target: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Merge source branch into target branch.

        Args:
            source: Source branch to merge from
            target: Target branch to merge into (default: main)
            message: Optional merge commit message

        Returns:
            Merge result info

        Raises:
            BranchNotFoundError: If source or target branch doesn't exist

        Example:
            nessie.merge_branch("workspace/acme", "main", message="Merge workspace changes")
        """
        target = target or self.default_branch

        # Get source branch info
        source_branch = self.get_branch(source)
        target_branch = self.get_branch(target)

        result = self._request(
            "POST",
            f"trees/{target}/history/merge",
            headers={"If-Match": target_branch.hash},
            json={
                "fromRefName": source,
                "fromHash": source_branch.hash,
                "message": message or f"Merge {source} into {target}",
            },
        )

        return result or {"merged": True, "source": source, "target": target}

    # =========================================================================
    # Table Metadata Operations
    # =========================================================================

    def get_table_content(
        self,
        table: str,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Get table content/metadata from Nessie.

        Args:
            table: Table identifier (e.g., "bronze.sales")
            branch: Branch to read from (default: default_branch)

        Returns:
            Table content including metadata location

        Raises:
            TableNotFoundError: If table doesn't exist on branch
        """
        branch = branch or self.default_branch

        # Parse table name into key
        key = self._table_to_key(table)

        data = self._request(
            "GET",
            f"trees/{branch}/contents/{key}",
        )

        return data

    def get_table_metadata_location(
        self,
        table: str,
        branch: str | None = None,
    ) -> str:
        """Get the S3 path to the Iceberg metadata.json file.

        This is the key method for DuckDB reads - it returns the path
        that can be used with iceberg_scan().

        Args:
            table: Table identifier (e.g., "bronze.sales")
            branch: Branch to read from

        Returns:
            S3 path to metadata.json (e.g., "s3://warehouse/.../metadata/xxx.metadata.json")

        Raises:
            TableNotFoundError: If table doesn't exist

        Example:
            path = nessie.get_table_metadata_location("bronze.sales", "main")
            # → "s3://warehouse/bronze/sales/metadata/00001-abc.metadata.json"
        """
        content = self.get_table_content(table, branch)

        # Extract metadata location from Iceberg table content
        if "content" in content:
            iceberg_content = content["content"]
            if "metadataLocation" in iceberg_content:
                return iceberg_content["metadataLocation"]

        raise TableNotFoundError(
            f"Table '{table}' on branch '{branch}' has no metadata location"
        )

    def list_tables(
        self,
        namespace: str | None = None,
        branch: str | None = None,
    ) -> list[str]:
        """List all tables on a branch.

        Args:
            namespace: Optional namespace filter (e.g., "bronze")
            branch: Branch to list from

        Returns:
            List of table identifiers

        Example:
            tables = nessie.list_tables("bronze", "main")
            # → ["bronze.sales", "bronze.customers"]
        """
        branch = branch or self.default_branch

        params = {}
        if namespace:
            params["filter"] = f"entry.namespace.name == '{namespace}'"

        data = self._request(
            "GET",
            f"trees/{branch}/entries",
            params=params,
        )

        tables = []
        for entry in data.get("entries", []):
            if entry.get("type") == "ICEBERG_TABLE":
                key = entry.get("name", {})
                if isinstance(key, dict):
                    # Key is namespace + name
                    elements = key.get("elements", [])
                    tables.append(".".join(elements))
                else:
                    tables.append(str(key))

        return tables

    def _table_to_key(self, table: str) -> str:
        """Convert table name to Nessie content key format.

        Args:
            table: Table name (e.g., "bronze.sales" or "sales")

        Returns:
            URL-encoded key path
        """
        # Split by dot and join with encoded separator
        parts = table.split(".")
        # Nessie v2 uses URL path format: namespace.table becomes namespace%1Ftable
        return "%1F".join(parts)

    def __repr__(self) -> str:
        return f"NessieClient(uri={self.uri!r}, default_branch={self.default_branch!r})"
