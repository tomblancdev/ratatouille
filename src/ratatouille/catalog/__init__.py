"""📚 Catalog - Nessie + Iceberg integration.

Provides git-like versioning for data through:
- NessieClient: Branch management (create, merge, delete)
- IcebergCatalog: Branch-aware table operations via PyIceberg

Example:
    from ratatouille.catalog import NessieClient, IcebergCatalog

    # Branch operations
    nessie = NessieClient("http://localhost:19120/api/v2")
    nessie.create_branch("workspace/acme", from_branch="main")

    # Table operations (branch-isolated)
    catalog = IcebergCatalog.from_env(branch="workspace/acme")
    catalog.create_table("bronze.sales", df)
"""

from .iceberg import IcebergCatalog
from .nessie import (
    BranchExistsError,
    BranchInfo,
    BranchNotFoundError,
    NessieClient,
    NessieError,
    TableNotFoundError,
)

__all__ = [
    "NessieClient",
    "NessieError",
    "BranchNotFoundError",
    "BranchExistsError",
    "TableNotFoundError",
    "BranchInfo",
    "IcebergCatalog",
]
