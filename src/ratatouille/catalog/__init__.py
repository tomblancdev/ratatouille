"""📚 Catalog - Nessie + Iceberg integration.

Provides:
- Nessie REST client for branch management
- Iceberg table operations via PyIceberg
- Git-like versioning (commit, merge, branch)
"""

from .nessie import NessieClient
from .iceberg import IcebergCatalog

__all__ = [
    "NessieClient",
    "IcebergCatalog",
]
