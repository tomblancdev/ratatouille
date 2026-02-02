"""🐀 Ratatouille SDK - Simple API for data operations.

Usage:
    from ratatouille import rat

    # ===================== Read Data =====================

    df = rat.df("{bronze.sales}")             # Read Iceberg table
    df = rat.df("{temp.filtered}")           # Read temp table
    rat.ice_all()                            # List all tables

    # ===================== Temp Tables (Variables) =====================

    rat.temp("clean", df)                    # Save temp table
    df = rat.temp("clean")                   # Retrieve temp table
    rat.temp_list()                          # List all temp tables
    rat.temp_drop("clean")                   # Drop temp table

    # ===================== Transforms (SQL) =====================

    # Use {namespace.table} placeholders - works with Iceberg and temp tables!
    rat.transform(
        sql=\"""
            SELECT *, price * quantity AS total
            FROM {bronze.transactions}
            WHERE quantity > 0
        \""",
        target="silver.transactions",
        merge_keys=["store_id", "date", "transaction_id"]
    )

    # ===================== Transforms (Ibis - Pythonic) =====================

    from ibis import _

    # Python syntax that compiles to ClickHouse SQL
    (rat.t("bronze.transactions")
        .filter(_.quantity > 0)
        .mutate(total=_.price * _.quantity)
        .to_iceberg("silver.transactions", merge_keys=["store_id", "date"]))

    # Equivalent to the SQL above, but with:
    # - Python linting for methods
    # - Composable/reusable transforms
    # - Type-safe operations

    # ===================== Parsers (Messy Files) =====================

    # Use custom parser function
    rat.ice_ingest("landing/data.xlsx", "bronze.data", parser=my_parser)

    # Register and use parsers
    rat.register_parser("my_format", my_parser)
    rat.parsers()  # List available parsers

    # ===================== Time Travel =====================

    rat.ice_history("bronze.transactions")
    rat.ice_time_travel("bronze.transactions", snapshot_id=123)
"""

from __future__ import annotations

import pandas as pd
from io import BytesIO
from typing import TYPE_CHECKING, Callable, Any

if TYPE_CHECKING:
    import clickhouse_connect
    from mypy_boto3_s3 import S3Client
    import ibis.expr.types as ir


