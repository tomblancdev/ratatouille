"""📋 Schema Management - Validation and evolution.

Provides:
- Schema definitions in YAML
- DataFrame validation (not_null, unique, positive, etc.)
- Schema evolution tracking
- dbt-like data tests
"""

from .validator import validate_dataframe, SchemaValidator
from .tests import not_null, unique, positive, accepted_values

__all__ = [
    "validate_dataframe",
    "SchemaValidator",
    "not_null",
    "unique",
    "positive",
    "accepted_values",
]
