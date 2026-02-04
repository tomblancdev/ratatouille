"""🐀 [DEPRECATED] Point of Sale (POS) Sales Pipeline - Demo.

⚠️ This file uses the OLD Dagster + ClickHouse approach.
   See the new dbt-like pipelines in workspaces/default/pipelines/:
   - silver/sales.sql + sales.yaml
   - gold/daily_sales.sql + daily_sales.yaml

The new approach:
- Uses DuckDB instead of ClickHouse
- SQL files with Jinja templating
- YAML configs for schema and tests
- See docs/guides/pipelines.md for migration guide

🐀 Point of Sale (POS) Sales Pipeline - Demo.

This demonstrates the Bronze → Silver → Gold flow:
1. Generate fake POS data → Landing
2. Ingest to Bronze (raw, partitioned)
3. Clean to Silver (validated, deduplicated)
4. Aggregate to Gold (business metrics)
5. Materialize to ClickHouse (for BI tools)
"""

from dagster import asset, asset_check, AssetCheckResult, AssetExecutionContext
from faker import Faker
import pandas as pd
from datetime import datetime, timedelta
import random

from ratatouille.core import (
    get_clickhouse,
    s3_path,
    write_parquet,
    read_parquet,
    create_table_from_s3,
)
from ratatouille.core.storage import get_s3_config, _s3_url_for_clickhouse


def _ch_s3_query(path: str, query_part: str = "*") -> str:
    """Build a ClickHouse S3 query."""
    config = get_s3_config()
    url = _s3_url_for_clickhouse(path)
    return f"""
        SELECT {query_part} FROM s3(
            '{url}',
            '{config["access_key"]}',
            '{config["secret_key"]}',
            'Parquet'
        )
    """


# =============================================================================
# LANDING: Generate Sample Data
# =============================================================================

@asset(group_name="landing", description="Generate fake POS sales data")
def landing_pos_sales(context: AssetExecutionContext) -> dict:
    """Generate realistic Point of Sale data."""
    fake = Faker()
    Faker.seed(42)
    random.seed(42)

    # Products catalog
    products = [
        {"id": "PROD-001", "name": "Espresso", "category": "Coffee", "base_price": 3.50},
        {"id": "PROD-002", "name": "Latte", "category": "Coffee", "base_price": 4.50},
        {"id": "PROD-003", "name": "Cappuccino", "category": "Coffee", "base_price": 4.00},
        {"id": "PROD-004", "name": "Croissant", "category": "Pastry", "base_price": 3.00},
        {"id": "PROD-005", "name": "Muffin", "category": "Pastry", "base_price": 2.50},
        {"id": "PROD-006", "name": "Sandwich", "category": "Food", "base_price": 7.50},
        {"id": "PROD-007", "name": "Salad", "category": "Food", "base_price": 8.00},
        {"id": "PROD-008", "name": "Cookie", "category": "Pastry", "base_price": 2.00},
        {"id": "PROD-009", "name": "Smoothie", "category": "Drinks", "base_price": 5.50},
        {"id": "PROD-010", "name": "Tea", "category": "Drinks", "base_price": 3.00},
    ]

    stores = ["STORE-NYC-001", "STORE-LA-002", "STORE-CHI-003", "STORE-SF-004"]
    payment_methods = ["cash", "credit_card", "debit_card", "mobile_pay"]

    # Generate transactions
    records = []
    base_date = datetime.now() - timedelta(days=30)

    for i in range(2000):
        product = random.choice(products)
        quantity = random.randint(1, 3)
        unit_price = product["base_price"] * random.uniform(0.95, 1.05)

        records.append({
            "transaction_id": f"TXN-{i:06d}",
            "store_id": random.choice(stores),
            "product_id": product["id"],
            "product_name": product["name"],
            "category": product["category"],
            "quantity": quantity,
            "unit_price": round(unit_price, 2),
            "total_amount": round(quantity * unit_price, 2),
            "payment_method": random.choice(payment_methods),
            "customer_id": f"CUST-{random.randint(1, 500):04d}" if random.random() > 0.3 else None,
            "transaction_time": base_date + timedelta(
                days=random.randint(0, 30),
                hours=random.randint(6, 22),
                minutes=random.randint(0, 59),
            ),
        })

    df = pd.DataFrame(records)

    # Write to landing
    path = s3_path("landing", "pos", "sales.parquet")
    write_parquet(df, path)

    context.log.info(f"✅ Generated {len(df)} POS transactions → {path}")
    return {"records": len(df), "path": path}


