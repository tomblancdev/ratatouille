# Lineage: Device Metrics

> 🐀 Auto-generated | Layer: `gold` | Last updated: 2026-02-05

## Summary

- **Pipeline:** `gold.device_metrics`
- **Layer:** gold
- **Upstream dependencies:** 1
- **Downstream consumers:** 0

## Pipeline Diagram

```mermaid
flowchart LR
    silver_events["silver.events"] --> gold_device_metrics["gold.device_metrics"]
```

## Upstream Dependencies

This pipeline reads from:

| Source | Layer | Description |
|--------|-------|-------------|
| `silver.events` | SILVER | - |

## Downstream Consumers

*No downstream pipelines consume this data (yet).*

## Impact Analysis

This pipeline has no downstream dependencies. Changes can be made safely.
