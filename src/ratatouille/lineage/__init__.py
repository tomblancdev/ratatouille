"""🔗 Lineage Tracking - Data flow visibility.

TODO: Implement lineage tracking.

Planned features:
- LineageTracker: Record source → target relationships
- LineageGraph: Query and visualize data flow
- Impact analysis: What depends on what?

For now, dependencies are tracked via:
- {{ ref('table') }} calls in SQL pipelines
- Pipeline DAG in loader.py
"""

# TODO: Implement when needed
# from .tracker import LineageTracker, record_transform
# from .graph import LineageGraph

__all__: list[str] = []
