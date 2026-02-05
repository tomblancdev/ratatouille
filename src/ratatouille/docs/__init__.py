"""📚 Documentation System - Auto-generate and validate pipeline documentation.

This module provides tools to:
- Generate standardized documentation from config.yaml and SQL
- Validate documentation completeness
- Track PII fields and business rules

Usage:
    from ratatouille.docs import DocumentationGenerator, CompletenessValidator

    # Generate docs for a workspace
    generator = DocumentationGenerator(workspace_path)
    generator.generate_all()

    # Validate completeness
    validator = CompletenessValidator(workspace_path)
    results = validator.validate_all()
"""

from .generator import DocumentationGenerator
from .validator import CompletenessValidator
from .models import (
    OwnerConfig,
    BusinessRule,
    DocumentationConfig,
    EnhancedColumnConfig,
    EnhancedPipelineConfig,
)

__all__ = [
    "DocumentationGenerator",
    "CompletenessValidator",
    "OwnerConfig",
    "BusinessRule",
    "DocumentationConfig",
    "EnhancedColumnConfig",
    "EnhancedPipelineConfig",
]
