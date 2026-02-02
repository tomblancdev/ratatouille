"""🐀 Data Cleaning Utilities - Ensure consistent null handling for Parquet/Iceberg.

This module handles the pandas NaN/<NA>/None mess to ensure clean storage.
Validation (error on nulls, required columns, etc.) is handled separately by Dagster checkers.
"""

import pandas as pd
import numpy as np


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a DataFrame for Iceberg/Parquet storage.

    - Converts string "NaN", "NA", "<NA>", etc. to proper None
    - Keeps numeric NaN as-is (Parquet stores them as NULL correctly)
    - Normalizes pandas nullable types to standard numpy types

    Does NOT validate or fill - that's for Dagster checkers.

    Args:
        df: DataFrame to clean

    Returns:
        Cleaned DataFrame with consistent nulls

    Example:
        df = clean_dataframe(df)
    """
    df = df.copy()

    # String values that should be treated as null
    NULL_STRINGS = {"", "NaN", "nan", "NAN", "NA", "na", "N/A", "n/a", "<NA>",
                    "null", "NULL", "None", "none", "#N/A", "#NA", "-"}

    for col in df.columns:
        dtype = df[col].dtype

        # For object/string columns: replace string null representations with None
        if dtype == object or isinstance(dtype, pd.StringDtype):
            df[col] = df[col].apply(
                lambda x: None if (isinstance(x, str) and x.strip() in NULL_STRINGS) else x
            )
            # Convert to object dtype (standard string)
            if isinstance(dtype, pd.StringDtype):
                df[col] = df[col].astype(object)

        # Convert pandas nullable Int64Dtype
        elif isinstance(dtype, pd.Int64Dtype):
            if df[col].isna().any():
                df[col] = df[col].astype("float64")  # float64 can hold NaN
            else:
                df[col] = df[col].astype("int64")

        # Convert pandas Float64Dtype to standard float64
        elif isinstance(dtype, pd.Float64Dtype):
            df[col] = df[col].astype("float64")

        # Convert pandas BooleanDtype
        elif isinstance(dtype, pd.BooleanDtype):
            if df[col].isna().any():
                df[col] = df[col].astype(object)
            else:
                df[col] = df[col].astype(bool)

    return df


def report_nulls(df: pd.DataFrame) -> dict:
    """Generate a report of null values in a DataFrame.

    Args:
        df: DataFrame to analyze

    Returns:
        Dict with null statistics

    Example:
        report = report_nulls(df)
        # → {"total_nulls": 150, "columns": {"price": 50, "name": 100}, "pct": 5.2}
    """
    null_counts = df.isna().sum()
    total_nulls = null_counts.sum()
    total_cells = df.size

    cols_with_nulls = {col: int(count) for col, count in null_counts.items() if count > 0}

    return {
        "total_nulls": int(total_nulls),
        "total_cells": int(total_cells),
        "pct": round(100 * total_nulls / total_cells, 2) if total_cells > 0 else 0,
        "columns": cols_with_nulls,
    }
