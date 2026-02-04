"""🦆 Query Engine - DuckDB with Iceberg support.

DuckDB is used for all data processing:
- Embedded (no separate service)
- Low memory footprint
- Native Iceberg extension
- Streaming/chunked processing for large data
"""

from .duckdb import DuckDBEngine

__all__ = [
    "DuckDBEngine",
]
