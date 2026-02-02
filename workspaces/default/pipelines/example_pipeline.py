"""🐀 Example Workspace Pipeline - Fully Documented!

This file demonstrates how to create a production-ready data pipeline
with Ratatouille. It is automatically discovered and loaded by Dagster.

📁 Location: workspaces/<workspace>/pipelines/*.py

Features demonstrated:
- Asset metadata (owners, descriptions, tags)
- Asset dependencies
- Asset checks (data quality)
- Partitioned assets
- Logging and context
- Using the Ratatouille SDK

For more info: https://docs.dagster.io/concepts/assets
"""

from dagster import (
    asset,
    asset_check,
    AssetCheckResult,
    AssetExecutionContext,
    AssetKey,
    MetadataValue,
    Output,
    DailyPartitionsDefinition,
)
import pandas as pd
from datetime import datetime, timedelta
import random

from ratatouille import rat


# =============================================================================
# 📋 CONFIGURATION
# =============================================================================

# Define who owns this pipeline (shown in Dagster UI)
# Format: email addresses or "team:<team-name>"
OWNERS = ["team:data-team", "team:workspace-default"]

# Common tags for all assets in this pipeline
COMMON_TAGS = {
    "domain": "example",
    "layer": "gold",
    "source": "generated",
}

# Partitions for time-series data (optional)
daily_partitions = DailyPartitionsDefinition(start_date="2024-01-01")


# =============================================================================
# 🥉 LANDING LAYER - Raw Data Ingestion
# =============================================================================

@asset(
    # Group assets in the Dagster UI
    group_name="example_landing",

    # Detailed description (supports markdown!)
    description="""
    ## 🎯 Generate Sample Website Analytics Data

    This asset simulates raw website analytics events that would typically
    come from a tracking system like Google Analytics or Segment.

    ### Output Schema
    | Column | Type | Description |
    |--------|------|-------------|
    | event_id | string | Unique event identifier |
    | user_id | string | Anonymous user ID |
    | event_type | string | Type of event (pageview, click, etc.) |
    | page_url | string | URL of the page |
    | timestamp | datetime | When the event occurred |
    | device | string | Device type (desktop, mobile, tablet) |
    | country | string | User's country |

    ### Notes
    - Generates 1000 sample events
    - Data is deterministic (seeded random)
    """,

    # Owners show up in Dagster UI and can receive alerts
    owners=OWNERS,

    # Tags help filter and organize assets
    tags={**COMMON_TAGS, "layer": "landing"},

    # Compute kind shows an icon in the UI
    compute_kind="python",

    # Code version - bump when logic changes (helps with caching)
    code_version="1.0.0",
)
def example_landing_events(context: AssetExecutionContext) -> Output[dict]:
    """Generate sample website analytics events."""

    # Seed for reproducibility
    random.seed(42)

    # Configuration
    n_events = 1000
    event_types = ["pageview", "click", "scroll", "form_submit", "purchase"]
    pages = ["/", "/products", "/about", "/contact", "/checkout", "/blog"]
    devices = ["desktop", "mobile", "tablet"]
    countries = ["US", "UK", "DE", "FR", "JP", "BR", "AU"]

    # Generate events
    base_date = datetime.now() - timedelta(days=7)
    events = []

    for i in range(n_events):
        events.append({
            "event_id": f"EVT-{i:06d}",
            "user_id": f"USER-{random.randint(1, 200):04d}",
            "event_type": random.choice(event_types),
            "page_url": random.choice(pages),
            "timestamp": base_date + timedelta(
                days=random.randint(0, 7),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            ),
            "device": random.choice(devices),
            "country": random.choice(countries),
            "session_duration_sec": random.randint(10, 600),
        })

    df = pd.DataFrame(events)

    # Write to S3
    path = "landing/example/events.parquet"
    rat.write(df, path)

    # Log useful info
    context.log.info(f"✅ Generated {len(df)} events")
    context.log.info(f"📁 Written to: s3://{path}")
    context.log.info(
        f"📊 Event types: {df['event_type'].value_counts().to_dict()}")

    # Return with rich metadata (shown in Dagster UI)
    return Output(
        value={"records": len(df), "path": f"s3://{path}"},
        metadata={
            "record_count": MetadataValue.int(len(df)),
            "path": MetadataValue.path(f"s3://{path}"),
            "event_types": MetadataValue.json(df["event_type"].value_counts().to_dict()),
            "date_range": MetadataValue.text(
                f"{df['timestamp'].min()} to {df['timestamp'].max()}"
            ),
            "preview": MetadataValue.md(df.head(5).to_markdown()),
        },
    )


