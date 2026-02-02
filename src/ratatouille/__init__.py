"""🐀 Ratatouille - Anyone Can Data!

Simple SDK usage:
    from ratatouille import rat

    df = rat.query("SELECT * FROM gold_sales_by_product")
    df = rat.read("gold/pos/sales.parquet")
    rat.write(df, "silver/pos/cleaned.parquet")
    rat.ls("gold/")
    rat.tables()
"""

__version__ = "0.1.0"

from ratatouille.sdk import rat

__all__ = ["rat", "__version__"]
