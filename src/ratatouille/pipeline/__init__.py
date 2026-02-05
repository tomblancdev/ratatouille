"""🔄 Pipeline Framework - dbt-like SQL + YAML + Python.

Supports:
- SQL pipelines with {{ ref() }} and {% if %} templating
- YAML configuration for schema, tests, freshness
- Python pipelines for complex ingestion logic
- Incremental processing with watermarks

Example SQL Pipeline:
    -- pipelines/silver/sales.sql
    -- @name: silver_sales
    -- @materialized: incremental
    -- @unique_key: txn_id

    SELECT *
    FROM {{ ref('bronze.raw_sales') }}
    WHERE quantity > 0
    {% if is_incremental() %}
      AND _ingested_at > '{{ watermark("_ingested_at") }}'
    {% endif %}

Example Python Pipeline:
    from ratatouille import pipeline

    @pipeline(name="ingest_sales", layer="bronze")
    def ingest_sales():
        for f in rat.ls("landing/*.xlsx"):
            df = parse_excel(f)
            rat.append("bronze.raw_sales", df)
"""

from .parser import SQLParser, ParsedPipeline
from .config import PipelineConfig, ColumnConfig, load_pipeline_config
from .loader import (
    LoadedPipeline,
    load_pipeline,
    discover_pipelines,
    build_dag,
    topological_sort,
)
from .executor import PipelineExecutor, PipelineResult
from .incremental import WatermarkTracker, WatermarkState, compute_watermark
from .decorators import (
    pipeline,
    is_pipeline,
    get_pipeline_meta,
    bronze_pipeline,
    silver_pipeline,
    gold_pipeline,
)

__all__ = [
    # Parser
    "SQLParser",
    "ParsedPipeline",
    # Config
    "PipelineConfig",
    "ColumnConfig",
    "load_pipeline_config",
    # Loader
    "LoadedPipeline",
    "load_pipeline",
    "discover_pipelines",
    "build_dag",
    "topological_sort",
    # Executor
    "PipelineExecutor",
    "PipelineResult",
    # Incremental
    "WatermarkTracker",
    "WatermarkState",
    "compute_watermark",
    # Decorators
    "pipeline",
    "is_pipeline",
    "get_pipeline_meta",
    "bronze_pipeline",
    "silver_pipeline",
    "gold_pipeline",
]
