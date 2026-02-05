"""🎯 Pipeline Decorators - Python-based pipeline definitions.

Use decorators for pipelines that need complex Python logic,
especially for ingestion (bronze layer).

Example:
    from ratatouille import pipeline

    @pipeline(
        name="ingest_sales",
        layer="bronze",
        schedule="0 * * * *",  # Hourly
    )
    def ingest_sales():
        files = rat.ls("landing/sales/*.xlsx")
        for f in files:
            df = parse_excel(f)
            rat.append("bronze.raw_sales", df)
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, Literal


def pipeline(
    name: str | None = None,
    layer: Literal["bronze", "silver", "gold"] = "bronze",
    schedule: str | None = None,
    merge_keys: list[str] | None = None,
    partition_by: list[str] | None = None,
    owner: str | None = None,
    description: str | None = None,
    tags: dict[str, str] | None = None,
) -> Callable:
    """Decorator to define a Python pipeline.

    Args:
        name: Pipeline name (default: function name)
        layer: Medallion layer (bronze, silver, gold)
        schedule: Cron schedule expression (optional)
        merge_keys: Unique keys for merge/upsert (optional)
        partition_by: Partition columns (optional)
        owner: Owner email or team (optional)
        description: Pipeline description (optional)
        tags: Additional tags for organization (optional)

    Returns:
        Decorated function with pipeline metadata

    Example:
        @pipeline(name="ingest_sales", layer="bronze", schedule="@hourly")
        def ingest_sales():
            # Ingestion logic here
            pass

        @pipeline(
            name="transform_sales",
            layer="silver",
            merge_keys=["txn_id"],
        )
        def transform_sales():
            # Transform logic here
            pass
    """

    def decorator(func: Callable) -> Callable:
        # Store metadata on the function
        func._pipeline_meta = {
            "name": name or func.__name__,
            "layer": layer,
            "schedule": schedule,
            "merge_keys": merge_keys or [],
            "partition_by": partition_by or [],
            "owner": owner,
            "description": description or func.__doc__ or "",
            "tags": tags or {},
        }

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Copy metadata to wrapper
        wrapper._pipeline_meta = func._pipeline_meta
        return wrapper

    return decorator


def is_pipeline(obj: Any) -> bool:
    """Check if an object is a pipeline function."""
    return callable(obj) and hasattr(obj, "_pipeline_meta")


def get_pipeline_meta(func: Callable) -> dict:
    """Get pipeline metadata from a decorated function."""
    if not hasattr(func, "_pipeline_meta"):
        raise ValueError(f"{func.__name__} is not a pipeline function")
    return func._pipeline_meta


# Convenience decorators for specific layers


def bronze_pipeline(
    name: str | None = None,
    schedule: str | None = None,
    **kwargs,
) -> Callable:
    """Shortcut for @pipeline(layer="bronze", ...).

    Example:
        @bronze_pipeline(name="ingest_sales")
        def ingest_sales():
            pass
    """
    return pipeline(name=name, layer="bronze", schedule=schedule, **kwargs)


def silver_pipeline(
    name: str | None = None,
    merge_keys: list[str] | None = None,
    **kwargs,
) -> Callable:
    """Shortcut for @pipeline(layer="silver", ...).

    Example:
        @silver_pipeline(name="clean_sales", merge_keys=["txn_id"])
        def clean_sales():
            pass
    """
    return pipeline(name=name, layer="silver", merge_keys=merge_keys, **kwargs)


def gold_pipeline(
    name: str | None = None,
    **kwargs,
) -> Callable:
    """Shortcut for @pipeline(layer="gold", ...).

    Example:
        @gold_pipeline(name="sales_kpis")
        def compute_kpis():
            pass
    """
    return pipeline(name=name, layer="gold", **kwargs)
