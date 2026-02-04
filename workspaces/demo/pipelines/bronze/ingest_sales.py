"""🐀 Bronze: POS Sales Ingestion

Generates sample Point-of-Sale transaction data.
In production, this would ingest from a POS system, CSV files, or API.
"""

from datetime import datetime, timedelta
import random

import pandas as pd

from ratatouille.pipeline import bronze_pipeline


@bronze_pipeline(
    name="raw_sales",
    schedule="@daily",
    description="Ingest POS transaction data",
    owner="data-team@acme.com",
    tags=["pos", "sales", "transactions"],
)
def ingest_sales(context):
    """Generate sample POS sales data.

    Simulates a coffee shop chain with multiple stores.
    """
    random.seed(42)

    # Product catalog
    products = [
        {"id": "PROD-001", "name": "Espresso", "category": "Coffee", "price": 3.50},
        {"id": "PROD-002", "name": "Latte", "category": "Coffee", "price": 4.50},
        {"id": "PROD-003", "name": "Cappuccino", "category": "Coffee", "price": 4.00},
        {"id": "PROD-004", "name": "Croissant", "category": "Pastry", "price": 3.00},
        {"id": "PROD-005", "name": "Muffin", "category": "Pastry", "price": 2.50},
        {"id": "PROD-006", "name": "Sandwich", "category": "Food", "price": 7.50},
        {"id": "PROD-007", "name": "Salad", "category": "Food", "price": 8.00},
        {"id": "PROD-008", "name": "Cookie", "category": "Pastry", "price": 2.00},
        {"id": "PROD-009", "name": "Smoothie", "category": "Drinks", "price": 5.50},
        {"id": "PROD-010", "name": "Tea", "category": "Drinks", "price": 3.00},
    ]

    stores = ["STORE-NYC-001", "STORE-LA-002", "STORE-CHI-003", "STORE-SF-004"]
    payment_methods = ["cash", "credit_card", "debit_card", "mobile_pay"]

    # Generate transactions
    records = []
    base_date = datetime.now() - timedelta(days=30)

    for i in range(2000):
        product = random.choice(products)
        quantity = random.randint(1, 3)
        unit_price = product["price"] * random.uniform(0.95, 1.05)

        records.append({
            "txn_id": f"TXN-{i:06d}",
            "store_id": random.choice(stores),
            "product_id": product["id"],
            "product_name": product["name"],
            "category": product["category"],
            "quantity": quantity,
            "unit_price": round(unit_price, 2),
            "payment_method": random.choice(payment_methods),
            "customer_id": f"CUST-{random.randint(1, 500):04d}" if random.random() > 0.3 else None,
            "transaction_time": base_date + timedelta(
                days=random.randint(0, 30),
                hours=random.randint(6, 22),
                minutes=random.randint(0, 59),
            ),
        })

    df = pd.DataFrame(records)

    # Add ingestion metadata
    df["_ingested_at"] = datetime.utcnow()
    df["_source"] = "pos_simulator"

    # Write to bronze layer
    context.write("bronze.raw_sales", df)
    context.log.info(f"✅ Ingested {len(df)} POS transactions")

    return {"record_count": len(df), "stores": len(stores), "products": len(products)}
