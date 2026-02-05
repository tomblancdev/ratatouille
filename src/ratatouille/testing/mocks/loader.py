"""Load mock data from various formats into DuckDB.

Supported formats:
- YAML (.yaml, .yml) - with 'table' and 'rows' keys
- CSV (.csv) - filename becomes table name
- Excel (.xlsx, .xls) - sheet names become table names
- JSON (.json) - with 'table' and 'rows' keys, or array of records
- Parquet (.parquet) - filename becomes table name
- Python generators (.py) - classes with generate() method
"""

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml


def load_mock_file(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
    sheet: str | None = None,
) -> list[str]:
    """Load a mock data file into DuckDB tables.

    Args:
        file_path: Path to the mock data file
        conn: DuckDB connection to load data into
        table_name: Override table name (default: derived from file/content)
        sheet: Sheet name for Excel files (None = all sheets)

    Returns:
        List of table names created
    """
    suffix = file_path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        return _load_yaml(file_path, conn, table_name)
    elif suffix == ".csv":
        return _load_csv(file_path, conn, table_name)
    elif suffix in (".xlsx", ".xls"):
        return _load_excel(file_path, conn, table_name, sheet)
    elif suffix == ".json":
        return _load_json(file_path, conn, table_name)
    elif suffix == ".parquet":
        return _load_parquet(file_path, conn, table_name)
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
    """Load YAML mock data.

    Expected format:
    ```yaml
    table: bronze.raw_sales
    rows:
      - txn_id: "T001"
        quantity: 2
    ```

    Or multiple tables:
    ```yaml
    tables:
      - table: bronze.raw_sales
        rows: [...]
      - table: bronze.stores
        rows: [...]
    ```
    """
    with open(file_path) as f:
        data = yaml.safe_load(f)

    tables_created = []

    # Single table format
    if "table" in data and "rows" in data:
        name = table_name or _normalize_table_name(data["table"])
        df = pd.DataFrame(data["rows"])
        _register_dataframe(conn, name, df)
        tables_created.append(name)

    # Multiple tables format
    elif "tables" in data:
        for table_def in data["tables"]:
            name = _normalize_table_name(table_def["table"])
            df = pd.DataFrame(table_def["rows"])
            _register_dataframe(conn, name, df)
            tables_created.append(name)

    # Just rows (use table_name or filename)
    elif "rows" in data:
        name = table_name or _normalize_table_name(file_path.stem)
        df = pd.DataFrame(data["rows"])
        _register_dataframe(conn, name, df)
        tables_created.append(name)

    else:
        raise ValueError(f"Invalid YAML format in {file_path}: expected 'table' and 'rows' keys")

    return tables_created


def _load_csv(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
) -> list[str]:
    """Load CSV file as a table."""
    name = table_name or _normalize_table_name(file_path.stem)
    df = pd.read_csv(file_path)
    _register_dataframe(conn, name, df)
    return [name]


def _load_excel(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
    sheet: str | None = None,
) -> list[str]:
    """Load Excel file as tables (one per sheet)."""
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        raise ImportError("openpyxl is required for Excel support: pip install openpyxl")

    tables_created = []
    xlsx = pd.ExcelFile(file_path)

    sheets_to_load = [sheet] if sheet else xlsx.sheet_names

    for sheet_name in sheets_to_load:
        if sheet_name not in xlsx.sheet_names:
            raise ValueError(f"Sheet '{sheet_name}' not found in {file_path}")

        df = xlsx.parse(sheet_name)
        name = table_name if (table_name and sheet) else _normalize_table_name(sheet_name)
        _register_dataframe(conn, name, df)
        tables_created.append(name)

    return tables_created


def _load_json(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
) -> list[str]:
    """Load JSON mock data.

    Expected formats:
    1. Object with 'table' and 'rows':
       {"table": "bronze.raw_sales", "rows": [...]}

    2. Array of records:
       [{"txn_id": "T001"}, {"txn_id": "T002"}]

    3. Multiple tables:
       {"tables": [{"table": "...", "rows": [...]}, ...]}
    """
    with open(file_path) as f:
        data = json.load(f)

    tables_created = []

    if isinstance(data, list):
        # Array of records
        name = table_name or _normalize_table_name(file_path.stem)
        df = pd.DataFrame(data)
        _register_dataframe(conn, name, df)
        tables_created.append(name)

    elif isinstance(data, dict):
        if "table" in data and "rows" in data:
            name = table_name or _normalize_table_name(data["table"])
            df = pd.DataFrame(data["rows"])
            _register_dataframe(conn, name, df)
            tables_created.append(name)

        elif "tables" in data:
            for table_def in data["tables"]:
                name = _normalize_table_name(table_def["table"])
                df = pd.DataFrame(table_def["rows"])
                _register_dataframe(conn, name, df)
                tables_created.append(name)

        elif "rows" in data:
            name = table_name or _normalize_table_name(file_path.stem)
            df = pd.DataFrame(data["rows"])
            _register_dataframe(conn, name, df)
            tables_created.append(name)

        else:
            raise ValueError(f"Invalid JSON format in {file_path}")

    return tables_created


def _load_parquet(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
) -> list[str]:
    """Load Parquet file as a table."""
    name = table_name or _normalize_table_name(file_path.stem)
    df = pd.read_parquet(file_path)
    _register_dataframe(conn, name, df)
    return [name]


def _load_generator(
    file_path: Path,
    conn: duckdb.DuckDBPyConnection,
    table_name: str | None = None,
    generator_args: dict[str, Any] | None = None,
) -> list[str]:
    """Load mock data from a Python generator.

    The file should contain a class with a generate() method that returns a DataFrame,
    or a function called 'generate' that returns a DataFrame.

    The @generates comment specifies the table name:
    ```python
    # @generates: bronze.raw_sales

    class MockGenerator:
        def generate(self, num_records: int = 100) -> pd.DataFrame:
            ...
    ```
    """
    # Read the file to extract metadata
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

    # Find generator class or function
    generator_args = generator_args or {}
    df: pd.DataFrame | None = None

    # Try to find a class with generate() method
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and hasattr(attr, "generate"):
            instance = attr()
            df = instance.generate(**generator_args)
            break

    # Try to find a generate() function
    if df is None and hasattr(module, "generate"):
        df = module.generate(**generator_args)

    if df is None:
        raise ValueError(f"No generator found in {file_path}. "
                        "Expected a class with generate() method or a generate() function.")

    name = table_name or _normalize_table_name(gen_table_name)
    _register_dataframe(conn, name, df)
    return [name]


def _register_dataframe(
    conn: duckdb.DuckDBPyConnection,
    name: str,
    df: pd.DataFrame,
) -> None:
    """Register a DataFrame as a table in DuckDB."""
    conn.register(name, df)
    conn.execute(f"CREATE TABLE {name} AS SELECT * FROM {name}")


class MockLoader:
    """Load multiple mock files into a DuckDB connection.

    Example:
        loader = MockLoader()
        conn = loader.create_connection()

        loader.load_file(conn, Path("mocks/bronze_sales.yaml"))
        loader.load_file(conn, Path("mocks/stores.csv"))

        # Query the mock data
        result = conn.execute("SELECT * FROM bronze_raw_sales").fetchdf()
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
