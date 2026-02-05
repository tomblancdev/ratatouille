"""📄 README Template - Generate main pipeline documentation.

Generates a README.md with:
- Overview and description
- Owner information
- Tags and categorization
- Dependencies (upstream pipelines)
- Freshness SLA
- Links to detailed docs
- Manual content preservation
"""

from __future__ import annotations

from datetime import datetime

from ..models import EnhancedPipelineConfig
from ..parsers.lineage import LineageInfo

# Markers for manual content preservation
MANUAL_START = "<!-- MANUAL CONTENT START -->"
MANUAL_END = "<!-- MANUAL CONTENT END -->"


def generate_readme(
    config: EnhancedPipelineConfig,
    pipeline_name: str,
    layer: str,
    lineage: LineageInfo | None = None,
    existing_content: str | None = None,
) -> str:
    """Generate README.md content for a pipeline.

    Args:
        config: Pipeline configuration
        pipeline_name: Name of the pipeline (e.g., "sales")
        layer: Layer (bronze, silver, gold)
        lineage: Optional lineage info with dependencies
        existing_content: Existing README to preserve manual sections

    Returns:
        Generated README.md content
    """
    sections = []

    # Header
    display_name = pipeline_name.replace("_", " ").title()
    sections.append(f"# {display_name} Pipeline")
    sections.append("")
    sections.append(
        f"> 🐀 Auto-generated documentation | Last updated: {datetime.now().strftime('%Y-%m-%d')}"
    )
    sections.append("")

    # Tags
    if config.get_tags():
        tags_str = " ".join(f"`{tag}`" for tag in config.get_tags())
        sections.append(f"**Tags:** {tags_str}")
        sections.append("")

    # Overview
    sections.append("## Overview")
    sections.append("")
    if config.description:
        sections.append(config.description.strip())
    else:
        sections.append(f"*No description provided for {layer}/{pipeline_name}*")
    sections.append("")

    # Owner
    sections.append("## Owner")
    sections.append("")
    owner = config.get_owner_config()
    if owner:
        if owner.team:
            sections.append(f"- **Team:** {owner.team}")
        if owner.email:
            sections.append(f"- **Email:** {owner.email}")
        if owner.slack:
            sections.append(f"- **Slack:** {owner.slack}")
    else:
        sections.append("*No owner defined*")
    sections.append("")

    # Dependencies
    sections.append("## Dependencies")
    sections.append("")
    if lineage and lineage.upstream:
        sections.append("### Upstream")
        for upstream in lineage.upstream:
            sections.append(f"- `{upstream}`")
        sections.append("")

        if lineage.downstream:
            sections.append("### Downstream")
            for downstream in lineage.downstream:
                sections.append(f"- `{downstream}`")
            sections.append("")
    else:
        sections.append("*No dependencies detected*")
        sections.append("")

    # Freshness SLA
    if config.freshness:
        sections.append("## Freshness SLA")
        sections.append("")
        sections.append(f"- **Warning:** {config.freshness.format_warn()}")
        sections.append(f"- **Error:** {config.freshness.format_error()}")
        sections.append("")

    # PII Columns (warning if any)
    pii_columns = config.get_pii_columns()
    if pii_columns:
        sections.append("## ⚠️ PII Notice")
        sections.append("")
        sections.append(
            "This pipeline contains personally identifiable information (PII):"
        )
        sections.append("")
        for col in pii_columns:
            pii_type = f" ({col.pii_type})" if col.pii_type else ""
            sections.append(
                f"- `{col.name}`{pii_type}: {col.description or 'No description'}"
            )
        sections.append("")

    # Links to detailed docs
    sections.append("## Documentation")
    sections.append("")
    sections.append(
        "- [Data Dictionary](docs/data_dictionary.md) - Column definitions and types"
    )
    sections.append(
        "- [Business Rules](docs/business_rules.md) - Data validation logic"
    )
    sections.append("- [Lineage](docs/lineage.md) - Dependency diagram")
    sections.append("")

    # Schema summary
    if config.columns:
        sections.append("## Schema Summary")
        sections.append("")
        sections.append("| Column | Type | Required | Unique |")
        sections.append("|--------|------|----------|--------|")
        for col in config.columns[:10]:  # First 10 columns
            required = "✓" if "not_null" in col.tests else ""
            unique = "✓" if "unique" in col.tests else ""
            sections.append(f"| `{col.name}` | {col.type} | {required} | {unique} |")
        if len(config.columns) > 10:
            sections.append(f"| ... | *{len(config.columns) - 10} more columns* | | |")
        sections.append("")
        sections.append(
            "See [Data Dictionary](docs/data_dictionary.md) for full schema."
        )
        sections.append("")

    # Manual content section
    manual_content = _extract_manual_content(existing_content)
    sections.append(MANUAL_START)
    if manual_content:
        sections.append(manual_content)
    else:
        sections.append("## Additional Notes")
        sections.append("")
        sections.append(
            "*Add your manual notes here. This section is preserved on regeneration.*"
        )
    sections.append(MANUAL_END)
    sections.append("")

    return "\n".join(sections)


def _extract_manual_content(existing_content: str | None) -> str | None:
    """Extract manual content from existing README."""
    if not existing_content:
        return None

    start_idx = existing_content.find(MANUAL_START)
    end_idx = existing_content.find(MANUAL_END)

    if start_idx == -1 or end_idx == -1:
        return None

    # Extract content between markers (excluding the markers themselves)
    manual = existing_content[start_idx + len(MANUAL_START) : end_idx]
    return manual.strip() if manual.strip() else None
