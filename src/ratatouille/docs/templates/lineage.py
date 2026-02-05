"""🔗 Lineage Template - Generate dependency documentation.

Generates lineage.md with:
- Mermaid diagram showing dependencies
- List of upstream/downstream pipelines
- Layer classification
"""

from __future__ import annotations

from datetime import datetime

from ..parsers.lineage import LineageInfo


def generate_lineage(
    lineage: LineageInfo,
    pipeline_name: str,
    layer: str,
    workspace_diagram: str | None = None,
) -> str:
    """Generate lineage.md content for a pipeline.

    Args:
        lineage: LineageInfo with dependencies
        pipeline_name: Name of the pipeline
        layer: Layer (bronze, silver, gold)
        workspace_diagram: Optional full workspace diagram

    Returns:
        Generated lineage.md content
    """
    sections = []

    # Header
    display_name = pipeline_name.replace("_", " ").title()
    sections.append(f"# Lineage: {display_name}")
    sections.append("")
    sections.append(
        f"> 🐀 Auto-generated | Layer: `{layer}` | Last updated: {datetime.now().strftime('%Y-%m-%d')}"
    )
    sections.append("")

    # Summary
    sections.append("## Summary")
    sections.append("")
    sections.append(f"- **Pipeline:** `{lineage.pipeline}`")
    sections.append(f"- **Layer:** {layer}")
    sections.append(f"- **Upstream dependencies:** {len(lineage.upstream)}")
    sections.append(f"- **Downstream consumers:** {len(lineage.downstream)}")
    sections.append("")

    # Pipeline-specific diagram
    if lineage.has_dependencies():
        sections.append("## Pipeline Diagram")
        sections.append("")
        sections.append(lineage.to_mermaid())
        sections.append("")

    # Upstream details
    sections.append("## Upstream Dependencies")
    sections.append("")
    if lineage.upstream:
        sections.append("This pipeline reads from:")
        sections.append("")
        sections.append("| Source | Layer | Description |")
        sections.append("|--------|-------|-------------|")
        for upstream in sorted(lineage.upstream):
            upstream_layer = _get_layer(upstream)
            sections.append(f"| `{upstream}` | {upstream_layer} | - |")
        sections.append("")
    else:
        sections.append("*This is a source pipeline with no upstream dependencies.*")
        sections.append("")

    # Downstream details
    sections.append("## Downstream Consumers")
    sections.append("")
    if lineage.downstream:
        sections.append("This pipeline is consumed by:")
        sections.append("")
        sections.append("| Consumer | Layer | Description |")
        sections.append("|----------|-------|-------------|")
        for downstream in sorted(lineage.downstream):
            downstream_layer = _get_layer(downstream)
            sections.append(f"| `{downstream}` | {downstream_layer} | - |")
        sections.append("")
    else:
        sections.append("*No downstream pipelines consume this data (yet).*")
        sections.append("")

    # Impact analysis
    sections.append("## Impact Analysis")
    sections.append("")

    if lineage.downstream:
        sections.append("### ⚠️ Changes to this pipeline may affect:")
        sections.append("")
        for downstream in lineage.downstream:
            sections.append(f"- `{downstream}`")
        sections.append("")
        sections.append(
            "Please coordinate with downstream owners before making breaking changes."
        )
    else:
        sections.append(
            "This pipeline has no downstream dependencies. Changes can be made safely."
        )
    sections.append("")

    # Full workspace diagram (optional)
    if workspace_diagram:
        sections.append("## Full Workspace Lineage")
        sections.append("")
        sections.append("Complete dependency graph for this workspace:")
        sections.append("")
        sections.append(workspace_diagram)
        sections.append("")

    return "\n".join(sections)


def _get_layer(pipeline_name: str) -> str:
    """Extract layer from pipeline name."""
    if "." in pipeline_name:
        layer = pipeline_name.split(".")[0]
        return layer.upper()
    return "UNKNOWN"


def generate_lineage_index(
    lineage_map: dict[str, LineageInfo],
    workspace_name: str,
) -> str:
    """Generate an index of all pipeline lineage in a workspace.

    Args:
        lineage_map: Dict mapping pipeline names to LineageInfo
        workspace_name: Name of the workspace

    Returns:
        Generated markdown content
    """
    sections = []

    sections.append(f"# Lineage Index: {workspace_name}")
    sections.append("")
    sections.append(
        f"> 🐀 Auto-generated | Last updated: {datetime.now().strftime('%Y-%m-%d')}"
    )
    sections.append("")

    # Stats
    sections.append("## Overview")
    sections.append("")
    sections.append(f"- **Total pipelines:** {len(lineage_map)}")

    # Count by layer
    by_layer: dict[str, int] = {}
    for lineage in lineage_map.values():
        layer = lineage.layer or "unknown"
        by_layer[layer] = by_layer.get(layer, 0) + 1

    for layer in ["bronze", "silver", "gold"]:
        if layer in by_layer:
            sections.append(f"- **{layer.title()}:** {by_layer[layer]}")
    sections.append("")

    # Full diagram
    sections.append("## Complete Lineage Diagram")
    sections.append("")

    # Build the diagram inline
    lines = ["```mermaid", "flowchart TD"]

    # Group by layer
    layers = {"bronze": [], "silver": [], "gold": []}
    for _name, lineage in lineage_map.items():
        layer = lineage.layer or "other"
        if layer in layers:
            layers[layer].append(lineage)

    for layer, pipelines in layers.items():
        if pipelines:
            lines.append(f"    subgraph {layer.upper()}")
            for lineage in pipelines:
                node_id = lineage.pipeline.replace(".", "_").replace("-", "_")
                lines.append(f'        {node_id}["{lineage.pipeline}"]')
            lines.append("    end")

    # Add edges
    for lineage in lineage_map.values():
        pipeline_id = lineage.pipeline.replace(".", "_").replace("-", "_")
        for upstream in lineage.upstream:
            upstream_id = upstream.replace(".", "_").replace("-", "_")
            lines.append(f"    {upstream_id} --> {pipeline_id}")

    lines.append("```")
    sections.extend(lines)
    sections.append("")

    # Pipeline list
    sections.append("## Pipeline List")
    sections.append("")
    sections.append("| Pipeline | Layer | Upstream | Downstream |")
    sections.append("|----------|-------|----------|------------|")

    for name in sorted(lineage_map.keys()):
        lineage = lineage_map[name]
        layer = lineage.layer or "-"
        upstream = ", ".join(lineage.upstream[:3]) or "-"
        if len(lineage.upstream) > 3:
            upstream += "..."
        downstream = ", ".join(lineage.downstream[:3]) or "-"
        if len(lineage.downstream) > 3:
            downstream += "..."
        sections.append(f"| `{name}` | {layer} | {upstream} | {downstream} |")
    sections.append("")

    return "\n".join(sections)
