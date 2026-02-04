"""📚 Catalog - Nessie + Iceberg integration.

TODO: Implement Nessie REST client and Iceberg operations.

Planned features:
- NessieClient: Branch management (create, merge, commit)
- IcebergCatalog: Table operations via PyIceberg
- Git-like versioning for data

For now, workspace isolation is handled by:
- Nessie branches (configured in workspace.yaml)
- S3 prefixes per workspace
"""

# TODO: Implement when needed
# from .nessie import NessieClient
# from .iceberg import IcebergCatalog

__all__: list[str] = []
