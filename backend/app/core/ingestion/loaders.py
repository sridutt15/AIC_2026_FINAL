"""Pure file loaders: read CSV/XLSX/JSON into a DataFrame with standardized column names.

Enterprise-generic: no hardcoded column names anywhere.
"""

from pathlib import Path

import pandas as pd


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Trim, lower-case, and replace spaces with underscores in all column names.

    Keeps column order and handles non-string headers by casting to str first.
    """
    df = df.copy()
    df.columns = [
        str(col).strip().lower().replace(" ", "_") for col in df.columns
    ]
    return df


def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV file into a DataFrame."""
    return standardize_columns(pd.read_csv(path))


def load_xlsx(path: Path) -> pd.DataFrame:
    """Load the first sheet of an Excel workbook into a DataFrame."""
    return standardize_columns(pd.read_excel(path, sheet_name=0))


def load_json(path: Path) -> pd.DataFrame:
    """Load a JSON file (array of records or single record) into a DataFrame."""
    return standardize_columns(pd.read_json(path))


def load_source(path: Path, filetype: str) -> pd.DataFrame:
    """Dispatch to the right loader based on a normalized file type string."""
    filetype = filetype.strip().lower().lstrip(".")
    if filetype == "csv":
        return load_csv(path)
    if filetype in ("xlsx", "xls"):
        return load_xlsx(path)
    if filetype == "json":
        return load_json(path)
    raise ValueError(f"Unsupported file type: {filetype!r}")
