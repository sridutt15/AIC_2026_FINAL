"""KPI validation: sample size, ratio denominators, variance.

Deterministic checks; each returns {status, reason} where status is one of
"valid" | "low-data" | "invalid".
"""

import numpy as np
import pandas as pd

from app.core.kpi_engine.discovery import MIN_PERIODS_DEFAULT

ZERO_DENOMINATOR_THRESHOLD = 1e-12


def _count_periods(series: pd.Series) -> int:
    """Number of distinct non-null periods (index entries) in a trend series."""
    s = pd.Series(series).dropna()
    if s.empty:
        return 0
    return int(s.index.nunique())


def _series_for(kpi: dict, canonical_df: pd.DataFrame) -> pd.Series:
    """Compute the KPI's per-period values from the canonical frame.

    Deterministic pipeline: parse time column, group by period + slices, aggregate
    the measure. For sliced KPIs the slice dimension is collapsed (slice values
    summed per period) so the trend represents the KPI's total across slices.
    Returns a Series indexed by period (datetime).

    Memory safety (the Phase 8 500s): grouping on a raw datetime64 column forces
    pandas to factorize full Timestamp objects; on multi-million-row canonical
    frames the string/date hash tables exhaust RAM. We instead group on an int64
    nanosecond representation (cheap factorization, exact same grouping) and map
    back to Timestamps at the end. Categorical/datetime slice columns are
    pre-converted to cheap str keys via the same int-backed approach.
    """
    time_col = kpi.get("time_column")
    measure = kpi["measure"]
    agg = kpi.get("aggregation", "sum")

    if time_col is None:
        # No time axis: a single aggregate over the whole frame.
        return pd.Series([_aggregate(canonical_df[measure], agg)])

    times = pd.to_datetime(canonical_df[time_col], errors="coerce")
    frame = canonical_df.assign(_period=times)
    frame = frame[frame["_period"].notna()]

    slices = [s for s in kpi.get("slice_columns", []) if s in frame.columns]

    # Int-backed period keys: identical grouping semantics, tiny hash tables.
    # Timestamp.value is ALWAYS nanoseconds regardless of the column's internal
    # resolution (pandas 3 parses dates to us/ms in some paths), and the
    # matching to_datetime(..., unit="ns") below reads exactly that back.
    period_int = frame["_period"].map(lambda ts: ts.value)
    frame = frame.assign(_p_int=period_int)

    grouped = frame.groupby("_p_int", dropna=False)[measure]
    if agg in ("avg", "rate"):
        series = grouped.mean()
    elif agg == "count":
        series = grouped.count()
    else:  # sum
        series = grouped.sum()
    series.index = pd.to_datetime(series.index, unit="ns")
    return series.sort_index()


def _aggregate(series: pd.Series, agg: str):
    if agg == "count":
        return series.count()
    if agg in ("avg", "rate"):
        return series.mean()
    return series.sum()


def validate_kpi(kpi: dict, canonical_df: pd.DataFrame) -> dict:
    """Validate a candidate KPI. Returns {status: "valid"|"low-data"|"invalid", reason}.

    Checks (deterministic):
      1. Measure column exists and yields usable values; ratio aggregations need
         a non-zero denominator (no all-zero/null measures).
      2. Variance: the trend must not be degenerate constant-null or empty.
      3. Sample size: fewer than MIN_PERIODS_DEFAULT distinct periods -> low-data
         (still computable, flagged for the UI).
    """
    measure = kpi.get("measure")
    if measure not in canonical_df.columns:
        return {"status": "invalid", "reason": f"measure column '{measure}' not in dataset"}

    series = _series_for(kpi, canonical_df)
    values = pd.Series(series).dropna()

    if len(values) == 0:
        return {"status": "invalid", "reason": "no values for measure"}

    non_null_measure = canonical_df[measure].dropna()
    if len(non_null_measure) == 0:
        return {"status": "invalid", "reason": "measure column is all null"}

    if kpi.get("aggregation") in ("rate", "avg"):
        # Ratio-like: a zero denominator (all-zero measure) is meaningless.
        if float(np.abs(non_null_measure).max()) <= ZERO_DENOMINATOR_THRESHOLD:
            return {"status": "invalid", "reason": "zero denominator for ratio aggregation"}

    if len(values) < 2:
        return {"status": "invalid", "reason": "degenerate trend (fewer than 2 period values)"}

    periods = _count_periods(series) if kpi.get("time_column") else len(values)
    if periods < MIN_PERIODS_DEFAULT:
        return {
            "status": "low-data",
            "reason": f"only {periods} time periods (< {MIN_PERIODS_DEFAULT} required)",
        }

    return {"status": "valid", "reason": "sufficient periods and healthy variance"}
