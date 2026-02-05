"""📝 Documentation Templates - Markdown generators for pipeline docs.

Templates for generating:
- README.md - Main pipeline overview
- data_dictionary.md - Column definitions and PII info
- business_rules.md - Business logic documentation
- lineage.md - Dependency diagrams

All templates support manual content preservation via markers.
"""

from .readme import generate_readme
from .data_dictionary import generate_data_dictionary
from .business_rules import generate_business_rules
from .lineage import generate_lineage

__all__ = [
    "generate_readme",
    "generate_data_dictionary",
    "generate_business_rules",
    "generate_lineage",
]
