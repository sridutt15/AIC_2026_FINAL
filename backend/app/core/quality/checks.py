"""Deterministic data-quality checks. Pure functions — no ML, no LLM.

Every check returns a list of issue dicts:
    {"column": str, "issue_type": str, "severity": str, "affected_row_count": int}

Severity levels: "high" (blocks trust), "medium" (warrants review), "low" (informational).
All thresholds are constants or contract-driven — never hardcoded column names.
"""

import pandas as pd

# Null-ratio above which a column is flagged (Phase 3 default; may become
# contract-driven in later phases).
NULL_RATIO_THRESHOLD = 0.05

# IQR outlier detection: k * IQR beyond the quartiles. k=1.5 is Tukey's convention.
IQR_K = 1.5

# Columns with fewer than this many numeric values are skipped for outlier checks
# (tiny samples make IQR meaningless).
MIN_OUTLIER_SUPPORT = 8

MEASURE_ISSUE = "invalid_range"
TYPE_ISSUE = "type_violation"


def _issue(column: str, issue_type: str, severity: str, count: int) -> dict:
    return {
        "column": column,
        "issue_type": issue_type,
        "severity": severity,
        "affected_row_count": int(count),
    }


def check_missing_values(df: pd.DataFrame, threshold: float = NULL_RATIO_THRESHOLD) -> list:
    """Flag columns whose null ratio exceeds `threshold` (default >5%).

    Severity: ratio > 0.3 -> high, > 0.1 -> medium, else low.
    """
    issues = []
    row_count = len(df)
    if row_count == 0:
        return issues
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        ratio = null_count / row_count
        if ratio > threshold:
            severity = "high" if ratio > 0.3 else ("medium" if ratio > 0.1 else "low")
            issues.append(_issue(col, "missing_values", severity, null_count))
    return issues


def check_duplicates(df: pd.DataFrame) -> list:
    """Flag fully duplicate rows (all columns identical).

    affected_row_count = number of rows that are copies of an earlier row.
    Severity: >10% of rows -> high, >2% -> medium, else low.
    """
    issues = []
    if df.empty:
        return issues
    dup_mask = df.duplicated(keep="first")
    dup_count = int(dup_mask.sum())
    if dup_count > 0:
        ratio = dup_count / len(df)
        severity = "high" if ratio > 0.10 else ("medium" if ratio > 0.02 else "low")
        issues.append(_issue("(all columns)", "duplicate_rows", severity, dup_count))
    return issues


def check_invalid_ranges(df: pd.DataFrame, contract: dict | None = None) -> list:
    """Flag impossible values in measure columns.

    Default rule (documented): a measure column must not contain negatives, unless the
    contract explicitly allows it via {"allow_negative": [col, ...]} or the column's
    access/behavior metadata says so. Contract-driven, never column-name-driven.
    """
    issues = []
    if contract is None:
        contract = {}
    allow_negative = set(contract.get("allow_negative", []))
    measures = contract.get("columns_by_role", {}).get("measure", [])
    if not measures:
        # Fall back: any numeric column that is not flagged otherwise.
        measures = [
            c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
        ]
    for col in measures:
        if col not in df.columns or col in allow_negative:
            continue
        series = df[col]
        if not pd.api.types.is_numeric_dtype(series):
            continue
        neg_count = int((series < 0).sum())
        if neg_count > 0:
            issues.append(_issue(col, MEASURE_ISSUE, "high", neg_count))
    return issues


def check_type_violations(df: pd.DataFrame, profile: dict | None = None) -> list:
    """Flag values that don't match the column's declared dtype from profiling.

    Deterministic rule: for each profiled column declared numeric whose dataframe dtype is
    object/string, count non-null values that fail numeric coercion. (When CSV load already
    produced the declared dtype, no issue is reported — this catches mixed-type columns.)
    """
    issues = []
    if profile is None:
        return issues
    for col_profile in profile.get("columns", []):
        name = col_profile["name"]
        declared = col_profile["dtype"]
        if name not in df.columns:
            continue
        series = df[name]
        # Declared numeric but loaded as object/string -> count unparseable values.
        # Vite/pandas 3 may represent strings as a dedicated string dtype, so test both.
        if ("int" in declared or "float" in declared) and (
            pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)
        ):
            coerced = pd.to_numeric(series, errors="coerce")
            bad = int((coerced.isna() & series.notna()).sum())
            if bad > 0:
                issues.append(_issue(name, TYPE_ISSUE, "medium", bad))
    return issues


def check_outliers(df: pd.DataFrame, contract: dict | None = None) -> list:
    """IQR-based outlier flags on numeric columns (Tukey, k=1.5).

    Skips columns with < MIN_OUTLIER_SUPPORT non-null values (IQR is meaningless on
    tiny samples). Severity: always "low" (statistical outliers are informational —
    they may be real spikes the business cares about).
    """
    issues = []
    for col in df.columns:
        series = df[col]
        if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
            continue
        non_null = series.dropna()
        if len(non_null) < MIN_OUTLIER_SUPPORT:
            continue
        q1 = float(non_null.quantile(0.25))
        q3 = float(non_null.quantile(0.75))
        iqr = q3 - q1
        if iqr == 0:
            continue  # constant column — no spread, no outliers
        lower = q1 - IQR_K * iqr
        upper = q3 + IQR_K * iqr
        out_count = int(((non_null < lower) | (non_null > upper)).sum())
        if out_count > 0:
            issues.append(_issue(col, "outlier", "low", out_count))
    return issues
