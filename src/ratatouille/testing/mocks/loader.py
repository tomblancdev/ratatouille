"""Load mock data from various formats into DuckDB.

Optimized for DuckDB native file readers - minimal pandas usage.

Supported formats:
- YAML (.yaml, .yml) - with 'table' and 'rows' keys
- CSV (.csv) - DuckDB native reader
- Excel (.xlsx, .xls) - requires openpyxl, uses pandas bridge
- JSON (.json) - DuckDB native reader
- Parquet (.parquet) - DuckDB native reader
- Python generators (.py) - for dynamic data
"""

import importlib.util
import json
import re
import tempfile
from pathlib import Path
from typing import Any

import duckdb
import yaml


def load_mock_file(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
    sheet: str | None = None,
) -> list[str]:
    """Load a mock data file into DuckDB tables.

    Uses DuckDB native readers where possible for performance.

    Args:
        file_path: Path to the mock data file
        conn: DuckDB connection to load data into
        table_name: Override table name (default: derived from file/content)
        sheet: Sheet name for Excel files (None = first sheet)

    Returns:
        List of table names created
    """
    suffix = file_path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        return _load_yaml(file_path, conn, table_name)
    elif suffix == ".csv":
        return _load_csv_native(file_path, conn, table_name)
    elif suffix in (".xlsx", ".xls"):
        return _load_excel(file_path, conn, table_name, sheet)
    elif suffix == ".json":
        return _load_json_native(file_path, conn, table_name)
    elif suffix == ".parquet":
        return _load_parquet_native(file_path, conn, table_name)
    elif suffix == ".py":
        return _load_generator(file_path, conn, table_name)
    else:
        raise ValueError(f"Unsupported mock file format: {suffix}")


def _normalize_table_name(name: str) -> str:
    """Convert table reference to valid SQL identifier.

    e.g., 'bronze.raw_sales' -> 'bronze_raw_sales'
    """
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _load_yaml(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
) -> list[str]:
    """Load YAML mock data using DuckDB's JSON capabilities."""
    with open(file_path) as f:
        data = yaml.safe_load(f)

    tables_created = []

    def create_table_from_rows(name: str, rows: list[dict]) -> None:
        """Create table from rows using DuckDB's native JSON parsing."""
        if not rows:
            # Empty table - create with no rows
            conn.execute(f"CREATE TABLE {name} AS SELECT * FROM (SELECT 1) WHERE false")
            return

        # Write to temp file and use DuckDB's native JSON reader
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(rows, f)
            temp_path = f.name

        try:
            conn.execute(f"""
                CREATE TABLE {name} AS
                SELECT * FROM read_json_auto('{temp_path}')
            """)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    # Single table format
    if "table" in data and "rows" in data:
        name = table_name or _normalize_table_name(data["table"])
        create_table_from_rows(name, data["rows"])
        tables_created.append(name)

    # Multiple tables format
    elif "tables" in data:
        for table_def in data["tables"]:
            name = _normalize_table_name(table_def["table"])
            create_table_from_rows(name, table_def["rows"])
            tables_created.append(name)

    # Just rows (use table_name or filename)
    elif "rows" in data:
        name = table_name or _normalize_table_name(file_path.stem)
        create_table_from_rows(name, data["rows"])
        tables_created.append(name)

    else:
        raise ValueError(
            f"Invalid YAML format in {file_path}: expected 'table' and 'rows' keys"
        )

    return tables_created


def _load_csv_native(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
) -> list[str]:
    """Load CSV file using DuckDB's native reader."""
    name = table_name or _normalize_table_name(file_path.stem)
    conn.execute(f"""
        CREATE TABLE {name} AS
        SELECT * FROM read_csv_auto('{file_path}')
    """)
    return [name]


def _load_json_native(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
) -> list[str]:
    """Load JSON file using DuckDB's native reader."""
    # Read JSON to check structure
    with open(file_path) as f:
        data = json.load(f)

    tables_created = []

    if isinstance(data, list):
        # Array of records - load directly
        name = table_name or _normalize_table_name(file_path.stem)
        conn.execute(f"""
            CREATE TABLE {name} AS
            SELECT * FROM read_json_auto('{file_path}')
        """)
        tables_created.append(name)

    elif isinstance(data, dict):
        if "rows" in data:
            # Extract rows and load via temp file
            name = table_name or _normalize_table_name(
                data.get("table", file_path.stem)
            )
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(data["rows"], f)
                temp_path = f.name
            try:
                conn.execute(f"""
                    CREATE TABLE {name} AS
                    SELECT * FROM read_json_auto('{temp_path}')
                """)
            finally:
                Path(temp_path).unlink(missing_ok=True)
            tables_created.append(name)

        elif "tables" in data:
            for table_def in data["tables"]:
                name = _normalize_table_name(table_def["table"])
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False
                ) as f:
                    json.dump(table_def["rows"], f)
                    temp_path = f.name
                try:
                    conn.execute(f"""
                        CREATE TABLE {name} AS
                        SELECT * FROM read_json_auto('{temp_path}')
                    """)
                finally:
                    Path(temp_path).unlink(missing_ok=True)
                tables_created.append(name)
        else:
            # Try loading as-is (single object becomes single row)
            name = table_name or _normalize_table_name(file_path.stem)
            conn.execute(f"""
                CREATE TABLE {name} AS
                SELECT * FROM read_json_auto('{file_path}')
            """)
            tables_created.append(name)

    return tables_created


