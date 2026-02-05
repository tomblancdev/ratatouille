"""🔗 Lineage Parser - Extract and visualize pipeline dependencies.

Parses SQL files to identify:
- {{ ref('table') }} calls for upstream dependencies
- Generates Mermaid diagrams for lineage visualization

Example:
    sql = '''
    SELECT *
    FROM {{ ref('bronze.raw_sales') }}
    JOIN {{ ref('bronze.raw_stores') }} ON ...
    '''

    lineage = extract_lineage(sql, pipeline_name="silver.sales")
    # Returns:
    # LineageInfo(
    #   pipeline="silver.sales",
    #   upstream=["bronze.raw_sales", "bronze.raw_stores"],
    #   mermaid="flowchart LR\\n    bronze.raw_sales --> silver.sales\\n    bronze.raw_stores --> silver.sales"
    # )
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LineageInfo:
    """Pipeline lineage information."""

    pipeline: str
    layer: str | None = None
    upstream: list[str] = field(default_factory=list)
    downstream: list[str] = field(
        default_factory=list
    )  # Populated from full workspace scan

    def to_mermaid(self, title: str | None = None) -> str:
        """Generate a Mermaid flowchart of the lineage.

        Args:
            title: Optional title for the diagram

        Returns:
            Mermaid diagram as string
        """
        lines = ["```mermaid", "flowchart LR"]

        if title:
            lines.insert(1, f"    subgraph {title}")

        # Add upstream connections
        for upstream in sorted(self.upstream):
            upstream_display = self._format_node(upstream)
            pipeline_display = self._format_node(self.pipeline)
            lines.append(f"    {upstream_display} --> {pipeline_display}")

        # Add downstream connections
        for downstream in sorted(self.downstream):
            pipeline_display = self._format_node(self.pipeline)
            downstream_display = self._format_node(downstream)
            lines.append(f"    {pipeline_display} --> {downstream_display}")

        if title:
            lines.append("    end")

        lines.append("```")
        return "\n".join(lines)

    def _format_node(self, name: str) -> str:
        """Format a node name for Mermaid (handle dots and special chars)."""
        # Replace dots with underscores for Mermaid node IDs
        node_id = name.replace(".", "_").replace("-", "_")
        # Use display name with original format
        return f'{node_id}["{name}"]'

    def has_dependencies(self) -> bool:
        """Check if this pipeline has any dependencies."""
        return bool(self.upstream or self.downstream)


class LineageParser:
    """Parse SQL files to extract lineage information.

    Identifies dependencies from:
    1. {{ ref('table') }} template calls
    2. {{ ref("table") }} template calls (double quotes)
    """

    # Pattern to match ref() calls
    REF_PATTERN = re.compile(r"\{\{\s*ref\(['\"]([^'\"]+)['\"]\)\s*\}\}")

    def __init__(self) -> None:
        self._lineage_cache: dict[str, LineageInfo] = {}

    def parse_file(
        self, path: Path | str, pipeline_name: str | None = None
    ) -> LineageInfo:
        """Parse a SQL file and extract lineage.

        Args:
            path: Path to the SQL file
            pipeline_name: Name of this pipeline (default: derived from path)

        Returns:
            LineageInfo with upstream dependencies
        """
        path = Path(path)

        if pipeline_name is None:
            pipeline_name = self._derive_pipeline_name(path)

        with open(path) as f:
            sql = f.read()

        return self.parse_string(sql, pipeline_name)

    def parse_string(self, sql: str, pipeline_name: str) -> LineageInfo:
        """Parse SQL string and extract lineage.

        Args:
            sql: SQL content
            pipeline_name: Name of this pipeline

        Returns:
            LineageInfo with upstream dependencies
        """
        upstream = self._extract_refs(sql)

        # Determine layer from pipeline name
        layer = None
        if "." in pipeline_name:
            layer = pipeline_name.split(".")[0]
        elif "/" in pipeline_name:
            parts = pipeline_name.split("/")
            if len(parts) >= 2:
                layer = parts[-2]

        return LineageInfo(
            pipeline=pipeline_name,
            layer=layer,
            upstream=upstream,
        )

    def _extract_refs(self, sql: str) -> list[str]:
        """Extract table references from {{ ref() }} calls."""
        refs = self.REF_PATTERN.findall(sql)
        # Return unique refs in order of appearance
        seen = set()
        unique_refs = []
        for ref in refs:
            if ref not in seen:
                seen.add(ref)
                unique_refs.append(ref)
        return unique_refs

    def _derive_pipeline_name(self, path: Path) -> str:
        """Derive pipeline name from file path.

        Examples:
            pipelines/silver/sales/pipeline.sql -> silver.sales
            pipelines/gold/daily_sales.sql -> gold.daily_sales
        """
        parts = path.parts

        # Find 'pipelines' in path
        try:
            idx = parts.index("pipelines")
            remaining = parts[idx + 1 :]

            if len(remaining) >= 2:
                layer = remaining[0]  # bronze, silver, gold
                # Handle both silver/sales.sql and silver/sales/pipeline.sql
                if remaining[-1] == "pipeline.sql":
                    name = remaining[-2]
                else:
                    name = remaining[-1].replace(".sql", "")
                return f"{layer}.{name}"
        except (ValueError, IndexError):
            pass

        # Fallback to filename without extension
        return path.stem

    def build_workspace_lineage(self, workspace_path: Path) -> dict[str, LineageInfo]:
        """Build complete lineage for all pipelines in a workspace.

        Args:
            workspace_path: Path to workspace root

        Returns:
            Dict mapping pipeline names to their LineageInfo
        """
        pipelines_dir = workspace_path / "pipelines"
        if not pipelines_dir.exists():
            return {}

        lineage_map: dict[str, LineageInfo] = {}

        # Find all SQL files
        for sql_file in pipelines_dir.rglob("*.sql"):
            # Skip test files
            if "tests" in sql_file.parts:
                continue

            lineage = self.parse_file(sql_file)
            lineage_map[lineage.pipeline] = lineage

        # Build downstream relationships
        for pipeline_name, lineage in lineage_map.items():
            for upstream in lineage.upstream:
                if upstream in lineage_map:
                    lineage_map[upstream].downstream.append(pipeline_name)

        self._lineage_cache = lineage_map
        return lineage_map


def extract_lineage(sql: str | Path, pipeline_name: str) -> LineageInfo:
    """Convenience function to extract lineage from SQL.

    Args:
        sql: SQL string or path to SQL file
        pipeline_name: Name of the pipeline

    Returns:
        LineageInfo with upstream dependencies
    """
    parser = LineageParser()

    if isinstance(sql, Path):
        return parser.parse_file(sql, pipeline_name)
    if isinstance(sql, str) and Path(sql).exists():
        return parser.parse_file(sql, pipeline_name)
    return parser.parse_string(sql, pipeline_name)


def generate_workspace_lineage_diagram(workspace_path: Path) -> str:
    """Generate a complete lineage diagram for the workspace.

    Args:
        workspace_path: Path to workspace root

    Returns:
        Mermaid diagram as string
    """
    parser = LineageParser()
    lineage_map = parser.build_workspace_lineage(workspace_path)

    if not lineage_map:
        return "```mermaid\nflowchart LR\n    empty[No pipelines found]\n```"

    lines = ["```mermaid", "flowchart TD"]

    # Group by layer
    layers = {"bronze": [], "silver": [], "gold": []}
    for _name, lineage in lineage_map.items():
        layer = lineage.layer or "other"
        if layer in layers:
            layers[layer].append(lineage)

    # Generate subgraphs for each layer
    for layer, pipelines in layers.items():
        if pipelines:
            lines.append(f"    subgraph {layer.upper()}")
            for lineage in pipelines:
                node_id = lineage.pipeline.replace(".", "_").replace("-", "_")
                lines.append(f'        {node_id}["{lineage.pipeline}"]')
            lines.append("    end")

    # Add all edges
    for lineage in lineage_map.values():
        pipeline_id = lineage.pipeline.replace(".", "_").replace("-", "_")
        for upstream in lineage.upstream:
            upstream_id = upstream.replace(".", "_").replace("-", "_")
            lines.append(f"    {upstream_id} --> {pipeline_id}")

    lines.append("```")
    return "\n".join(lines)
