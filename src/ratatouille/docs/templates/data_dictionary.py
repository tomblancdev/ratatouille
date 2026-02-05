"""📖 Data Dictionary Template - Generate column documentation.

Generates a data_dictionary.md with:
- Column definitions (name, type, description)
- PII marking and classification
- Example values
- Tests/constraints
- Required/unique indicators
"""

from __future__ import annotations

from datetime import datetime

from ..models import EnhancedPipelineConfig, EnhancedColumnConfig


def generate_data_dictionary(
    config: EnhancedPipelineConfig,
    pipeline_name: str,
    layer: str,
) -> str:
    """Generate data_dictionary.md content for a pipeline.

    Args:
        config: Pipeline configuration
        pipeline_name: Name of the pipeline
        layer: Layer (bronze, silver, gold)

    Returns:
        Generated data_dictionary.md content
    """
    sections = []

    # Header
    display_name = pipeline_name.replace("_", " ").title()
    sections.append(f"# Data Dictionary: {display_name}")
    sections.append("")
    sections.append(f"> 🐀 Auto-generated | Layer: `{layer}` | Last updated: {datetime.now().strftime('%Y-%m-%d')}")
    sections.append("")

    if not config.columns:
        sections.append("*No columns defined in config.yaml*")
        return "\n".join(sections)

    # Summary stats
    total = len(config.columns)
    required = len(config.get_required_columns())
    unique = len(config.get_unique_columns())
    pii_count = len(config.get_pii_columns())
    unmarked = len(config.columns_missing_pii_marking())

    sections.append("## Summary")
    sections.append("")
    sections.append(f"- **Total columns:** {total}")
    sections.append(f"- **Required (not_null):** {required}")
    sections.append(f"- **Unique keys:** {unique}")
    sections.append(f"- **PII columns:** {pii_count}")
    if unmarked > 0:
        sections.append(f"- **⚠️ Missing PII marking:** {unmarked}")
    sections.append("")

    # Quick reference table
    sections.append("## Quick Reference")
    sections.append("")
    sections.append("| Column | Type | PII | Required | Unique |")
    sections.append("|--------|------|-----|----------|--------|")
    for col in config.columns:
        pii = "⚠️" if col.is_pii() else ("✓" if col.pii is False else "?")
        required = "✓" if "not_null" in col.tests else ""
        unique = "✓" if "unique" in col.tests else ""
        sections.append(f"| `{col.name}` | {col.type} | {pii} | {required} | {unique} |")
    sections.append("")

    # Detailed column definitions
    sections.append("## Column Definitions")
    sections.append("")

    for col in config.columns:
        sections.extend(_generate_column_section(col))

    return "\n".join(sections)


def _generate_column_section(col: EnhancedColumnConfig) -> list[str]:
    """Generate detailed documentation for a single column."""
    lines = []

    # Column header
    lines.append(f"### `{col.name}`")
    lines.append("")

    # Description
    if col.description:
        lines.append(col.description)
        lines.append("")

    # Properties table
    lines.append("| Property | Value |")
    lines.append("|----------|-------|")
    lines.append(f"| **Type** | `{col.type}` |")

    # PII info
    if col.pii is True:
        pii_type = col.pii_type or "unclassified"
        lines.append(f"| **PII** | ⚠️ Yes ({pii_type}) |")
    elif col.pii is False:
        lines.append("| **PII** | No |")
    else:
        lines.append("| **PII** | ❓ Not marked |")

    # Example
    if col.example:
        lines.append(f"| **Example** | `{col.example}` |")

    # Tests/constraints
    if col.tests:
        tests_str = ", ".join(_format_test(t) for t in col.tests)
        lines.append(f"| **Constraints** | {tests_str} |")

    lines.append("")
    return lines


def _format_test(test: str | dict) -> str:
    """Format a test for display."""
    if isinstance(test, str):
        return f"`{test}`"
    if isinstance(test, dict):
        # Handle tests like {'accepted_values': ['A', 'B']}
        for key, value in test.items():
            if isinstance(value, list):
                return f"`{key}({', '.join(str(v) for v in value[:3])}{'...' if len(value) > 3 else ''})`"
            return f"`{key}({value})`"
    return str(test)


def generate_pii_report(config: EnhancedPipelineConfig, pipeline_name: str) -> str:
    """Generate a PII-focused report for compliance.

    Args:
        config: Pipeline configuration
        pipeline_name: Name of the pipeline

    Returns:
        PII report as markdown
    """
    sections = []

    sections.append(f"# PII Report: {pipeline_name}")
    sections.append("")

    pii_columns = config.get_pii_columns()
    unmarked = config.columns_missing_pii_marking()

    if not pii_columns and not unmarked:
        sections.append("✅ No PII columns and all columns have been marked.")
        return "\n".join(sections)

    if pii_columns:
        sections.append("## ⚠️ PII Columns")
        sections.append("")
        sections.append("| Column | Type | Classification | Description |")
        sections.append("|--------|------|----------------|-------------|")
        for col in pii_columns:
            pii_type = col.pii_type or "unclassified"
            sections.append(f"| `{col.name}` | {col.type} | {pii_type} | {col.description or '-'} |")
        sections.append("")

    if unmarked:
        sections.append("## ❓ Columns Missing PII Marking")
        sections.append("")
        sections.append("The following columns need `pii: true` or `pii: false` in config.yaml:")
        sections.append("")
        for name in unmarked:
            sections.append(f"- `{name}`")
        sections.append("")

    return "\n".join(sections)