# =============================================================================
# 🥈 SILVER LAYER - Cleaned & Validated
# =============================================================================

@asset(
    group_name="example_silver",
    description="""
    ## 🧹 Clean and Validate Events

    Transforms raw landing data into clean, validated records.

    ### Transformations
    - Remove invalid records (null user_id, future timestamps)
    - Standardize event types to uppercase
    - Add processing metadata (_processed_at)
    - Deduplicate by event_id

    ### Quality Checks
    - No null user_ids
    - No future timestamps
    - No duplicate event_ids
    """,
    owners=OWNERS,
    tags={**COMMON_TAGS, "layer": "silver"},
    compute_kind="clickhouse",
    code_version="1.0.0",
    deps=[AssetKey("example_landing_events")],  # Explicit dependency
)
def example_silver_events(context: AssetExecutionContext) -> Output[dict]:
    """Clean and validate raw events."""

    # Read from landing
    df = rat.read("landing/example/events.parquet")
    initial_count = len(df)
    context.log.info(f"📥 Read {initial_count} raw events")

    # Clean: remove nulls
    df = df.dropna(subset=["user_id", "event_id"])

    # Clean: remove future timestamps
    df = df[df["timestamp"] <= datetime.now()]

    # Standardize
    df["event_type"] = df["event_type"].str.upper()

    # Deduplicate
    df = df.drop_duplicates(subset=["event_id"])

    # Add metadata
    df["_processed_at"] = datetime.utcnow()

    # Write to silver
    path = "silver/example/events.parquet"
    rat.write(df, path)

    removed = initial_count - len(df)
    context.log.info(f"🧹 Removed {removed} invalid records")
    context.log.info(f"✅ {len(df)} clean records → s3://{path}")

    return Output(
        value={"records": len(df), "removed": removed, "path": f"s3://{path}"},
        metadata={
            "record_count": MetadataValue.int(len(df)),
            "records_removed": MetadataValue.int(removed),
            "removal_rate": MetadataValue.float(removed / initial_count if initial_count > 0 else 0),
            "path": MetadataValue.path(f"s3://{path}"),
        },
    )


@asset_check(
    asset=example_silver_events,
    description="Validate silver events data quality",
)
def check_silver_events_quality(context) -> AssetCheckResult:
    """Data quality checks for silver events."""

    df = rat.read("silver/example/events.parquet")

    checks = {
        "has_records": len(df) > 0,
        "no_null_user_ids": df["user_id"].notna().all(),
        "no_null_event_ids": df["event_id"].notna().all(),
        "no_duplicates": df["event_id"].is_unique,
        "valid_event_types": df["event_type"].isin([
            "PAGEVIEW", "CLICK", "SCROLL", "FORM_SUBMIT", "PURCHASE"
        ]).all(),
    }

    all_passed = all(checks.values())

    return AssetCheckResult(
        passed=all_passed,
        metadata={
            "checks": MetadataValue.json(checks),
            "record_count": MetadataValue.int(len(df)),
        },
    )


# =============================================================================
# 🥇 GOLD LAYER - Business Aggregations
# =============================================================================

@asset(
    group_name="example_gold",
    description="""
    ## 📊 Events by Page - Traffic Analysis

    Aggregates events by page URL to understand traffic patterns.

    ### Metrics
    - `total_events`: Total event count
    - `unique_users`: Distinct user count
    - `pageviews`: Pageview event count
    - `clicks`: Click event count
    - `avg_session_duration`: Average session duration in seconds

    ### Use Cases
    - Identify most popular pages
    - Analyze user engagement by page
    - Find pages with high bounce rates
    """,
    owners=OWNERS,
    tags={**COMMON_TAGS, "layer": "gold", "business_domain": "analytics"},
    compute_kind="clickhouse",
    code_version="1.0.0",
    deps=[AssetKey("example_silver_events")],
)
def example_gold_events_by_page(context: AssetExecutionContext) -> Output[dict]:
    """Aggregate events by page."""

    # Use ClickHouse SQL for aggregation
    df = rat.query("""
        SELECT
            page_url,
            count(*) as total_events,
            count(DISTINCT user_id) as unique_users,
            countIf(event_type = 'PAGEVIEW') as pageviews,
            countIf(event_type = 'CLICK') as clicks,
            countIf(event_type = 'PURCHASE') as purchases,
            round(avg(session_duration_sec), 1) as avg_session_duration
        FROM s3(
            'http://minio:9000/silver/example/events.parquet',
            'ratatouille', 'ratatouille123', 'Parquet'
        )
        GROUP BY page_url
        ORDER BY total_events DESC
    """)

    path = "gold/example/events_by_page.parquet"
    rat.write(df, path)

    context.log.info(f"✅ Aggregated {len(df)} pages → s3://{path}")

    return Output(
        value={"records": len(df), "path": f"s3://{path}"},
        metadata={
            "record_count": MetadataValue.int(len(df)),
            "top_page": MetadataValue.text(df.iloc[0]["page_url"] if len(df) > 0 else "N/A"),
            "total_events": MetadataValue.int(int(df["total_events"].sum())),
            "preview": MetadataValue.md(df.to_markdown(index=False)),
        },
    )


