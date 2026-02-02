"""🐀 Ratatouille Parsers - Transform messy files into clean DataFrames.

Built-in parsers for common formats. Use by name or pass custom functions.

Usage:
    # Use custom parser function
    rat.ice_ingest("landing/weird.xlsx", "bronze.data", parser=my_custom_parser)

    # List available parsers
    rat.parsers()

To add a built-in parser:
1. Create a parser file: parsers/my_format.py
2. Define a function: def parse_my_format(data: BytesIO, filename: str) -> pd.DataFrame
3. Import and register it in PARSERS dict below
"""

from typing import Callable, Protocol
from io import BytesIO
import pandas as pd


class Parser(Protocol):
    """Parser function signature.

    A parser takes file data and returns a DataFrame.
    """
    def __call__(self, data: BytesIO, filename: str) -> pd.DataFrame:
        """Parse file data into a DataFrame.

        Args:
            data: File contents as BytesIO
            filename: Original filename (for metadata extraction)

        Returns:
            Cleaned DataFrame ready for ingestion
        """
        ...


# Parser registry - add new parsers here!
PARSERS: dict[str, Callable[[BytesIO, str], pd.DataFrame]] = {
    # Example:
    # "my_format": parse_my_format,
}


def get_parser(name: str) -> Callable[[BytesIO, str], pd.DataFrame]:
    """Get a parser by name.

    Args:
        name: Parser name (e.g., "my_format")

    Returns:
        Parser function

    Raises:
        KeyError: If parser not found
    """
    if name not in PARSERS:
        available = ", ".join(PARSERS.keys()) if PARSERS else "(none registered)"
        raise KeyError(f"Parser '{name}' not found. Available: {available}")
    return PARSERS[name]


def list_parsers() -> dict[str, str]:
    """List all available parsers with descriptions.

    Returns:
        Dict mapping parser name to description
    """
    descriptions = {
        # Add descriptions for built-in parsers here
    }
    return {name: descriptions.get(name, "No description") for name in PARSERS}


def register_parser(name: str, func: Callable[[BytesIO, str], pd.DataFrame]) -> None:
    """Register a custom parser.

    Args:
        name: Parser name
        func: Parser function (data: BytesIO, filename: str) -> pd.DataFrame

    Example:
        from ratatouille.parsers import register_parser

        def my_parser(data, filename):
            df = pd.read_excel(data, skiprows=5)
            return df

        register_parser("my_format", my_parser)
    """
    PARSERS[name] = func
    print(f"✅ Registered parser: {name}")
