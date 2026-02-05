"""📂 Pipeline Loader - Discover and load pipelines from workspace directories.

Supports:
- SQL pipelines (*.sql + optional *.yaml config)
- Python pipelines (*.py with @pipeline decorator)
- Auto-discovery from workspaces/*/pipelines/{bronze,silver,gold}/
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ratatouille.workspace.manager import Workspace

from .parser import SQLParser, ParsedPipeline
from .config import PipelineConfig, load_pipeline_config


@dataclass
class LoadedPipeline:
    """A fully loaded pipeline ready for execution."""

    # Identity
    name: str
    path: Path
    layer: Literal["bronze", "silver", "gold"]
    pipeline_type: Literal["sql", "python"]

    # Parsed SQL (for SQL pipelines)
    parsed: ParsedPipeline | None = None

    # Configuration (from YAML)
    config: PipelineConfig | None = None

    # Python module (for Python pipelines)
    module: object | None = None
    function: object | None = None

    @property
    def is_incremental(self) -> bool:
        """Check if this is an incremental pipeline."""
        if self.parsed:
            return self.parsed.is_incremental
        if self.config and self.config.materialized:
            return self.config.materialized == "incremental"
        return False

    @property
    def unique_key(self) -> list[str]:
        """Get unique key columns."""
        if self.config and self.config.unique_key:
            return self.config.unique_key
        if self.parsed:
            return self.parsed.unique_key
        return []

    @property
    def dependencies(self) -> list[str]:
        """Get pipeline dependencies (refs)."""
        if self.parsed:
            return self.parsed.dependencies
        return []


def load_pipeline(
    path: Path | str,
    workspace: "Workspace | None" = None,
) -> LoadedPipeline:
    """Load a single pipeline from a file.

    Args:
        path: Path to .sql or .py file
        workspace: Optional workspace for context

    Returns:
        LoadedPipeline ready for execution
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Pipeline not found: {path}")

    # Determine layer from path
    layer = _detect_layer(path)

    if path.suffix == ".sql":
        return _load_sql_pipeline(path, layer, workspace)
    elif path.suffix == ".py":
        return _load_python_pipeline(path, layer)
    else:
        raise ValueError(f"Unsupported pipeline type: {path.suffix}")


def _load_sql_pipeline(
    path: Path,
    layer: str,
    workspace: "Workspace | None",
) -> LoadedPipeline:
    """Load a SQL pipeline."""
    parser = SQLParser(workspace)
    parsed = parser.parse_file(str(path))
    config = load_pipeline_config(path)

    return LoadedPipeline(
        name=parsed.name,
        path=path,
        layer=layer,
        pipeline_type="sql",
        parsed=parsed,
        config=config,
    )


def _load_python_pipeline(path: Path, layer: str) -> LoadedPipeline:
    """Load a Python pipeline."""
    import importlib.util

    # Load module dynamically
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find pipeline function (decorated with @pipeline)
    pipeline_func = None
    pipeline_name = path.stem

    for name in dir(module):
        obj = getattr(module, name)
        if hasattr(obj, "_pipeline_meta"):
            pipeline_func = obj
            pipeline_name = obj._pipeline_meta.get("name", name)
            break

    return LoadedPipeline(
        name=pipeline_name,
        path=path,
        layer=layer,
        pipeline_type="python",
        module=module,
        function=pipeline_func,
    )


def _detect_layer(path: Path) -> Literal["bronze", "silver", "gold"]:
    """Detect medallion layer from file path."""
    path_str = str(path).lower()

    if "/bronze/" in path_str or "\\bronze\\" in path_str:
        return "bronze"
    elif "/silver/" in path_str or "\\silver\\" in path_str:
        return "silver"
    elif "/gold/" in path_str or "\\gold\\" in path_str:
        return "gold"
    else:
        # Default to bronze for ingestion
        return "bronze"


def discover_pipelines(
    workspace: "Workspace",
    layer: str | None = None,
) -> list[LoadedPipeline]:
    """Discover all pipelines in a workspace.

    Args:
        workspace: Workspace to scan
        layer: Optional layer filter (bronze, silver, gold)

    Returns:
        List of LoadedPipeline objects
    """
    pipelines = []
    pipelines_dir = workspace.path / "pipelines"

    if not pipelines_dir.exists():
        return []

    # Layers to scan
    layers = [layer] if layer else ["bronze", "silver", "gold"]

    for l in layers:
        layer_dir = pipelines_dir / l
        if not layer_dir.exists():
            continue

        # Find SQL pipelines
        for sql_file in layer_dir.glob("*.sql"):
            try:
                pipeline = load_pipeline(sql_file, workspace)
                pipelines.append(pipeline)
            except Exception as e:
                print(f"⚠️ Could not load {sql_file}: {e}")

        # Find Python pipelines
        for py_file in layer_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                pipeline = load_pipeline(py_file, workspace)
                pipelines.append(pipeline)
            except Exception as e:
                print(f"⚠️ Could not load {py_file}: {e}")

    return pipelines


def build_dag(pipelines: list[LoadedPipeline]) -> dict[str, list[str]]:
    """Build a dependency DAG from pipelines.

    Returns:
        Dict mapping pipeline name to list of dependencies
    """
    dag = {}
    for pipeline in pipelines:
        dag[pipeline.name] = pipeline.dependencies
    return dag


def topological_sort(pipelines: list[LoadedPipeline]) -> list[LoadedPipeline]:
    """Sort pipelines in dependency order.

    Returns:
        Pipelines sorted so dependencies come before dependents
    """
    # Build name -> pipeline mapping
    by_name = {p.name: p for p in pipelines}

    # Build adjacency list
    dag = build_dag(pipelines)

    # Kahn's algorithm for topological sort
    in_degree = {name: 0 for name in dag}
    for deps in dag.values():
        for dep in deps:
            if dep in in_degree:
                in_degree[dep] += 1

    # Start with nodes that have no dependencies
    queue = [name for name, degree in in_degree.items() if degree == 0]
    result = []

    while queue:
        name = queue.pop(0)
        if name in by_name:
            result.append(by_name[name])

        for other, deps in dag.items():
            if name in deps:
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    queue.append(other)

    if len(result) != len(pipelines):
        # Cycle detected
        missing = set(by_name.keys()) - {p.name for p in result}
        raise ValueError(f"Circular dependency detected involving: {missing}")

    return result