# =============================================================================
# BRONZE: Raw Ingestion
# =============================================================================

@asset(
    group_name="bronze",
    deps=[landing_pos_sales],
    description="Ingest POS data to Bronze layer (raw, with metadata)",
)
def bronze_pos_sales(context: AssetExecutionContext) -> dict:
    """Ingest landing data to Bronze with ingestion metadata."""
    # Read from landing
    df = read_parquet(s3_path("landing", "pos", "sales.parquet"))

    # Add ingestion metadata
    df["_ingested_at"] = datetime.utcnow()
    df["_source"] = "landing/pos/sales.parquet"

    # Write to bronze
    path = s3_path("bronze", "pos", "sales.parquet")
    write_parquet(df, path)

    context.log.info(f"✅ Ingested {len(df)} records → {path}")
    return {"records": len(df), "path": path}


@asset_check(asset=bronze_pos_sales, description="Validate Bronze POS data")
def bronze_pos_sales_check() -> AssetCheckResult:
    """Check Bronze data quality."""
    df = read_parquet(s3_path("bronze", "pos", "sales.parquet"))

    checks = []

    # Row count
    if len(df) < 100:
        checks.append(f"❌ Too few rows: {len(df)}")
    else:
        checks.append(f"✅ Row count: {len(df)}")

    # Required columns
    required = ["transaction_id", "store_id", "product_id", "total_amount"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        checks.append(f"❌ Missing columns: {missing}")
    else:
        checks.append("✅ All required columns present")

    # No duplicate transaction IDs
    dups = df["transaction_id"].duplicated().sum()
    if dups > 0:
        checks.append(f"❌ Duplicate transactions: {dups}")
    else:
        checks.append("✅ No duplicate transactions")

    passed = not any("❌" in c for c in checks)
    return AssetCheckResult(passed=passed, metadata={"checks": "\n".join(checks)})


# =============================================================================
# SILVER: Cleaned Data
# =============================================================================

@asset(
    group_name="silver",
    deps=[bronze_pos_sales],
    description="Clean and validate POS data (Silver layer)",
)
def silver_pos_sales(context: AssetExecutionContext) -> dict:
    """Clean Bronze data: validate, standardize, remove bad records."""
    client = get_clickhouse()
    config = get_s3_config()
    url = _s3_url_for_clickhouse(s3_path("bronze", "pos", "sales.parquet"))

    df = client.query_df(f"""
        SELECT
            transaction_id,
            store_id,
            product_id,
            upper(product_name) as product_name,
            upper(category) as category,
            quantity,
            unit_price,
            total_amount,
            upper(payment_method) as payment_method,
            customer_id,
            transaction_time,
            _ingested_at
        FROM s3(
            '{url}',
            '{config["access_key"]}',
            '{config["secret_key"]}',
            'Parquet'
        )
        WHERE quantity > 0
          AND unit_price > 0
          AND total_amount > 0
    """)

    # Add processing metadata
    df["_processed_at"] = datetime.utcnow()

    path = s3_path("silver", "pos", "sales.parquet")
    write_parquet(df, path)

    context.log.info(f"✅ Cleaned {len(df)} records → {path}")
    return {"records": len(df), "path": path}


# =============================================================================
# GOLD: Business Aggregations
# =============================================================================

@asset(
    group_name="gold",
    deps=[silver_pos_sales],
    description="Sales by product (Gold layer)",
)
def gold_sales_by_product(context: AssetExecutionContext) -> dict:
    """Aggregate sales by product."""
    client = get_clickhouse()
    config = get_s3_config()
    url = _s3_url_for_clickhouse(s3_path("silver", "pos", "sales.parquet"))

    df = client.query_df(f"""
        SELECT
            product_id,
            product_name,
            category,
            count(*) as total_transactions,
            sum(quantity) as total_quantity,
            round(sum(total_amount), 2) as total_revenue,
            round(avg(total_amount), 2) as avg_transaction_value
        FROM s3(
            '{url}',
            '{config["access_key"]}',
            '{config["secret_key"]}',
            'Parquet'
        )
        GROUP BY product_id, product_name, category
        ORDER BY total_revenue DESC
    """)

    path = s3_path("gold", "pos", "sales_by_product.parquet")
    write_parquet(df, path)

    context.log.info(f"✅ Aggregated {len(df)} products → {path}")
    return {"records": len(df), "path": path}


@asset(
    group_name="gold",
    deps=[silver_pos_sales],
    description="Sales by store (Gold layer)",
)
def gold_sales_by_store(context: AssetExecutionContext) -> dict:
    """Aggregate sales by store."""
    client = get_clickhouse()
    config = get_s3_config()
    url = _s3_url_for_clickhouse(s3_path("silver", "pos", "sales.parquet"))

    df = client.query_df(f"""
        SELECT
            store_id,
            count(*) as total_transactions,
            sum(quantity) as total_items_sold,
            round(sum(total_amount), 2) as total_revenue,
            round(avg(total_amount), 2) as avg_transaction_value,
            count(distinct customer_id) as unique_customers
        FROM s3(
            '{url}',
            '{config["access_key"]}',
            '{config["secret_key"]}',
            'Parquet'
        )
        GROUP BY store_id
        ORDER BY total_revenue DESC
    """)

    path = s3_path("gold", "pos", "sales_by_store.parquet")
    write_parquet(df, path)

    context.log.info(f"✅ Aggregated {len(df)} stores → {path}")
    return {"records": len(df), "path": path}


@asset(
    group_name="gold",
    deps=[silver_pos_sales],
    description="Daily sales summary (Gold layer)",
)
def gold_daily_sales(context: AssetExecutionContext) -> dict:
    """Daily sales summary."""
    client = get_clickhouse()
    config = get_s3_config()
    url = _s3_url_for_clickhouse(s3_path("silver", "pos", "sales.parquet"))

    df = client.query_df(f"""
        SELECT
            toDate(transaction_time) as sale_date,
            count(*) as total_transactions,
            sum(quantity) as total_items_sold,
            round(sum(total_amount), 2) as total_revenue,
            count(distinct store_id) as active_stores
        FROM s3(
            '{url}',
            '{config["access_key"]}',
            '{config["secret_key"]}',
            'Parquet'
        )
        GROUP BY toDate(transaction_time)
        ORDER BY sale_date
    """)

    path = s3_path("gold", "pos", "daily_sales.parquet")
    write_parquet(df, path)

    context.log.info(f"✅ Aggregated {len(df)} days → {path}")
    return {"records": len(df), "path": path}


# =============================================================================
# CLICKHOUSE: Materialize Gold Tables for BI
# =============================================================================

@asset(
    group_name="clickhouse",
    deps=[gold_sales_by_product, gold_sales_by_store, gold_daily_sales],
    description="Materialize Gold tables in ClickHouse for Power BI",
)
def clickhouse_gold_tables(context: AssetExecutionContext) -> dict:
    """Create ClickHouse tables from Gold parquet files for fast BI queries."""

    tables_created = []

    # Sales by Product
    create_table_from_s3(
        table_name="gold_sales_by_product",
        s3_path=s3_path("gold", "pos", "sales_by_product.parquet"),
        order_by="product_id",
    )
    tables_created.append("gold_sales_by_product")
    context.log.info("✅ Created table: gold_sales_by_product")

    # Sales by Store
    create_table_from_s3(
        table_name="gold_sales_by_store",
        s3_path=s3_path("gold", "pos", "sales_by_store.parquet"),
        order_by="store_id",
    )
    tables_created.append("gold_sales_by_store")
    context.log.info("✅ Created table: gold_sales_by_store")

    # Daily Sales
    create_table_from_s3(
        table_name="gold_daily_sales",
        s3_path=s3_path("gold", "pos", "daily_sales.parquet"),
        order_by="sale_date",
    )
    tables_created.append("gold_daily_sales")
    context.log.info("✅ Created table: gold_daily_sales")

    context.log.info(f"✅ Materialized {len(tables_created)} tables in ClickHouse")
    return {"tables": tables_created}
