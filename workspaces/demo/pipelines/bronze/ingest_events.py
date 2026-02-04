"""🐀 Bronze: Web Events Ingestion

Generates sample website analytics events.
In production, this would ingest from Google Analytics, Segment, or similar.
"""

from datetime import datetime, timedelta
import random

import pandas as pd

from ratatouille.pipeline import bronze_pipeline


@bronze_pipeline(
    name="raw_events",
    schedule="@hourly",
    description="Ingest website analytics events",
    owner="data-team@acme.com",
    tags=["web", "analytics", "events"],
)
def ingest_events(context):
    """Generate sample website analytics events.

    Simulates user interactions on an e-commerce website.
    """
    random.seed(42)

    # Configuration
    n_events = 1000
    event_types = ["pageview", "click", "scroll", "form_submit", "purchase"]
    pages = ["/", "/products", "/about", "/contact", "/checkout", "/blog", "/cart"]
    devices = ["desktop", "mobile", "tablet"]
    countries = ["US", "UK", "DE", "FR", "JP", "BR", "AU", "CA"]
    browsers = ["Chrome", "Safari", "Firefox", "Edge"]

    # Generate events
    base_date = datetime.now() - timedelta(days=7)
    events = []

    for i in range(n_events):
        events.append({
            "event_id": f"EVT-{i:06d}",
            "user_id": f"USER-{random.randint(1, 200):04d}",
            "session_id": f"SESS-{random.randint(1, 500):04d}",
            "event_type": random.choice(event_types),
            "page_url": random.choice(pages),
            "referrer": random.choice([None, "google.com", "facebook.com", "twitter.com"]),
            "timestamp": base_date + timedelta(
                days=random.randint(0, 7),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            ),
            "device": random.choice(devices),
            "browser": random.choice(browsers),
            "country": random.choice(countries),
            "session_duration_sec": random.randint(10, 600),
        })

    df = pd.DataFrame(events)

    # Add ingestion metadata
    df["_ingested_at"] = datetime.utcnow()
    df["_source"] = "analytics_simulator"

    # Write to bronze layer
    context.write("bronze.raw_events", df)
    context.log.info(f"✅ Ingested {len(df)} web events")

    return {
        "record_count": len(df),
        "event_types": df["event_type"].value_counts().to_dict(),
    }