class IbisTable:
    """Enhanced Ibis table expression with .to_iceberg() method.

    Wraps an Ibis table expression and delegates all methods to it,
    while adding Ratatouille-specific functionality like .to_iceberg().

    Example:
        from ibis import _

        (rat.t("bronze.sales")
            .filter(_.amount > 0)
            .group_by("store_id")
            .agg(total=_.amount.sum())
            .to_iceberg("gold.revenue"))
    """

    def __init__(self, expr: "ir.Table", rat_instance: "Rat"):
        self._expr = expr
        self._rat = rat_instance

    def to_iceberg(
        self,
        target: str,
        merge_keys: list[str] | None = None,
        mode: str = "overwrite",
    ) -> dict:
        """Execute this expression and write to Iceberg.

        Args:
            target: Target Iceberg table (e.g., "silver.sales")
            merge_keys: Keys for merge/upsert (if None, overwrites)
            mode: "overwrite" (default) or "append"

        Returns:
            Dict with stats

        Example:
            (rat.t("bronze.sales")
                .filter(_.amount > 0)
                .to_iceberg("silver.clean_sales"))
        """
        return self._rat.to_iceberg(self._expr, target, merge_keys, mode)

    def execute(self) -> pd.DataFrame:
        """Execute the expression and return a DataFrame."""
        return self._expr.execute()

    def to_pandas(self) -> pd.DataFrame:
        """Alias for execute() - returns DataFrame."""
        return self._expr.execute()

    def sql(self) -> str:
        """Get the generated SQL for debugging."""
        import ibis
        return ibis.to_sql(self._expr)

    def preview(self, n: int = 10) -> pd.DataFrame:
        """Preview first N rows."""
        return self._expr.limit(n).execute()

    # Delegate all other methods to the underlying Ibis expression
    # and wrap the result in IbisTable if it returns a table

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying Ibis expression."""
        attr = getattr(self._expr, name)

        # If it's a method, wrap its result
        if callable(attr):
            def wrapper(*args, **kwargs):
                result = attr(*args, **kwargs)
                # If result is a table expression, wrap it
                if hasattr(result, "execute") and hasattr(result, "filter"):
                    return IbisTable(result, self._rat)
                return result
            return wrapper

        return attr

    def __repr__(self) -> str:
        return f"IbisTable({self._expr})"


class Rat:
    """🐀 The friendly data rat - your SDK for Ratatouille."""

    def __init__(self):
        self._ch_client = None
        self._ibis_con = None
        self._s3_client = None
        self._temp_tables: dict[str, pd.DataFrame] = {}  # Temp table storage

    # =========================================================================
    # Core Query Methods
    # =========================================================================

    def query(self, sql: str) -> pd.DataFrame:
        """Execute SQL query on ClickHouse.

        Supports {table} placeholders for Iceberg and temp tables.

        Args:
            sql: SQL query string (can include {bronze.table}, {temp.name}, etc.)

        Returns:
            DataFrame with query results

        Example:
            df = rat.query("SELECT * FROM {bronze.sales} LIMIT 10")
            df = rat.query("SELECT * FROM {temp.filtered} WHERE x > 100")
        """
        import re

        # Expand {namespace.table} placeholders if present
        # Pattern matches ONLY {word.word} to avoid conflicts with regex like \d{4}
        if "{" in sql:
            def replace_table(match):
                table_ref = match.group(1)
                return self._resolve_placeholder(table_ref)
            sql = re.sub(r'\{(\w+\.\w+)\}', replace_table, sql)

        return self.clickhouse().query_df(sql)

    def read(self, path: str, where: str = "", limit: int | None = None) -> pd.DataFrame:
        """Read Parquet file(s) from S3.

        Args:
            path: S3 path (s3://bucket/key or bucket/key shorthand)
            where: Optional WHERE clause (without WHERE keyword)
            limit: Optional row limit

        Returns:
            DataFrame with file contents

        Example:
            df = rat.read("gold/pos/sales.parquet")
            df = rat.read("s3://gold/pos/*.parquet", where="total > 100", limit=1000)
        """
        from ratatouille.core.storage import get_s3_config, _s3_url_for_clickhouse

        path = self._normalize_path(path)
        config = get_s3_config()
        url = _s3_url_for_clickhouse(path)

        where_clause = f"WHERE {where}" if where else ""
        limit_clause = f"LIMIT {limit}" if limit else ""

        sql = f"""
            SELECT * FROM s3(
                '{url}',
                '{config["access_key"]}',
                '{config["secret_key"]}',
                'Parquet'
            )
            {where_clause}
            {limit_clause}
        """
        return self.clickhouse().query_df(sql)

    def write(self, df: pd.DataFrame, path: str) -> str:
        """Write DataFrame to S3 as Parquet.

        Args:
            df: DataFrame to write
            path: S3 path (s3://bucket/key or bucket/key shorthand)

        Returns:
            The full S3 path written to

        Example:
            rat.write(df, "silver/pos/cleaned.parquet")
        """
        from ratatouille.core import write_parquet

        path = self._normalize_path(path)
        return write_parquet(df, path)

    # =========================================================================
    # S3 Operations
    # =========================================================================

    def ingest(self, source: str, dest: str, sheet: str | int = 0) -> tuple[pd.DataFrame, str]:
        """Ingest a file to bronze/silver/gold as Parquet.

        Auto-detects file type (xlsx, csv, json) and converts to Parquet.

        Args:
            source: Source S3 path (e.g., "landing/data.xlsx")
            dest: Destination S3 path or bucket/prefix (e.g., "bronze/sales/")
            sheet: Sheet name or index for Excel files (default: 0)

        Returns:
            tuple of (DataFrame, S3 path written to)

        Example:
            # Auto-names output file
            df, path = rat.ingest("landing/sales.xlsx", "bronze/sales/")
            # → df with data, path = "s3://bronze/sales/sales.parquet"

            # Explicit output name
            df, path = rat.ingest("landing/sales.xlsx", "bronze/sales/2024.parquet")

            # Specific Excel sheet
            df, _ = rat.ingest("landing/data.xlsx", "bronze/", sheet="Sheet2")
        """
        import os

        # Read source file
        data, file_type = self.read_file(source)

        # Convert to DataFrame based on type
        if file_type in ("xlsx", "xls"):
            df = pd.read_excel(data, sheet_name=sheet)
        elif file_type == "csv":
            df = pd.read_csv(data)
        elif file_type == "json":
            df = pd.read_json(data)
        elif file_type == "parquet":
            df = pd.read_parquet(data)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        # Build destination path
        dest = self._normalize_path(dest)
        if dest.endswith("/"):
            # Auto-generate filename from source
            source_name = os.path.basename(source).rsplit(".", 1)[0]
            dest = f"{dest}{source_name}.parquet"
        elif not dest.endswith(".parquet"):
            dest = f"{dest}.parquet"

        # Write to destination
        path = self.write(df, dest)
        return df, path

    def read_file(self, path: str) -> tuple["BytesIO", str]:
        """Read any file from S3 (xlsx, csv, png, etc).

        Args:
            path: S3 path (s3://bucket/key or bucket/key shorthand)

        Returns:
            tuple of (BytesIO with content, file extension)

        Example:
            data, file_type = rat.read_file("landing/data.xlsx")
            if file_type == "xlsx":
                df = pd.read_excel(data)
            elif file_type == "csv":
                df = pd.read_csv(data)
        """
        from ratatouille.core.storage import read_file

        path = self._normalize_path(path)
        return read_file(path)

    def ls(self, path: str = "") -> list[str]:
        """List files in S3.

        Args:
            path: Bucket or bucket/prefix (e.g., "gold/pos/")

        Returns:
            List of file keys

        Example:
            files = rat.ls("gold/pos/")
        """
        # Parse bucket and prefix
        path = path.replace("s3://", "")
        parts = path.split("/", 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""

        from ratatouille.core import list_files
        return list_files(bucket, prefix)

    def buckets(self) -> list[str]:
        """List all S3 buckets.

        Returns:
            List of bucket names

        Example:
            buckets = rat.buckets()
        """
        response = self.s3().list_buckets()
        return [b["Name"] for b in response.get("Buckets", [])]

    # =========================================================================
    # Iceberg Lakehouse Operations
    # =========================================================================

    def ice_ingest(
        self,
        source: str,
        table: str,
        sheet: str | int = 0,
        mode: str = "append",
        extract_from_filename: str | None = None,
        parser: "str | Callable[[BytesIO, str], pd.DataFrame] | None" = None,
    ) -> tuple[pd.DataFrame, int]:
        """Ingest a file directly to an Iceberg table.

        Auto-detects file type, converts to DataFrame, and writes to Iceberg.
        Metadata is tracked automatically. Data is auto-cleaned for storage compatibility.

        Args:
            source: Source S3 path (e.g., "landing/data.xlsx")
            table: Iceberg table name (e.g., "bronze.transactions")
            sheet: Sheet name or index for Excel files (default: 0)
            mode: "append" or "overwrite"
            extract_from_filename: Regex with named groups to extract columns from filename
                Example: r"store_(?P<store_id>\\d+)_(?P<period>\\d{4}-\\d{2})"
                         → adds store_id="001", period="2024-01" columns
            parser: Custom parser - either a name or a function.
                Parser function signature: (data: BytesIO, filename: str) -> pd.DataFrame

        Returns:
            tuple of (DataFrame, rows written)

        Example:
            # Simple ingest
            df, n = rat.ice_ingest("landing/sales.xlsx", "bronze.sales")

            # Extract entity from filename
            df, n = rat.ice_ingest(
                "landing/store_001_2024-01.xlsx",
                "bronze.transactions",
                extract_from_filename=r"store_(?P<store_id>\\d+)_(?P<period>\\d{4}-\\d{2})"
            )
            # → Adds store_id="001", period="2024-01" columns

            # Use custom parser function
            df, n = rat.ice_ingest("landing/report.xlsx", "bronze.reports", parser=my_parser)
        """
        from ratatouille.core.iceberg import append, create_table
        from ratatouille.core.cleaning import clean_dataframe
        import re
        import os
        from datetime import datetime

        # Read source file
        data, file_type = self.read_file(source)
        filename = os.path.basename(source)

        # Use parser if provided
        if parser is not None:
            parser_func = self._resolve_parser(parser)
            df = parser_func(data, filename)
        else:
            # Convert to DataFrame based on file type
            if file_type in ("xlsx", "xls"):
                df = pd.read_excel(data, sheet_name=sheet)
            elif file_type == "csv":
                df = pd.read_csv(data)
            elif file_type == "json":
                df = pd.read_json(data)
            elif file_type == "parquet":
                df = pd.read_parquet(data)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            # Extract columns from filename if pattern provided
            if extract_from_filename:
                match = re.match(extract_from_filename, filename)
                if match:
                    for col_name, value in match.groupdict().items():
                        df[col_name] = value
                else:
                    raise ValueError(f"Filename '{filename}' doesn't match pattern: {extract_from_filename}")

            # Add metadata columns (parser should add these itself)
            df["_source_file"] = filename
            df["_ingested_at"] = datetime.utcnow()

        # Clean DataFrame (normalize types for Parquet/Iceberg compatibility)
        df = clean_dataframe(df)

        # Write to Iceberg
        if mode == "overwrite":
            create_table(table, df)
        else:
            try:
                append(table, df)
            except Exception:
                create_table(table, df)

        return df, len(df)

    def ice_ingest_batch(
        self,
        source_prefix: str,
        table: str,
        sheet: str | int = 0,
        extract_from_filename: str | None = None,
        file_filter: str | None = None,
        parser: "str | Callable[[BytesIO, str], pd.DataFrame] | None" = None,
        skip_existing: bool = False,
    ) -> tuple[pd.DataFrame, dict]:
        """Batch ingest multiple files to an Iceberg table.

        Args:
            source_prefix: S3 prefix (e.g., "landing/" or "landing/stores/")
            table: Iceberg table name (e.g., "bronze.transactions")
            sheet: Sheet name or index for Excel files (default: 0)
            extract_from_filename: Regex with named groups to extract columns
            file_filter: Optional regex to filter which files to process
            parser: Custom parser - either a name or a function.
                Parser function signature: (data: BytesIO, filename: str) -> pd.DataFrame
            skip_existing: If True, skip files already in the registry (for prod jobs)

        Returns:
            tuple of (combined DataFrame, stats dict)

        Example:
            # Ingest all xlsx files from landing/
            df, stats = rat.ice_ingest_batch(
                "landing/",
                "bronze.transactions",
                extract_from_filename=r"store_(?P<store_id>\\d+)_(?P<period>\\d{4}-\\d{2})"
            )
            # stats = {"files": 10, "rows": 5000, "errors": 0}

            # Production mode - skip already ingested files
            df, stats = rat.ice_ingest_batch(
                "landing/reports/",
                "bronze.reports",
                parser=my_parser,
                skip_existing=True
            )
        """
        import re
        from ratatouille.core.tracking import (
            is_file_ingested, mark_file_ingested, compute_file_hash
        )

        # Normalize the source prefix
        source_prefix = self._normalize_path(source_prefix)

        # Parse bucket from prefix
        prefix_without_s3 = source_prefix.replace("s3://", "")
        bucket = prefix_without_s3.split("/")[0]

        files = self.ls(source_prefix)

        # Filter files if pattern provided
        if file_filter:
            files = [f for f in files if re.match(file_filter, f)]

        stats = {"files": 0, "rows": 0, "errors": 0, "skipped": [], "already_ingested": 0}
        all_dfs = []

        for file in files:
            try:
                # ls returns full key path, so just prepend s3://bucket/
                file_path = f"s3://{bucket}/{file}"

                # Check if file already ingested (prod mode)
                if skip_existing:
                    data, _ = self.read_file(file_path)
                    file_hash = compute_file_hash(data)

                    if is_file_ingested(file_path, file_hash):
                        stats["already_ingested"] += 1
                        print(f"⏭️ {file}: already ingested")
                        continue

                df, n = self.ice_ingest(
                    file_path,
                    table,
                    sheet=sheet,
                    extract_from_filename=extract_from_filename,
                    parser=parser,
                )
                all_dfs.append(df)
                stats["files"] += 1
                stats["rows"] += n
                print(f"✅ {file}: {n} rows")

                # Track successful ingestion (prod mode)
                if skip_existing:
                    mark_file_ingested(file_path, file_hash, table, n, "success")

            except Exception as e:
                stats["errors"] += 1
                stats["skipped"].append({"file": file, "error": str(e)})
                print(f"❌ {file}: {e}")

        # Combine all DataFrames
        combined_df = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

        print(f"\n📊 Batch complete: {stats['files']} files, {stats['rows']} rows, {stats['errors']} errors")
        return combined_df, stats

    def ice_merge(
        self,
        df: pd.DataFrame,
        table: str,
        merge_keys: list[str],
    ) -> dict:
        """Merge (upsert) data into an Iceberg table.

        Deduplicates by merge_keys, keeping the latest record.
        Only processes new/changed records (incremental).

        Args:
            df: DataFrame with new/updated records
            table: Iceberg table name
            merge_keys: Columns that form unique key

        Returns:
            Dict with stats: {"inserted": n, "updated": n}

        Example:
            stats = rat.ice_merge(df, "silver.transactions",
                                  merge_keys=["date", "store_id", "product_id"])
        """
        from ratatouille.core.iceberg import merge
        return merge(table, df, merge_keys)

    def ice_read(self, table: str) -> pd.DataFrame:
        """Read an Iceberg table.

        Args:
            table: Table name (e.g., "bronze.transactions")

        Returns:
            DataFrame with table data

        Example:
            df = rat.ice_read("silver.transactions")
        """
        from ratatouille.core.iceberg import read_table
        return read_table(table)

    def ice_tables(self, namespace: str = "bronze") -> list[str]:
        """List Iceberg tables in a namespace.

        Args:
            namespace: Namespace to list (bronze, silver, gold)

        Returns:
            List of table names

        Example:
            tables = rat.ice_tables("silver")
        """
        from ratatouille.core.iceberg import list_tables
        return list_tables(namespace)

    def ice_namespaces(self) -> list[str]:
        """List all Iceberg namespaces (bronze, silver, gold, etc).

        Returns:
            List of namespace names

        Example:
            namespaces = rat.ice_namespaces()
            # → ["bronze", "silver", "gold"]
        """
        from ratatouille.core.iceberg import list_namespaces
        return list_namespaces()

    def ice_all(self) -> dict[str, list[str]]:
        """List all tables organized by namespace.

        Returns:
            Dict mapping namespace to list of tables

        Example:
            rat.ice_all()
            # → {"bronze": ["sales", "products"], "silver": [...], "gold": [...]}
        """
        result = {}
        for ns in self.ice_namespaces():
            tables = self.ice_tables(ns)
            if tables:
                result[ns] = tables
        return result

    def ice_drop(self, table: str, purge: bool = True) -> None:
        """Drop an Iceberg table and optionally delete data files.

        Args:
            table: Table name (e.g., "silver.old_table")
            purge: Also delete Parquet files from S3 (default: True)

        Example:
            rat.ice_drop("silver.old_table")
        """
        from ratatouille.core.iceberg import get_catalog
        import os

        catalog = get_catalog()

        # Get table location before dropping
        try:
            ice_table = catalog.load_table(table)
            location = ice_table.location()
        except Exception:
            print(f"⚠️ Table {table} not found in catalog")
            location = None

        # Drop from catalog
        try:
            catalog.drop_table(table)
            print(f"🗑️ Dropped {table} from catalog")
        except Exception as e:
            print(f"⚠️ Could not drop from catalog: {e}")

        # Delete S3 files if purge=True
        if purge and location:
            try:
                # Parse s3://bucket/path
                if location.startswith("s3://"):
                    path = location[5:]
                    bucket = path.split("/")[0]
                    prefix = "/".join(path.split("/")[1:])

                    s3 = self.s3()
                    # List and delete all objects with this prefix
                    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
                    if "Contents" in response:
                        for obj in response["Contents"]:
                            s3.delete_object(Bucket=bucket, Key=obj["Key"])
                        print(f"🗑️ Deleted {len(response['Contents'])} files from S3")
            except Exception as e:
                print(f"⚠️ Could not delete S3 files: {e}")

    def ice_history(self, table: str) -> pd.DataFrame:
        """Get table snapshot history (time travel).

        Args:
            table: Table name

        Returns:
            DataFrame with snapshot info

        Example:
            history = rat.ice_history("bronze.transactions")
        """
        from ratatouille.core.iceberg import table_history
        return table_history(table)

    def ice_time_travel(self, table: str, snapshot_id: int) -> pd.DataFrame:
        """Read table at a specific point in time.

        Args:
            table: Table name
            snapshot_id: Snapshot ID from ice_history()

        Returns:
            DataFrame at that point in time

        Example:
            # Get history
            history = rat.ice_history("bronze.transactions")
            # Read old version
            old_df = rat.ice_time_travel("bronze.transactions", snapshot_id=123)
        """
        from ratatouille.core.iceberg import read_snapshot
        return read_snapshot(table, snapshot_id)

    # =========================================================================
    # Temp Tables (In-Memory Variables)
    # =========================================================================

    def temp(self, name: str, df: pd.DataFrame | None = None) -> pd.DataFrame | None:
        """Save or retrieve a temp table.

        Temp tables are stored in memory and can be used in transforms
        with the {temp.name} syntax.

        Args:
            name: Temp table name
            df: DataFrame to save (if None, retrieves existing)

        Returns:
            DataFrame if retrieving, None if saving

        Example:
            # Save a temp table
            rat.temp("clean", df)

            # Use in transform
            rat.transform("SELECT * FROM {temp.clean}", target="silver.x")

            # Retrieve
            df = rat.temp("clean")
        """
        if df is not None:
            self._temp_tables[name] = df
            print(f"💾 Saved temp.{name} ({len(df)} rows)")
            return None
        else:
            if name not in self._temp_tables:
                raise KeyError(f"Temp table '{name}' not found. Available: {list(self._temp_tables.keys())}")
            return self._temp_tables[name]

    def temp_list(self) -> dict[str, int]:
        """List all temp tables with row counts.

        Returns:
            Dict mapping name to row count

        Example:
            rat.temp_list()
            # → {"clean": 1500, "filtered": 800}
        """
        return {name: len(df) for name, df in self._temp_tables.items()}

    def temp_drop(self, name: str | None = None) -> None:
        """Drop temp table(s).

        Args:
            name: Table to drop (if None, drops all)

        Example:
            rat.temp_drop("clean")  # Drop one
            rat.temp_drop()         # Drop all
        """
        if name is None:
            count = len(self._temp_tables)
            self._temp_tables.clear()
            print(f"🗑️ Dropped all {count} temp tables")
        else:
            if name in self._temp_tables:
                del self._temp_tables[name]
                print(f"🗑️ Dropped temp.{name}")

    def _temp_to_s3_func(self, name: str) -> str:
        """Convert temp table to ClickHouse s3() function.

        Writes temp DataFrame to S3 and returns the s3() call.
        """
        if name not in self._temp_tables:
            raise KeyError(f"Temp table '{name}' not found")

        df = self._temp_tables[name]
        from ratatouille.core.storage import get_s3_config

        # Write to temp location in warehouse
        temp_path = f"s3://warehouse/_temp/{name}.parquet"
        self.write(df, temp_path)

        config = get_s3_config()
        s3_url = temp_path.replace("s3://", f"{config['endpoint']}/")

        return f"s3('{s3_url}', '{config['access_key']}', '{config['secret_key']}', 'Parquet')"

    # =========================================================================
    # Placeholder Resolution
    # =========================================================================

    def _resolve_placeholder(self, table_ref: str) -> str:
        """Resolve a {table} placeholder to ClickHouse s3() function.

        Supports:
            - {bronze.table} → Iceberg table
            - {silver.table} → Iceberg table
            - {gold.table} → Iceberg table
            - {temp.name} → Temp table
        """
        if table_ref.startswith("temp."):
            name = table_ref[5:]  # Remove "temp." prefix
            return self._temp_to_s3_func(name)
        else:
            return self._ice_s3_func(table_ref)

    def df(self, table: str) -> pd.DataFrame:
        """Read a table using {placeholder} syntax.

        Supports Iceberg tables and temp tables.

        Args:
            table: Table reference like "{bronze.sales}" or "{temp.clean}"

        Returns:
            DataFrame

        Example:
            df = rat.df("{bronze.sales}")
            df = rat.df("{temp.filtered}")
        """
        # Strip braces if present
        table = table.strip("{}")

        if table.startswith("temp."):
            name = table[5:]
            return self.temp(name)
        else:
            return self.ice_read(table)

    def ice_location(self, table: str) -> str:
        """Get the S3 location of an Iceberg table's data files.

        Args:
            table: Table name (e.g., "bronze.transactions")

        Returns:
            S3 path with glob pattern for Parquet files

        Example:
            path = rat.ice_location("bronze.transactions")
            # → "s3://warehouse/bronze/transactions/data/*.parquet"
        """
        from ratatouille.core.iceberg import get_catalog
        catalog = get_catalog()
        ice_table = catalog.load_table(table)
        location = ice_table.location()
        return f"{location}/data/*.parquet"

    def _ice_s3_func(self, table: str) -> str:
        """Get ClickHouse s3() function call for an Iceberg table.

        Internal helper for SQL generation.
        """
        from ratatouille.core.storage import get_s3_config

        location = self.ice_location(table)
        config = get_s3_config()

        # Convert s3:// to http:// for ClickHouse
        s3_url = location.replace("s3://", f"{config['endpoint']}/")

        return f"s3('{s3_url}', '{config['access_key']}', '{config['secret_key']}', 'Parquet')"

    def transform(
        self,
        sql: str,
        target: str,
        merge_keys: list[str] | None = None,
        mode: str = "overwrite",
    ) -> dict:
        """Transform data using ClickHouse SQL and write to Iceberg.

        Use {table_name} placeholders in SQL to reference Iceberg tables.
        ClickHouse handles the heavy computation, Iceberg stores the result.

        Respects dev mode - if in dev mode, writes to the current branch.

        Args:
            sql: SQL query with {table} placeholders for Iceberg tables
            target: Target Iceberg table name (e.g., "silver.transactions")
            merge_keys: Keys for merge/upsert (if None, overwrites entire table)
            mode: "overwrite" (default) or "append"

        Returns:
            Dict with stats: {"rows": n, "target": "table_name", "branch": "..."}

        Example:
            # Bronze → Silver: Clean and dedupe
            rat.transform(
                sql=\"""
                    SELECT DISTINCT *,
                        toDecimal64(price * quantity, 2) AS total
                    FROM {bronze.transactions}
                    WHERE quantity > 0
                \""",
                target="silver.transactions",
                merge_keys=["store_id", "date", "transaction_id"]
            )

            # Silver → Gold: Aggregate
            rat.transform(
                sql=\"""
                    SELECT
                        store_id,
                        toDate(date) AS order_date,
                        SUM(total) AS revenue,
                        SUM(quantity) AS items_sold,
                        COUNT(*) AS transactions
                    FROM {silver.transactions}
                    GROUP BY store_id, order_date
                \""",
                target="gold.daily_sales",
                merge_keys=["store_id", "order_date"]
            )
        """
        import re
        from ratatouille.core.dev import is_dev_mode, get_effective_branch
        from ratatouille.core.iceberg import (
            merge, create_table, append,
            merge_to_branch, append_to_branch, overwrite_branch
        )

        # Replace {table} placeholders with s3() function calls
        # Pattern matches ONLY {namespace.table} format (e.g., {bronze.sales}, {temp.clean})
        # This avoids conflicts with regex patterns like \d{4} in SQL
        def replace_table(match):
            table_ref = match.group(1)
            return self._resolve_placeholder(table_ref)

        expanded_sql = re.sub(r'\{(\w+\.\w+)\}', replace_table, sql)

        # Execute SQL via ClickHouse
        branch = get_effective_branch()
        branch_info = f" (branch: {branch})" if branch != "main" else ""
        print(f"🔄 Transforming → {target}{branch_info}")
        df = self.clickhouse().query_df(expanded_sql)
        print(f"   ClickHouse returned {len(df)} rows")

        # Write to Iceberg - respecting dev mode
        if is_dev_mode():
            # Dev mode: write to branch
            if merge_keys and mode != "append":
                stats = merge_to_branch(target, df, merge_keys, branch)
                print(f"   ✅ Merged to branch: {stats['inserted']} inserted, {stats['updated']} updated")
            elif mode == "append":
                append_to_branch(target, df, branch)
                stats = {"rows": len(df), "mode": "append"}
                print(f"   ✅ Appended {len(df)} rows to branch")
            else:
                overwrite_branch(target, df, branch)
                stats = {"rows": len(df), "mode": "overwrite"}
                print(f"   ✅ Wrote {len(df)} rows to branch")
        else:
            # Normal mode: write to main
            if merge_keys and mode != "append":
                stats = merge(target, df, merge_keys)
                print(f"   ✅ Merged: {stats['inserted']} inserted, {stats['updated']} updated")
            elif mode == "append":
                append(target, df)
                stats = {"rows": len(df), "mode": "append"}
                print(f"   ✅ Appended {len(df)} rows")
            else:
                create_table(target, df)
                stats = {"rows": len(df), "mode": "overwrite"}

        stats["target"] = target
        stats["branch"] = branch
        return stats

    def transform_preview(self, sql: str) -> str:
        """Preview the expanded SQL without executing it.

        Useful for debugging - shows how {table} placeholders are expanded.

        Args:
            sql: SQL query with {table} placeholders

        Returns:
            Expanded SQL string

        Example:
            print(rat.transform_preview("SELECT * FROM {bronze.transactions}"))
            print(rat.transform_preview("SELECT * FROM {temp.clean}"))
        """
        import re

        def replace_table(match):
            table_ref = match.group(1)
            return self._resolve_placeholder(table_ref)

        return re.sub(r'\{(\w+\.\w+)\}', replace_table, sql)

    # =========================================================================
    # Layer Operations (Medallion Architecture)
    # =========================================================================

    def layer(self, name: str | None = None) -> str:
        """Get or set current medallion layer.

        Args:
            name: Layer to switch to (bronze, silver, gold)

        Returns:
            Current layer name

        Example:
            rat.layer()           # → "bronze"
            rat.layer("silver")   # Switch to silver
        """
        from ratatouille.core.branches import get_current_layer, set_layer

        if name:
            set_layer(name)
        return get_current_layer()

    def layers(self) -> list[dict]:
        """List all medallion layers with descriptions.

        Returns:
            List of layer info dicts

        Example:
            rat.layers()
            # → [{"name": "bronze", "description": "...", "current": True}, ...]
        """
        from ratatouille.core.branches import list_layers
        return list_layers()

    def use_bronze(self) -> None:
        """Switch to bronze layer (raw data).

        Example:
            rat.use_bronze()
            df, n = rat.ice_ingest("landing/data.xlsx", "transactions")
        """
        from ratatouille.core.branches import use_bronze
        use_bronze()

    def use_silver(self) -> None:
        """Switch to silver layer (cleaned data).

        Example:
            rat.use_silver()
            rat.ice_merge(df, "transactions", merge_keys=["id"])
        """
        from ratatouille.core.branches import use_silver
        use_silver()

    def use_gold(self) -> None:
        """Switch to gold layer (business-ready).

        Example:
            rat.use_gold()
            df = rat.ice_read("sales_summary")
        """
        from ratatouille.core.branches import use_gold
        use_gold()

    def workflow_ingest(self) -> str:
        """Start ingestion workflow (sets layer to bronze).

        Returns:
            Current layer name

        Example:
            rat.workflow_ingest()  # → "bronze"
            # Now ingest raw data
        """
        from ratatouille.core.branches import workflow_ingest
        return workflow_ingest()

    def workflow_transform(self) -> str:
        """Start transformation workflow (sets layer to silver).

        Returns:
            Current layer name

        Example:
            rat.workflow_transform()  # → "silver"
            # Now clean and dedupe data
        """
        from ratatouille.core.branches import workflow_transform
        return workflow_transform()

    def workflow_publish(self) -> str:
        """Start publish workflow (sets layer to gold).

        Returns:
            Current layer name

        Example:
            rat.workflow_publish()  # → "gold"
            # Now create business aggregations
        """
        from ratatouille.core.branches import workflow_publish
        return workflow_publish()

    # =========================================================================
    # ClickHouse Operations
    # =========================================================================

    def tables(self) -> list[str]:
        """List all ClickHouse tables.

        Returns:
            List of table names

        Example:
            tables = rat.tables()
        """
        result = self.clickhouse().query("SHOW TABLES")
        return [row[0] for row in result.result_rows]

    def materialize(
        self,
        table_name: str,
        path: str,
        order_by: str = "tuple()",
    ) -> None:
        """Create ClickHouse table from S3 Parquet data.

        Args:
            table_name: Name for the new table
            path: S3 path to Parquet file(s)
            order_by: ORDER BY clause for MergeTree (default: tuple())

        Example:
            rat.materialize("sales", "gold/pos/sales.parquet", order_by="product_id")
        """
        from ratatouille.core import create_table_from_s3, s3_path

        path = self._normalize_path(path)
        create_table_from_s3(table_name, path, order_by=order_by)

    def drop(self, table_name: str) -> None:
        """Drop a ClickHouse table.

        Args:
            table_name: Table to drop

        Example:
            rat.drop("old_table")
        """
        self.clickhouse().command(f"DROP TABLE IF EXISTS {table_name}")

    def describe(self, table_name: str) -> pd.DataFrame:
        """Describe a ClickHouse table schema.

        Args:
            table_name: Table to describe

        Returns:
            DataFrame with column info

        Example:
            schema = rat.describe("gold_sales_by_product")
        """
        return self.clickhouse().query_df(f"DESCRIBE TABLE {table_name}")

    # =========================================================================
    # Raw Clients
    # =========================================================================

    def clickhouse(self):
        """Get the ClickHouse client.

        Returns:
            clickhouse_connect Client

        Example:
            client = rat.clickhouse()
            result = client.query("SELECT 1")
        """
        if self._ch_client is None:
            from ratatouille.core import get_clickhouse
            self._ch_client = get_clickhouse()
        return self._ch_client

    def s3(self):
        """Get the S3 client.

        Returns:
            boto3 S3 client

        Example:
            s3 = rat.s3()
            s3.download_file("gold", "pos/sales.parquet", "/tmp/sales.parquet")
        """
        if self._s3_client is None:
            from ratatouille.core import get_s3_client
            self._s3_client = get_s3_client()
        return self._s3_client

    def ibis(self):
        """Get the Ibis ClickHouse connection (cached).

        Returns:
            Ibis ClickHouse connection

        Example:
            con = rat.ibis()
            t = con.table("my_table")
            result = t.filter(t.amount > 100).execute()
        """
        if self._ibis_con is None:
            import ibis
            from ratatouille.core.storage import get_clickhouse_config

            config = get_clickhouse_config()

            self._ibis_con = ibis.clickhouse.connect(
                host=config["host"],
                port=config["port"],
                user=config["user"],
                password=config["password"],
            )
        return self._ibis_con

    # =========================================================================
    # Ibis (Pythonic Transforms)
    # =========================================================================

    def t(self, table_ref: str) -> "IbisTable":
        """Get an Ibis table expression for Pythonic transforms.

        Supports the same {placeholder} syntax as other methods.
        Returns an enhanced Ibis table with `.to_iceberg()` method.

        Args:
            table_ref: Table reference:
                - "bronze.sales" → Iceberg table
                - "temp.clean" → Temp table (materialized to S3)

        Returns:
            IbisTable expression with .to_iceberg() method

        Example:
            from ibis import _

            # Simple filter and aggregate
            (rat.t("bronze.sales")
                .filter(_.amount > 0)
                .group_by("store_id")
                .agg(total=_.amount.sum())
                .to_iceberg("gold.revenue"))

            # With merge keys (upsert)
            (rat.t("bronze.transactions")
                .filter(_.qty > 0)
                .mutate(total=_.price * _.qty)
                .to_iceberg("silver.transactions", merge_keys=["id"]))
        """
        from ratatouille.core.storage import get_s3_config

        config = get_s3_config()

        # Resolve table reference to S3 path
        if table_ref.startswith("temp."):
            # Temp table - materialize to S3 first
            name = table_ref[5:]
            if name not in self._temp_tables:
                raise KeyError(f"Temp table '{name}' not found")

            # Write temp table to S3
            temp_path = f"s3://warehouse/_temp/{name}.parquet"
            self.write(self._temp_tables[name], temp_path)

            s3_url = temp_path.replace("s3://", f"{config['endpoint']}/")
            s3_func = f"s3('{s3_url}', '{config['access_key']}', '{config['secret_key']}', 'Parquet')"
        else:
            # Iceberg table - get S3 path
            location = self.ice_location(table_ref)
            s3_url = location.replace("s3://", f"{config['endpoint']}/")
            s3_func = f"s3('{s3_url}', '{config['access_key']}', '{config['secret_key']}', 'Parquet')"

        # Create Ibis table from SQL
        ibis_table = self.ibis().sql(f"SELECT * FROM {s3_func}")

        # Wrap in our enhanced class with .to_iceberg()
        return IbisTable(ibis_table, self)

    def to_iceberg(
        self,
        expr,
        target: str,
        merge_keys: list[str] | None = None,
        mode: str = "overwrite",
    ) -> dict:
        """Execute an Ibis expression and write to Iceberg.

        Args:
            expr: Ibis table expression
            target: Target Iceberg table (e.g., "silver.sales")
            merge_keys: Keys for merge/upsert (if None, overwrites)
            mode: "overwrite" (default) or "append"

        Returns:
            Dict with stats

        Example:
            expr = rat.t("bronze.sales").filter(_.amount > 0)
            rat.to_iceberg(expr, "silver.sales")
        """
        from ratatouille.core.dev import is_dev_mode, get_effective_branch
        from ratatouille.core.iceberg import (
            merge, create_table, append,
            merge_to_branch, append_to_branch, overwrite_branch
        )

        # Execute the Ibis expression
        branch = get_effective_branch()
        branch_info = f" (branch: {branch})" if branch != "main" else ""
        print(f"🐍 Ibis → {target}{branch_info}")

        # Get the SQL for debugging
        import ibis
        sql = ibis.to_sql(expr)
        print(f"   Generated SQL: {len(sql)} chars")

        # Execute
        df = expr.execute()
        print(f"   Returned {len(df)} rows")

        # Write to Iceberg - respecting dev mode
        if is_dev_mode():
            if merge_keys and mode != "append":
                stats = merge_to_branch(target, df, merge_keys, branch)
                print(f"   ✅ Merged to branch: {stats['inserted']} inserted, {stats['updated']} updated")
            elif mode == "append":
                append_to_branch(target, df, branch)
                stats = {"rows": len(df), "mode": "append"}
                print(f"   ✅ Appended {len(df)} rows to branch")
            else:
                overwrite_branch(target, df, branch)
                stats = {"rows": len(df), "mode": "overwrite"}
                print(f"   ✅ Wrote {len(df)} rows to branch")
        else:
            if merge_keys and mode != "append":
                stats = merge(target, df, merge_keys)
                print(f"   ✅ Merged: {stats['inserted']} inserted, {stats['updated']} updated")
            elif mode == "append":
                append(target, df)
                stats = {"rows": len(df), "mode": "append"}
                print(f"   ✅ Appended {len(df)} rows")
            else:
                create_table(target, df)
                stats = {"rows": len(df), "mode": "overwrite"}

        stats["target"] = target
        stats["branch"] = branch
        return stats

    # =========================================================================
    # Parsers
    # =========================================================================

    def parsers(self) -> dict[str, str]:
        """List all available parsers with descriptions.

        Returns:
            Dict mapping parser name to description

        Example:
            rat.parsers()
            # → {"my_format": "Custom Excel format parser"}
        """
        from ratatouille.parsers import list_parsers
        return list_parsers()

    def register_parser(self, name: str, func: "Callable[[BytesIO, str], pd.DataFrame]") -> None:
        """Register a custom parser for reuse.

        Args:
            name: Parser name (e.g., "my_format")
            func: Parser function (data: BytesIO, filename: str) -> pd.DataFrame

        Example:
            def my_parser(data, filename):
                df = pd.read_excel(data, skiprows=10)
                df["_source_file"] = filename
                return df

            rat.register_parser("my_format", my_parser)
            rat.ice_ingest("landing/file.xlsx", "bronze.data", parser="my_format")
        """
        from ratatouille.parsers import register_parser
        register_parser(name, func)

    def _resolve_parser(self, parser: "str | Callable") -> "Callable[[BytesIO, str], pd.DataFrame]":
        """Resolve parser to a callable function.

        Args:
            parser: Either a parser name (str) or a callable function

        Returns:
            Parser function
        """
        if callable(parser):
            return parser
        elif isinstance(parser, str):
            from ratatouille.parsers import get_parser
            return get_parser(parser)
        else:
            raise ValueError(f"Parser must be a string name or callable, got: {type(parser)}")

    # =========================================================================
    # Data Quality
    # =========================================================================

    def nulls(self, df: pd.DataFrame) -> dict:
        """Report null values in a DataFrame.

        Args:
            df: DataFrame to analyze

        Returns:
            Dict with null statistics:
            - total_nulls: Total null count
            - total_cells: Total cells in DataFrame
            - pct: Percentage of nulls
            - columns: Dict of columns with nulls and their counts

        Example:
            df = rat.df("{bronze.sales}")
            report = rat.nulls(df)
            # → {"total_nulls": 150, "columns": {"value": 50, "name": 100}, "pct": 5.2}
        """
        from ratatouille.core.cleaning import report_nulls
        return report_nulls(df)

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean a DataFrame for storage (normalize types).

        Converts pandas nullable types to standard numpy types for
        Parquet/Iceberg compatibility. Does NOT fill or validate.

        Args:
            df: DataFrame to clean

        Returns:
            Cleaned DataFrame

        Example:
            df = rat.clean(df)
        """
        from ratatouille.core.cleaning import clean_dataframe
        return clean_dataframe(df)

    # =========================================================================
    # File Tracking (Production)
    # =========================================================================

    def ingestion_history(self, table: str | None = None) -> pd.DataFrame:
        """Get file ingestion history from registry.

        Args:
            table: Filter by target table (optional)

        Returns:
            DataFrame with ingestion history (file_path, file_hash, target_table, rows, timestamp, status)

        Example:
            # All history
            rat.ingestion_history()

            # For specific table
            rat.ingestion_history("bronze.sales")
        """
        from ratatouille.core.tracking import get_ingestion_history
        return get_ingestion_history(table)

    def reset_ingestion(self, table: str | None = None) -> None:
        """Reset ingestion tracking (allows re-ingesting files).

        Args:
            table: Reset only for specific table (if None, resets all)

        Example:
            # Reset all
            rat.reset_ingestion()

            # Reset specific table
            rat.reset_ingestion("bronze.sales")
        """
        from ratatouille.core.iceberg import get_catalog

        registry_table = "bronze._file_registry"
        try:
            if table:
                # Filter and rewrite without the specified table
                history = self.ingestion_history()
                if not history.empty:
                    filtered = history[history["target_table"] != table]
                    from ratatouille.core.iceberg import create_table
                    create_table(registry_table, filtered)
                    print(f"🔄 Reset ingestion tracking for {table}")
            else:
                # Drop entire registry
                self.ice_drop(registry_table)
                print("🔄 Reset all ingestion tracking")
        except Exception as e:
            print(f"⚠️ Could not reset: {e}")

    # =========================================================================
    # Helpers
    # =========================================================================

    def _normalize_path(self, path: str) -> str:
        """Normalize path to s3:// format."""
        if not path.startswith("s3://"):
            return f"s3://{path}"
        return path

    # =========================================================================
    # Dev Mode (Iceberg Branches)
    # =========================================================================

    def dev(self, branch_name: str | None = None) -> str | None:
        """Enter or exit dev mode.

        In dev mode, all writes go to a development branch instead of main.
        Reads also come from the dev branch (with fallback to main).

        Args:
            branch_name: Branch to use, or None to exit dev mode

        Returns:
            Current dev branch name, or None if not in dev mode

        Example:
            # Enter dev mode
            rat.dev("feature/new-transform")

            # All operations now use the branch
            rat.transform(sql, target="silver.sales")  # Writes to branch

            # Exit dev mode
            rat.dev(None)

            # Or use context manager
            with rat.dev_context("feature/new"):
                rat.transform(...)
        """
        from ratatouille.core.dev import enter_dev, exit_dev

        if branch_name is None:
            exit_dev()
            print("🔒 Exited dev mode (now using main)")
            return None
        else:
            enter_dev(branch_name)
            print(f"🔬 Dev mode: {branch_name}")
            return branch_name

    def dev_status(self) -> dict:
        """Get current dev mode status.

        Returns:
            Dict with dev mode info:
            - active: True if in dev mode
            - branch: Current branch name ("main" if not in dev mode)

        Example:
            rat.dev_status()
            # → {"active": True, "branch": "feature/new"}
        """
        from ratatouille.core.dev import is_dev_mode, get_effective_branch

        return {
            "active": is_dev_mode(),
            "branch": get_effective_branch(),
        }

    def dev_start(self, branch_name: str, tables: list[str] | None = None) -> dict:
        """Start a new dev branch for specified tables.

        Creates the branch on all specified tables (or all existing tables
        if none specified), then enters dev mode.

        Args:
            branch_name: Name for the dev branch (e.g., "feature/new-cleaning")
            tables: List of tables to branch (default: all tables)

        Returns:
            Dict with created branches info

        Example:
            # Branch all tables
            rat.dev_start("feature/new-cleaning")

            # Branch specific tables
            rat.dev_start("feature/fix", tables=["bronze.sales", "silver.sales"])
        """
        from ratatouille.core.iceberg import create_branch
        from ratatouille.core.dev import enter_dev

        # Get tables to branch
        if tables is None:
            tables = []
            for ns in self.ice_namespaces():
                for t in self.ice_tables(ns):
                    tables.append(f"{ns}.{t}")

        # Create branches
        created = []
        for table in tables:
            try:
                create_branch(table, branch_name)
                created.append(table)
                print(f"   🌿 Created branch '{branch_name}' on {table}")
            except Exception as e:
                print(f"   ⚠️ Could not branch {table}: {e}")

        # Enter dev mode
        enter_dev(branch_name)

        print(f"\n🔬 Dev mode active: {branch_name}")
        return {"branch": branch_name, "tables": created}

    def dev_merge(self, branch_name: str | None = None) -> dict:
        """Merge dev branch to main.

        Fast-forwards the main branch to match the dev branch.
        This is a metadata-only operation - no data is copied.

        Args:
            branch_name: Branch to merge (default: current dev branch)

        Returns:
            Dict with merge results

        Raises:
            ValueError: If trying to merge main into main

        Example:
            # Merge current dev branch
            rat.dev_merge()

            # Merge a specific branch
            rat.dev_merge("feature/done")
        """
        from ratatouille.core.iceberg import fast_forward_branch, list_branches
        from ratatouille.core.dev import get_effective_branch, exit_dev

        branch = branch_name or get_effective_branch()
        if branch == "main":
            raise ValueError("Cannot merge main into main")

        # Find tables with this branch
        merged = []
        for ns in self.ice_namespaces():
            for t in self.ice_tables(ns):
                table = f"{ns}.{t}"
                branches = list_branches(table)
                if any(b["name"] == branch for b in branches):
                    try:
                        fast_forward_branch(table, branch, "main")
                        merged.append(table)
                        print(f"   ✅ Merged {table}")
                    except Exception as e:
                        print(f"   ⚠️ Could not merge {table}: {e}")

        # Exit dev mode if we merged the current branch
        if branch_name is None or branch_name == get_effective_branch():
            exit_dev()

        print(f"\n🎉 Merged '{branch}' to main")
        return {"branch": branch, "merged": merged}

    def dev_drop(self, branch_name: str | None = None) -> dict:
        """Drop a dev branch without merging.

        Deletes the branch from all tables. Data unique to the branch
        will be garbage collected.

        Args:
            branch_name: Branch to drop (default: current dev branch)

        Returns:
            Dict with dropped branches

        Raises:
            ValueError: If trying to drop main branch

        Example:
            # Drop current dev branch
            rat.dev_drop()

            # Drop a specific branch
            rat.dev_drop("feature/abandoned")
        """
        from ratatouille.core.iceberg import drop_branch, list_branches
        from ratatouille.core.dev import get_effective_branch, exit_dev

        branch = branch_name or get_effective_branch()
        if branch == "main":
            raise ValueError("Cannot drop main branch")

        # Find and drop branches
        dropped = []
        for ns in self.ice_namespaces():
            for t in self.ice_tables(ns):
                table = f"{ns}.{t}"
                branches = list_branches(table)
                if any(b["name"] == branch for b in branches):
                    try:
                        drop_branch(table, branch)
                        dropped.append(table)
                        print(f"   🗑️ Dropped branch from {table}")
                    except Exception as e:
                        print(f"   ⚠️ Could not drop from {table}: {e}")

        # Exit dev mode if we dropped the current branch
        if branch_name is None or branch_name == get_effective_branch():
            exit_dev()

        print(f"\n🗑️ Dropped branch '{branch}'")
        return {"branch": branch, "dropped": dropped}

    def dev_diff(self, table: str, branch_name: str | None = None) -> dict:
        """Compare dev branch to main.

        Shows the difference in row counts between the branch and main.

        Args:
            table: Table to compare
            branch_name: Branch to compare (default: current dev branch)

        Returns:
            Dict with diff statistics:
            - table: Table name
            - branch: Branch name
            - main_rows: Number of rows in main
            - branch_rows: Number of rows in branch
            - diff: Difference (branch_rows - main_rows)

        Example:
            rat.dev_diff("silver.sales")
            # → {"main_rows": 1000, "branch_rows": 1050, "diff": 50}
        """
        from ratatouille.core.dev import get_effective_branch
        from ratatouille.core.iceberg import read_table, read_branch

        branch = branch_name or get_effective_branch()

        # Read both versions
        main_df = read_table(table)  # Main branch
        branch_df = read_branch(table, branch)  # Dev branch

        return {
            "table": table,
            "branch": branch,
            "main_rows": len(main_df),
            "branch_rows": len(branch_df),
            "diff": len(branch_df) - len(main_df),
        }

    def dev_branches(self, table: str | None = None) -> list[dict] | dict[str, list[dict]]:
        """List branches for tables.

        Args:
            table: Specific table to list branches for (default: all tables)

        Returns:
            If table specified: List of branch info dicts
            If no table: Dict mapping table name to list of branches

        Example:
            # Single table
            rat.dev_branches("bronze.sales")
            # → [{"name": "main", "type": "branch"}, {"name": "feature/x", "type": "branch"}]

            # All tables
            rat.dev_branches()
            # → {"bronze.sales": [...], "silver.sales": [...]}
        """
        from ratatouille.core.iceberg import list_branches

        if table:
            return list_branches(table)

        result = {}
        for ns in self.ice_namespaces():
            for t in self.ice_tables(ns):
                full_name = f"{ns}.{t}"
                result[full_name] = list_branches(full_name)

        return result

    def dev_context(self, branch_name: str):
        """Context manager for dev mode.

        All operations within the context will use the specified branch.
        Automatically reverts to previous state on exit.

        Args:
            branch_name: Branch to use within the context

        Yields:
            The branch name

        Example:
            with rat.dev_context("feature/test"):
                rat.transform(...)  # Uses branch
            # Back to main (or previous branch)
        """
        from ratatouille.core.dev import dev_mode

        return dev_mode(branch_name)

    def _ice_read_branch(self, table: str, branch_name: str) -> pd.DataFrame:
        """Read table at a specific branch (internal helper).

        Args:
            table: Table name
            branch_name: Branch to read from

        Returns:
            DataFrame with table data
        """
        from ratatouille.core.iceberg import read_branch

        return read_branch(table, branch_name)

    def ice_ingest_df(
        self,
        df: pd.DataFrame,
        table: str,
        mode: str = "append",
    ) -> int:
        """Ingest a DataFrame directly to an Iceberg table.

        Respects dev mode - if in dev mode, writes to the current branch.

        Args:
            df: DataFrame to ingest
            table: Iceberg table name (e.g., "bronze.test")
            mode: "append" or "overwrite"

        Returns:
            Number of rows written

        Example:
            df = pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})
            rat.ice_ingest_df(df, "bronze.test")
        """
        from ratatouille.core.dev import is_dev_mode, get_effective_branch
        from ratatouille.core.iceberg import (
            append, create_table, append_to_branch, overwrite_branch
        )
        from ratatouille.core.cleaning import clean_dataframe

        # Clean DataFrame
        df = clean_dataframe(df)

        # Check if in dev mode
        if is_dev_mode():
            branch = get_effective_branch()
            if mode == "overwrite":
                return overwrite_branch(table, df, branch)
            else:
                return append_to_branch(table, df, branch)
        else:
            # Normal mode - write to main
            if mode == "overwrite":
                create_table(table, df)
            else:
                try:
                    append(table, df)
                except Exception:
                    create_table(table, df)
            return len(df)

    def __repr__(self) -> str:
        return "🐀 Ratatouille SDK - rat.query(), rat.read(), rat.write(), rat.ls()"


# Singleton instance
rat = Rat()
