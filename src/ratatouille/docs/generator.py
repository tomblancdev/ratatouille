"""📚 Documentation Generator - Orchestrate doc generation for pipelines.

Generates complete documentation for pipelines including:
- README.md
- docs/data_dictionary.md
- docs/business_rules.md
- docs/lineage.md

Usage:
    generator = DocumentationGenerator(workspace_path)
    generator.generate_all()
    # or
    generator.generate_for_pipeline("silver/sales")
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from .models import EnhancedPipelineConfig, load_enhanced_config
from .parsers.lineage import LineageInfo, LineageParser
from .parsers.sql_comments import extract_business_rules
from .templates import (
    generate_business_rules,
    generate_data_dictionary,
    generate_lineage,
    generate_readme,
)


@dataclass
class GenerationResult:
    """Result of generating documentation for a pipeline."""

    pipeline: str
    layer: str
    files_created: list[str] = field(default_factory=list)
    files_updated: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class DocumentationGenerator:
    """Generate documentation for all pipelines in a workspace.

    Supports:
    - Single pipeline generation
    - Workspace-wide generation
    - Manual content preservation
    - Lineage tracking across pipelines
    """

    def __init__(
        self,
        workspace_path: Path | str,
        console: Console | None = None,
    ) -> None:
        """Initialize the generator.

        Args:
            workspace_path: Path to the workspace root
            console: Rich console for output (optional)
        """
        self.workspace_path = Path(workspace_path)
        self.console = console or Console()
        self._lineage_parser = LineageParser()
        self._lineage_map: dict[str, LineageInfo] = {}

    def generate_all(self) -> list[GenerationResult]:
        """Generate documentation for all pipelines in the workspace.

        Returns:
            List of GenerationResult for each pipeline
        """
        results = []

        # Build complete lineage map first
        self._lineage_map = self._lineage_parser.build_workspace_lineage(
            self.workspace_path
        )

        # Find all pipelines
        for pipeline_path in self._discover_pipelines():
            result = self._generate_for_path(pipeline_path)
            results.append(result)

        return results

    def generate_for_pipeline(self, pipeline: str) -> GenerationResult:
        """Generate documentation for a specific pipeline.

        Args:
            pipeline: Pipeline path relative to pipelines/ (e.g., "silver/sales")

        Returns:
            GenerationResult
        """
        # Build lineage map if not already done
        if not self._lineage_map:
            self._lineage_map = self._lineage_parser.build_workspace_lineage(
                self.workspace_path
            )

        pipeline_path = self.workspace_path / "pipelines" / pipeline
        if not pipeline_path.exists():
            return GenerationResult(
                pipeline=pipeline,
                layer="unknown",
                errors=[f"Pipeline not found: {pipeline_path}"],
            )

        return self._generate_for_path(pipeline_path)

    def _discover_pipelines(self) -> Generator[Path, None, None]:
        """Discover all pipeline directories in the workspace.

        Looks for directories or files with config.yaml or pipeline.sql.
        """
        pipelines_dir = self.workspace_path / "pipelines"
        if not pipelines_dir.exists():
            return

        # Pattern 1: pipelines/{layer}/{name}/config.yaml (folder-based)
        for config_file in pipelines_dir.rglob("config.yaml"):
            # Skip test configs
            if "tests" in config_file.parts:
                continue
            yield config_file.parent

        # Pattern 2: pipelines/{layer}/{name}.yaml (file-based, but we need the SQL file)
        for layer_dir in pipelines_dir.iterdir():
            if not layer_dir.is_dir():
                continue
            for sql_file in layer_dir.glob("*.sql"):
                # Skip if already covered by folder-based pattern
                folder_path = layer_dir / sql_file.stem
                if folder_path.exists() and (folder_path / "config.yaml").exists():
                    continue
                yield sql_file.parent / sql_file.stem

    def _generate_for_path(self, pipeline_path: Path) -> GenerationResult:
        """Generate documentation for a pipeline at the given path.

        Args:
            pipeline_path: Path to pipeline directory or file stem

        Returns:
            GenerationResult
        """
        # Determine layer and name from path
        parts = pipeline_path.relative_to(self.workspace_path / "pipelines").parts
        if len(parts) >= 2:
            layer = parts[0]
            name = parts[1] if len(parts) == 2 else parts[-1]
        else:
            layer = "unknown"
            name = pipeline_path.name

        result = GenerationResult(pipeline=f"{layer}/{name}", layer=layer)

        try:
            # Load configuration
            config = self._load_config(pipeline_path)

            # Get lineage
            pipeline_key = f"{layer}.{name}"
            lineage = self._lineage_map.get(
                pipeline_key, LineageInfo(pipeline=pipeline_key)
            )

            # Load SQL for rule extraction
            sql_rules = []
            sql_file = self._find_sql_file(pipeline_path)
            if sql_file and sql_file.exists():
                sql_rules = extract_business_rules(sql_file)
                # Also update lineage from SQL if not already done
                if not lineage.upstream:
                    lineage = self._lineage_parser.parse_file(sql_file, pipeline_key)

            # Ensure docs directory exists
            docs_dir = (
                pipeline_path / "docs"
                if pipeline_path.is_dir()
                else pipeline_path.parent / name / "docs"
            )
            docs_dir.mkdir(parents=True, exist_ok=True)

            # Ensure pipeline directory exists for folder-based structure
            if not pipeline_path.is_dir():
                pipeline_path = pipeline_path.parent / name
                pipeline_path.mkdir(parents=True, exist_ok=True)

            # Generate README
            readme_path = pipeline_path / "README.md"
            existing_readme = readme_path.read_text() if readme_path.exists() else None
            readme_content = generate_readme(
                config, name, layer, lineage, existing_readme
            )
            self._write_file(readme_path, readme_content, result)

            # Generate data dictionary
            dict_path = docs_dir / "data_dictionary.md"
            dict_content = generate_data_dictionary(config, name, layer)
            self._write_file(dict_path, dict_content, result)

            # Generate business rules
            rules_path = docs_dir / "business_rules.md"
            rules_content = generate_business_rules(config, name, layer, sql_rules)
            self._write_file(rules_path, rules_content, result)

            # Generate lineage
            lineage_path = docs_dir / "lineage.md"
            lineage_content = generate_lineage(lineage, name, layer)
            self._write_file(lineage_path, lineage_content, result)

        except Exception as e:
            result.errors.append(str(e))

        return result

    def _load_config(self, pipeline_path: Path) -> EnhancedPipelineConfig:
        """Load configuration for a pipeline."""
        # Try config.yaml in directory
        if pipeline_path.is_dir():
            config_path = pipeline_path / "config.yaml"
            if config_path.exists():
                return load_enhanced_config(config_path)

        # Try {name}.yaml alongside SQL file
        if not pipeline_path.is_dir():
            yaml_path = pipeline_path.with_suffix(".yaml")
            if yaml_path.exists():
                return load_enhanced_config(yaml_path)

        # Return empty config
        return EnhancedPipelineConfig()

    def _find_sql_file(self, pipeline_path: Path) -> Path | None:
        """Find the SQL file for a pipeline."""
        if pipeline_path.is_dir():
            # Check for pipeline.sql in directory
            sql_file = pipeline_path / "pipeline.sql"
            if sql_file.exists():
                return sql_file
            # Check for {name}.sql
            for sql in pipeline_path.glob("*.sql"):
                if "test" not in sql.name.lower():
                    return sql
        else:
            # File-based: {name}.sql
            sql_file = pipeline_path.with_suffix(".sql")
            if sql_file.exists():
                return sql_file

        return None

    def _write_file(self, path: Path, content: str, result: GenerationResult) -> None:
        """Write content to a file and track in result."""
        existed = path.exists()
        path.write_text(content)

        if existed:
            result.files_updated.append(str(path.relative_to(self.workspace_path)))
        else:
            result.files_created.append(str(path.relative_to(self.workspace_path)))


def generate_workspace_docs(workspace_path: Path | str) -> list[GenerationResult]:
    """Convenience function to generate all docs for a workspace.

    Args:
        workspace_path: Path to workspace root

    Returns:
        List of GenerationResult
    """
    generator = DocumentationGenerator(workspace_path)
    return generator.generate_all()
