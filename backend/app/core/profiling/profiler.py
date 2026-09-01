"""Deterministic column profiler. Pure function — same input, same output every time."""

from datetime import datetime

import pandas as pd

# Roles a column can be detected as.
ROLES = ("temporal", "numerical", "categorical", "identifier")

# Explicit, unambiguous date formats accepted for temporal detection. Strict formats avoid
# dateutil's lenient parser, which would treat strings like "T001" as valid times.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d.%m.%Y",
    "%Y%m%d",
    "%d-%b-%Y",
    "%d %b %Y",
    "%b %d, %Y",
)


def _detect_temporal(series: pd.Series) -> bool:
    """True if the column parses as a date for >90% of non-null values.

    Datetime dtypes count directly. Object/string columns are tested against an explicit
    list of date formats only — no lenient fallback — so IDs like "T001" never match.
    Numeric dtypes are never temporal here (Excel serial dates are out of scope).
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if not pd.api.types.is_object_dtype(series) and not pd.api.types.is_string_dtype(series):
        return False
    non_null = series.dropna().astype(str)
    if non_null.empty:
        return False
    best_ratio = 0.0
    for fmt in _DATE_FORMATS:
        parsed = pd.to_datetime(non_null, format=fmt, errors="coerce")
        ratio = parsed.notna().sum() / len(non_null)
        if ratio > best_ratio:
            best_ratio = ratio
        if best_ratio > 0.9:
            break
    return best_ratio > 0.9


def _looks_like_key_ints(series: pd.Series) -> bool:
    """True when an integer column behaves like a synthetic key (1..N, 1000..N).

    Deterministic test: values are non-negative, near-unique, and form a dense
    range (max-min <= 2 * count). Random count measures (clicks, quantities)
    have big gaps and never pass this; sequence keys always do.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    vals = non_null.astype("int64")
    if (vals < 0).any():
        return False
    span = int(vals.max() - vals.min())
    return span <= 2 * len(non_null)


def _detect_role(series: pd.Series, cardinality_ratio: float) -> str:
    """Heuristic role detection. Precedence order matters:

    temporal   : parses as a date for >90% of non-null values (checked first — unique
                 timestamps are still the time axis, not identifiers)
    numerical  : float dtype is ALWAYS a measure. Continuous measures (money,
                 rates, prices) are near-unique by nature but are measures,
                 never identifiers.
    identifier : cardinality ratio > 0.95 on a string column, OR an integer
                 column that is near-unique AND a dense 1..N-style key range.
    numerical  : other numeric dtypes (integer count/quantity measures).
    categorical: everything else
    """
    if _detect_temporal(series):
        return "temporal"
    if pd.api.types.is_float_dtype(series):
        return "numerical"
    if cardinality_ratio > 0.95:
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            return "identifier"
        if (
            pd.api.types.is_integer_dtype(series)
            and not pd.api.types.is_bool_dtype(series)
            and _looks_like_key_ints(series)
        ):
            return "identifier"
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return "numerical"
    return "categorical"


def _json_safe(value) -> object:
    """Convert a numpy/pandas scalar to a JSON-serializable Python value."""
    if value is None or value is pd.NA or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    try:  # numpy scalars
        return value.item()
    except AttributeError:
        pass
    if isinstance(value, datetime):  # pandas Timestamp is a datetime subclass
        return value.isoformat()
    return str(value)


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Profile every column of a DataFrame deterministically.

    Returns {"row_count": int, "columns": [{...per-column stats...}, ...]}.
    """
    row_count = int(len(df))
    columns = []
    for name, series in df.items():
        non_null = series.dropna()
        null_count = row_count - len(non_null)
        null_ratio = (null_count / row_count) if row_count else 0.0
        cardinality = int(non_null.nunique())
        is_unique = row_count > 0 and cardinality == row_count
        cardinality_ratio = (cardinality / len(non_null)) if len(non_null) else 0.0
        role = _detect_role(series, cardinality_ratio)
        samples = [_json_safe(v) for v in non_null.head(5).tolist()]
        columns.append(
            {
                "name": str(name),
                "dtype": str(series.dtype),
                "null_count": int(null_count),
                "null_ratio": round(float(null_ratio), 4),
                "cardinality": cardinality,
                "cardinality_ratio": round(float(cardinality_ratio), 4),
                "is_unique": bool(is_unique),
                "detected_role": role,
                "sample_values": samples,
            }
        )
    return {"row_count": row_count, "columns": columns}
