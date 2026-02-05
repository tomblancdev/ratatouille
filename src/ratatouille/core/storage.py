"""🐀 Storage utilities - S3/MinIO operations.

Note: Query operations are now handled by DuckDB (see engine/duckdb.py).
This module provides low-level S3 operations for file management.
"""

import os
from io import BytesIO

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.client import Config


def get_s3_config() -> dict:
    """Get S3 configuration from environment."""
    return {
        "endpoint": os.getenv("S3_ENDPOINT", "http://localhost:9000"),
        "access_key": os.getenv("S3_ACCESS_KEY", "ratatouille"),
        "secret_key": os.getenv("S3_SECRET_KEY", "ratatouille123"),
    }


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


def s3_path(bucket: str, *parts: str) -> str:
    """Build an S3 path.

    Example:
        s3_path("bronze", "pos", "sales.parquet")
        → "s3://bronze/pos/sales.parquet"
    """
    path = "/".join(str(p) for p in parts if p)
    return f"s3://{bucket}/{path}" if path else f"s3://{bucket}"


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


def write_parquet(df: pd.DataFrame, path: str) -> str:
    """Write a DataFrame to S3 as Parquet.

    Uses PyArrow for direct S3 writes.
    Returns the path written to.

    Note: For DuckDB-based writes, use engine.write_parquet() instead.
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


def read_parquet(path: str) -> pd.DataFrame:
    """Read a Parquet file from S3 into a DataFrame.

    Uses PyArrow for direct S3 reads.

    Note: For DuckDB-based reads with SQL, use engine.query() instead.
    """
    data, _ = read_file(path)
    return pd.read_parquet(data)


def list_files(bucket: str, prefix: str = "") -> list[str]:
    """List files in an S3 bucket."""
    s3 = get_s3_client()
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    if "Contents" not in response:
        return []

    return [obj["Key"] for obj in response["Contents"]]


def ensure_bucket(bucket: str) -> None:
    """Ensure an S3 bucket exists, create if not."""
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(Bucket=bucket)


def delete_file(path: str) -> None:
    """Delete a file from S3."""
    s3 = get_s3_client()

    if path.startswith("s3://"):
        path_parts = path[5:].split("/", 1)
        bucket = path_parts[0]
        key = path_parts[1] if len(path_parts) > 1 else ""
    else:
        raise ValueError(f"Path must start with s3://: {path}")

    s3.delete_object(Bucket=bucket, Key=key)
