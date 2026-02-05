"""🐀 Ratatouille - Anyone Can Data!

Quick Start:
    from ratatouille import tools

    # Explore your workspace
    tools.info()                    # Workspace info
    tools.ls("bronze/")             # List files in S3
    tools.tables()                  # List all tables
    tools.schema("silver.events")   # Get table schema
    tools.preview("gold.metrics")   # Preview data

    # S3 paths
    tools.s3_uri("silver", "events")  # Get full S3 URI
    tools.tree()                      # Show folder structure

Advanced SDK:
    from ratatouille import sdk

    df = sdk.query("SELECT * FROM ...")
    sdk.run("silver.events")
    sdk.publish("my_product", "gold.metrics", "1.0.0")
"""

from ratatouille import tools

__version__ = "2.0.0"


# Import SDK (lazy to avoid heavy imports)
def __getattr__(name: str) -> object:
    if name == "sdk":
        from ratatouille.sdk import RatatouilleSDK

        return RatatouilleSDK()
    raise AttributeError(f"module 'ratatouille' has no attribute '{name}'")

__all__ = ["tools", "sdk", "__version__"]