@asset(
    group_name="example_gold",
    description="""
    ## 📊 Events by Device - Platform Analysis

    Aggregates events by device type for platform insights.

    ### Metrics
    - `total_events`: Total event count
    - `unique_users`: Distinct user count
    - `conversion_rate`: Purchase events / Total events

    ### Use Cases
    - Mobile vs Desktop performance
    - Device-specific optimizations
    - Platform prioritization
    """,
    owners=OWNERS,
    tags={**COMMON_TAGS, "layer": "gold", "business_domain": "analytics"},
    compute_kind="clickhouse",
    code_version="1.0.0",
    deps=[AssetKey("example_silver_events")],
)
def example_gold_events_by_device(context: AssetExecutionContext) -> Output[dict]:
    """Aggregate events by device."""

    df = rat.query("""
        SELECT
            device,
            count(*) as total_events,
            count(DISTINCT user_id) as unique_users,
            countIf(event_type = 'PURCHASE') as purchases,
            round(countIf(event_type = 'PURCHASE') * 100.0 / count(*), 2) as conversion_rate
        FROM s3(
            'http://minio:9000/silver/example/events.parquet',
            'ratatouille', 'ratatouille123', 'Parquet'
        )
        GROUP BY device
        ORDER BY total_events DESC
    """)

    path = "gold/example/events_by_device.parquet"
    rat.write(df, path)

    context.log.info(f"✅ Aggregated {len(df)} devices → s3://{path}")

    return Output(
        value={"records": len(df), "path": f"s3://{path}"},
        metadata={
            "record_count": MetadataValue.int(len(df)),
            "preview": MetadataValue.md(df.to_markdown(index=False)),
        },
    )


# =============================================================================
# 🏠 CLICKHOUSE - Materialize for BI Tools
# =============================================================================

@asset(
    group_name="example_clickhouse",
    description="""
    ## 🏠 Materialize Gold Tables in ClickHouse

    Creates ClickHouse tables from Gold parquet files for fast BI queries.

    ### Tables Created
    - `example_events_by_page` - Traffic by page
    - `example_events_by_device` - Traffic by device

    ### Connecting from BI Tools
    - **Power BI**: ODBC driver → localhost:8123
    - **Tableau**: ClickHouse connector
    - **Grafana**: ClickHouse data source
    - **HTTP API**: `curl localhost:8123/?query=SELECT...`
    """,
    owners=OWNERS,
    tags={**COMMON_TAGS, "layer": "clickhouse", "bi_ready": "true"},
    compute_kind="clickhouse",
    code_version="1.0.0",
    deps=[
        AssetKey("example_gold_events_by_page"),
        AssetKey("example_gold_events_by_device"),
    ],
)
def example_clickhouse_tables(context: AssetExecutionContext) -> Output[dict]:
    """Materialize gold tables in ClickHouse for BI."""

    tables = []

    # Events by Page
    rat.materialize(
        "example_events_by_page",
        "gold/example/events_by_page.parquet",
        order_by="page_url",
    )
    tables.append("example_events_by_page")
    context.log.info("✅ Created: example_events_by_page")

    # Events by Device
    rat.materialize(
        "example_events_by_device",
        "gold/example/events_by_device.parquet",
        order_by="device",
    )
    tables.append("example_events_by_device")
    context.log.info("✅ Created: example_events_by_device")

    # Log all available tables
    all_tables = rat.tables()
    context.log.info(f"📋 All ClickHouse tables: {all_tables}")

    return Output(
        value={"tables_created": tables},
        metadata={
            "tables_created": MetadataValue.json(tables),
            "all_tables": MetadataValue.json(all_tables),
            "connection_info": MetadataValue.md("""
**Connect to ClickHouse:**
- Host: `localhost` (or your server IP)
- Port: `8123` (HTTP) or `9440` (Native)
- User: `ratatouille`
- Password: `ratatouille123`
- Database: `default`
            """),
        },
    )
