"""🐀 Storage utilities - ClickHouse + S3/MinIO."""

import os
from io import BytesIO
import clickhouse_connect
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import boto3
from botocore.client import Config


def _require_env(name: str) -> str:
    """Get required environment variable or raise clear error."""
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(
            f"Missing required environment variable: {name}\n"
            f"Make sure you have a .env file. See .env.example for reference."
        )
    return value


def get_s3_config() -> dict:
    """Get S3 configuration from environment."""
    return {
        "endpoint": _require_env("S3_ENDPOINT"),
        "access_key": _require_env("S3_ACCESS_KEY"),
        "secret_key": _require_env("S3_SECRET_KEY"),
    }


def get_clickhouse_config() -> dict:
    """Get ClickHouse configuration from environment."""
    return {
        "host": _require_env("CLICKHOUSE_HOST"),
        "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
        "user": _require_env("CLICKHOUSE_USER"),
        "password": _require_env("CLICKHOUSE_PASSWORD"),
    }


def get_clickhouse():
    """Get a ClickHouse client connection."""
    config = get_clickhouse_config()
    return clickhouse_connect.get_client(
        host=config["host"],
        port=config["port"],
        username=config["user"],
        password=config["password"],
    )


def get_s3_client():
    """Get a boto3 S3 client configured for MinIO."""
    config = get_s3_config()
    return boto3.client(
        "s3",
        endpoint_url=config["endpoint"],
        aws_access_key_id=config["access_key"],
        aws_secret_access_key=config["secret_key"],
        config=Config(signature_version="s3v4"),
    )


def read_file(path: str) -> tuple[BytesIO, str]:
    """Read any file from S3 and return its content + type.

    Args:
        path: S3 path (s3://bucket/key)

    Returns:
        tuple of (BytesIO with file content, file extension like 'xlsx', 'csv', 'png')

    Example:
        data, file_type = read_file("s3://landing/data.xlsx")
        if file_type == "xlsx":
            df = pd.read_excel(data)
        elif file_type == "csv":
            df = pd.read_csv(data)
    """
    s3 = get_s3_client()

    # Parse s3://bucket/key
    if path.startswith("s3://"):
        path_parts = path[5:].split("/", 1)
        bucket = path_parts[0]
        key = path_parts[1] if len(path_parts) > 1 else ""
    else:
        raise ValueError(f"Path must start with s3://: {path}")

    # Get file extension
    file_type = key.rsplit(".", 1)[-1].lower() if "." in key else ""

    # Download file
    response = s3.get_object(Bucket=bucket, Key=key)
    data = BytesIO(response["Body"].read())

    return data, file_type


def s3_path(bucket: str, *parts: str) -> str:
    """Build an S3 path.

    Example:
        s3_path("bronze", "pos", "sales.parquet")
        → "s3://bronze/pos/sales.parquet"
    """
    path = "/".join(str(p) for p in parts if p)
    return f"s3://{bucket}/{path}" if path else f"s3://{bucket}"


def _s3_url_for_clickhouse(path: str) -> str:
    """Convert s3:// path to http URL for ClickHouse."""
    config = get_s3_config()
    # s3://bucket/key → http://minio:9000/bucket/key
    if path.startswith("s3://"):
        path = path[5:]  # Remove s3://
    return f"{config['endpoint']}/{path}"


def read_parquet(path: str) -> pd.DataFrame:
    """Read a Parquet file from S3 into a DataFrame using ClickHouse."""
    client = get_clickhouse()
    config = get_s3_config()
    url = _s3_url_for_clickhouse(path)

    query = f"""
        SELECT * FROM s3(
            '{url}',
            '{config["access_key"]}',
            '{config["secret_key"]}',
            'Parquet'
        )
    """
    return client.query_df(query)


def write_parquet(df: pd.DataFrame, path: str) -> str:
    """Write a DataFrame to S3 as Parquet.

    Uses PyArrow for direct S3 writes (more reliable than ClickHouse INSERT INTO s3).
    Returns the path written to.
    """
    s3 = get_s3_client()

    # Parse s3://bucket/key
    if path.startswith("s3://"):
        path_parts = path[5:].split("/", 1)
        bucket = path_parts[0]
        key = path_parts[1] if len(path_parts) > 1 else ""
    else:
        raise ValueError(f"Path must start with s3://: {path}")

    # Convert to Arrow and write to bytes
    table = pa.Table.from_pandas(df)
    buffer = BytesIO()
    pq.write_table(table, buffer)
    buffer.seek(0)

    # Upload to S3
    s3.put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())

    return f"s3://{bucket}/{key}"


def query(sql: str) -> pd.DataFrame:
    """Execute a SQL query on ClickHouse and return a DataFrame.

    Example:
        df = query("SELECT * FROM s3('http://minio:9000/gold/pos/*.parquet', ...)")
    """
    client = get_clickhouse()
    return client.query_df(sql)


def query_s3(path: str, sql_where: str = "", limit: int | None = None) -> pd.DataFrame:
    """Query Parquet files from S3 using ClickHouse.

    Example:
        df = query_s3("s3://gold/pos/sales.parquet", "WHERE total > 100", limit=10)
    """
    client = get_clickhouse()
    config = get_s3_config()
    url = _s3_url_for_clickhouse(path)

    query = f"""
        SELECT * FROM s3(
            '{url}',
            '{config["access_key"]}',
            '{config["secret_key"]}',
            'Parquet'
        )
        {sql_where}
        {"LIMIT " + str(limit) if limit else ""}
    """
    return client.query_df(query)


def create_table_from_s3(
    table_name: str,
    s3_path: str,
    engine: str = "MergeTree",
    order_by: str = "tuple()",
) -> None:
    """Create a ClickHouse table from S3 Parquet data.

    This materializes the data in ClickHouse for fast queries.
    Ideal for Gold layer tables that need to be queried by BI tools.

    Example:
        create_table_from_s3(
            "gold_sales_by_product",
            "s3://gold/pos/sales_by_product.parquet",
            order_by="product_id"
        )
    """
    client = get_clickhouse()
    config = get_s3_config()
    url = _s3_url_for_clickhouse(s3_path)

    # Create table with schema inferred from Parquet
    client.command(f"DROP TABLE IF EXISTS {table_name}")

    query = f"""
        CREATE TABLE {table_name}
        ENGINE = {engine}
        ORDER BY {order_by}
        SETTINGS allow_nullable_key = 1
        AS SELECT * FROM s3(
            '{url}',
            '{config["access_key"]}',
            '{config["secret_key"]}',
            'Parquet'
        )
    """
    client.command(query)


def list_files(bucket: str, prefix: str = "") -> list[str]:
    """List files in an S3 bucket."""
    s3 = get_s3_client()
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    if "Contents" not in response:
        return []

    return [obj["Key"] for obj in response["Contents"]]


def list_tables() -> list[str]:
    """List all tables in ClickHouse."""
    client = get_clickhouse()
    result = client.query("SHOW TABLES")
    return [row[0] for row in result.result_rows]