def _load_parquet_native(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
) -> list[str]:
    """Load Parquet file using DuckDB's native reader."""
    name = table_name or _normalize_table_name(file_path.stem)
    conn.execute(f"""
        CREATE TABLE {name} AS
        SELECT * FROM read_parquet('{file_path}')
    """)
    return [name]


def _load_excel(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
    sheet: str | None = None,
) -> list[str]:
    """Load Excel file - requires pandas bridge (no native DuckDB support)."""
    try:
        import pandas as pd
    except ImportError as err:
        raise ImportError(
            "pandas is required for Excel support: pip install pandas openpyxl"
        ) from err

    try:
        import openpyxl  # noqa: F401
    except ImportError as err:
        raise ImportError(
            "openpyxl is required for Excel support: pip install openpyxl"
        ) from err

    tables_created = []
    xlsx = pd.ExcelFile(file_path)

    sheets_to_load = [sheet] if sheet else [xlsx.sheet_names[0]]

    for sheet_name in sheets_to_load:
        if sheet_name not in xlsx.sheet_names:
            raise ValueError(f"Sheet '{sheet_name}' not found in {file_path}")

        df = xlsx.parse(sheet_name)
        name = (
            table_name if (table_name and sheet) else _normalize_table_name(sheet_name)
        )

        # Register pandas DataFrame and create table
        conn.register("_temp_excel", df)
        conn.execute(f"CREATE TABLE {name} AS SELECT * FROM _temp_excel")
        conn.unregister("_temp_excel")

        tables_created.append(name)

    return tables_created


def _load_generator(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
    generator_args: dict[str, Any] | None = None,
) -> list[str]:
    """Load mock data from a Python generator."""
    content = file_path.read_text()

    # Extract table name from @generates comment
    match = re.search(r"#\s*@generates:\s*(\S+)", content)
    gen_table_name = match.group(1) if match else file_path.stem

    # Load the module
    spec = importlib.util.spec_from_file_location("mock_generator", file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load generator from {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find and run generator
    generator_args = generator_args or {}
    result = None

    # Try class with generate() method
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and hasattr(attr, "generate"):
            instance = attr()
            result = instance.generate(**generator_args)
            break

    # Try generate() function
    if result is None and hasattr(module, "generate"):
        result = module.generate(**generator_args)

    if result is None:
        raise ValueError(f"No generator found in {file_path}")

    name = table_name or _normalize_table_name(gen_table_name)

    # Handle different return types
    if hasattr(result, "to_dict"):  # DataFrame-like
        # Convert to records and use JSON via temp file
        records = result.to_dict(orient="records")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(records, f)
            temp_path = f.name
        try:
            conn.execute(f"""
                CREATE TABLE {name} AS
                SELECT * FROM read_json_auto('{temp_path}')
            """)
        finally:
            Path(temp_path).unlink(missing_ok=True)
    elif isinstance(result, list):
        # List of dicts via temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(result, f)
            temp_path = f.name
        try:
            conn.execute(f"""
                CREATE TABLE {name} AS
                SELECT * FROM read_json_auto('{temp_path}')
            """)
        finally:
            Path(temp_path).unlink(missing_ok=True)
    else:
        raise ValueError(f"Generator returned unsupported type: {type(result)}")

    return [name]


class MockLoader:
    """Load multiple mock files into a DuckDB connection.

    Optimized for DuckDB native operations - minimal pandas.

    Example:
        loader = MockLoader()
        conn = loader.create_connection()

        loader.load_file(conn, Path("mocks/bronze_sales.yaml"))
        loader.load_file(conn, Path("mocks/stores.csv"))

        # Query the mock data
        result = conn.execute("SELECT * FROM bronze_raw_sales").fetchall()
    """

    def __init__(self) -> None:
        self._loaded_tables: dict[str, Path] = {}

    def create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create a fresh in-memory DuckDB connection."""
        return duckdb.connect(":memory:")

    def load_file(
        self,
        conn: duckdb.DuckDBPyConnection,
        file_path: Path,
        table_name: str | None = None,
        sheet: str | None = None,
    ) -> list[str]:
        """Load a mock file and return created table names."""
        tables = load_mock_file(file_path, conn, table_name, sheet)

        for table in tables:
            self._loaded_tables[table] = file_path

        return tables

    def load_files(
        self,
        conn: duckdb.DuckDBPyConnection,
        file_paths: list[Path],
    ) -> list[str]:
        """Load multiple mock files."""
        all_tables = []
        for path in file_paths:
            tables = self.load_file(conn, path)
            all_tables.extend(tables)
        return all_tables

    def get_loaded_tables(self) -> dict[str, Path]:
        """Get mapping of table names to source files."""
        return self._loaded_tables.copy()
