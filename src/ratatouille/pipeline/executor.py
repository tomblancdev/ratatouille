"""⚡ Pipeline Executor - Run pipelines and track results.

Handles:
- Compiling SQL templates
- Executing queries via DuckDB
- Tracking watermarks for incremental pipelines
- Recording lineage
- Reporting metrics
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from ratatouille.engine.duckdb import DuckDBEngine
    from ratatouille.workspace.manager import Workspace

from .loader import LoadedPipeline
from .parser import SQLParser
from .incremental import WatermarkTracker, compute_watermark


@dataclass
class PipelineResult:
    """Result of executing a pipeline."""

    name: str
    success: bool
    started_at: datetime
    finished_at: datetime
    duration_ms: int

    # Row counts
    rows_read: int = 0
    rows_written: int = 0

    # Incremental info
    is_incremental: bool = False
    watermark_column: str | None = None
    watermark_value: Any = None

    # Error info
    error: str | None = None

    # Output path
    output_path: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "success": self.success,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_ms": self.duration_ms,
            "rows_read": self.rows_read,
            "rows_written": self.rows_written,
            "is_incremental": self.is_incremental,
            "watermark_column": self.watermark_column,
            "watermark_value": str(self.watermark_value) if self.watermark_value else None,
            "error": self.error,
            "output_path": self.output_path,
        }


class PipelineExecutor:
    """Execute pipelines within a workspace context.

    Example:
        executor = PipelineExecutor(workspace)
        result = executor.run(pipeline)

        # Run all pipelines in order
        results = executor.run_all()
    """

    def __init__(self, workspace: "Workspace"):
        self.workspace = workspace
        self.engine = workspace.get_engine()
        self.parser = SQLParser(workspace)
        self.watermarks = WatermarkTracker(workspace.path)

    def run(
        self,
        pipeline: LoadedPipeline,
        full_refresh: bool = False,
    ) -> PipelineResult:
        """Execute a single pipeline.

        Args:
            pipeline: LoadedPipeline to execute
            full_refresh: Force full refresh (ignore incremental)

        Returns:
            PipelineResult with execution details
        """
        started_at = datetime.utcnow()
        start_time = time.time()

        try:
            if pipeline.pipeline_type == "sql":
                result = self._run_sql_pipeline(pipeline, full_refresh)
            else:
                result = self._run_python_pipeline(pipeline)

            duration_ms = int((time.time() - start_time) * 1000)
            return PipelineResult(
                name=pipeline.name,
                success=True,
                started_at=started_at,
                finished_at=datetime.utcnow(),
                duration_ms=duration_ms,
                **result,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return PipelineResult(
                name=pipeline.name,
                success=False,
                started_at=started_at,
                finished_at=datetime.utcnow(),
                duration_ms=duration_ms,
                error=str(e),
            )

    def _run_sql_pipeline(
        self,
        pipeline: LoadedPipeline,
        full_refresh: bool,
    ) -> dict:
        """Execute a SQL pipeline."""
        parsed = pipeline.parsed
        if parsed is None:
            raise ValueError(f"Pipeline {pipeline.name} has no parsed SQL")

        # Determine if incremental
        is_incremental = parsed.is_incremental and not full_refresh

        # Get watermarks for incremental
        watermarks = {}
        watermark_column = None
        if is_incremental:
            watermarks = self.watermarks.get_all(pipeline.name)
            # Detect watermark column from SQL
            from .incremental import detect_watermark_column
            watermark_column = detect_watermark_column(parsed.raw_sql)

        # Compile SQL
        sql = self.parser.compile(
            parsed,
            is_incremental=is_incremental,
            watermarks=watermarks,
        )

        print(f"🔄 Running: {pipeline.name}")
        if is_incremental:
            print(f"   Mode: incremental (watermark: {watermarks})")
        else:
            print(f"   Mode: full refresh")

        # Execute query
        df = self.engine.query(sql)
        rows_read = len(df)
        print(f"   Read: {rows_read} rows")

        if df.empty:
            print(f"   ⏭️ No new data")
            return {
                "rows_read": 0,
                "rows_written": 0,
                "is_incremental": is_incremental,
            }

        # Determine output path
        output_path = self.workspace.s3_path(pipeline.layer, pipeline.name)

        # Write results
        # For incremental with unique_key, we need to merge
        if is_incremental and parsed.unique_key:
            rows_written = self._merge_write(df, output_path, parsed.unique_key)
        else:
            self.engine.write_parquet(df, output_path, partition_by=parsed.partition_by)
            rows_written = len(df)

        print(f"   Wrote: {rows_written} rows → {output_path}")

        # Update watermark
        new_watermark = None
        if is_incremental and watermark_column and watermark_column in df.columns:
            new_watermark = compute_watermark(df, watermark_column)
            if new_watermark is not None:
                self.watermarks.set(
                    pipeline.name,
                    watermark_column,
                    new_watermark,
                    row_count=rows_written,
                )
                print(f"   Watermark: {watermark_column} = {new_watermark}")

        return {
            "rows_read": rows_read,
            "rows_written": rows_written,
            "is_incremental": is_incremental,
            "watermark_column": watermark_column,
            "watermark_value": new_watermark,
            "output_path": output_path,
        }

    def _run_python_pipeline(self, pipeline: LoadedPipeline) -> dict:
        """Execute a Python pipeline."""
        if pipeline.function is None:
            raise ValueError(f"Pipeline {pipeline.name} has no function")

        print(f"🐍 Running: {pipeline.name}")

        # Execute the pipeline function
        result = pipeline.function()

        # If result is a dict, use it
        if isinstance(result, dict):
            return {
                "rows_read": result.get("rows_read", 0),
                "rows_written": result.get("rows_written", 0),
            }

        # If result is a DataFrame, we need to write it
        if isinstance(result, pd.DataFrame):
            output_path = self.workspace.s3_path(pipeline.layer, pipeline.name)
            self.engine.write_parquet(result, output_path)
            return {
                "rows_read": len(result),
                "rows_written": len(result),
                "output_path": output_path,
            }

        return {"rows_read": 0, "rows_written": 0}

    def _merge_write(
        self,
        df: pd.DataFrame,
        path: str,
        unique_key: list[str],
    ) -> int:
        """Merge new data with existing data using unique key.

        For incremental pipelines, this:
        1. Reads existing data (if any)
        2. Concatenates with new data
        3. Deduplicates by unique key (keeping latest)
        4. Writes back

        Note: This is a simple implementation. For very large tables,
        use Iceberg's native merge capabilities.
        """
        try:
            # Read existing data
            existing_df = self.engine.read_parquet(f"{path}*.parquet")
        except Exception:
            # No existing data
            self.engine.write_parquet(df, path)
            return len(df)

        # Concatenate
        combined = pd.concat([existing_df, df], ignore_index=True)

        # Deduplicate (keep last = keep new data)
        combined = combined.drop_duplicates(subset=unique_key, keep="last")

        # Write back
        self.engine.write_parquet(combined, path)

        return len(combined)

    def run_all(
        self,
        layer: str | None = None,
        full_refresh: bool = False,
    ) -> list[PipelineResult]:
        """Run all pipelines in dependency order.

        Args:
            layer: Optional layer filter
            full_refresh: Force full refresh for all pipelines

        Returns:
            List of PipelineResult for each pipeline
        """
        from .loader import discover_pipelines, topological_sort

        # Discover pipelines
        pipelines = discover_pipelines(self.workspace, layer)

        if not pipelines:
            print("⚠️ No pipelines found")
            return []

        # Sort by dependencies
        try:
            pipelines = topological_sort(pipelines)
        except ValueError as e:
            print(f"⚠️ {e}")
            # Continue with unsorted

        print(f"📋 Found {len(pipelines)} pipelines")
        print(f"   Order: {[p.name for p in pipelines]}")
        print()

        # Execute in order
        results = []
        for pipeline in pipelines:
            result = self.run(pipeline, full_refresh=full_refresh)
            results.append(result)

            if result.success:
                print(f"   ✅ {result.name}: {result.rows_written} rows in {result.duration_ms}ms")
            else:
                print(f"   ❌ {result.name}: {result.error}")

        # Summary
        success_count = sum(1 for r in results if r.success)
        total_rows = sum(r.rows_written for r in results)
        total_time = sum(r.duration_ms for r in results)

        print()
        print(f"📊 Summary: {success_count}/{len(results)} succeeded, {total_rows} rows, {total_time}ms")

        return results
