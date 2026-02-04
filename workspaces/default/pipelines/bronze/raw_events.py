"""🐀 Bronze: Raw Events Ingestion

Generates sample website analytics events for demonstration.
This replaces the old example_pipeline.py with the new @pipeline decorator.
"""

from datetime import datetime, timedelta
import random

import pandas as pd

from ratatouille.pipeline import bronze_pipeline


@bronze_pipeline(
    name="raw_events",
    schedule="@daily",
    description="Generate sample website analytics events",
    owner="data-team@acme.com",
    tags=["demo", "events", "website"],
)
def ingest_raw_events(context):
    """Generate sample website analytics events.

    This simulates raw events from a tracking system like
    Google Analytics or Segment.
    """
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

    # Add ingestion metadata
    df["_ingested_at"] = datetime.utcnow()
    df["_source"] = "demo_generator"

    # Write to bronze layer
    context.write("bronze.raw_events", df)
    context.log.info(f"✅ Generated {len(df)} events")

    return {
        "record_count": len(df),
        "event_types": df["event_type"].value_counts().to_dict(),
        "date_range": f"{df['timestamp'].min()} to {df['timestamp'].max()}",
    }
