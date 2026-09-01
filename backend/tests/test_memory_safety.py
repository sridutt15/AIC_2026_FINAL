"""Memory-safety tests for canonical dataset loading + KPI-series groupbys.

Regression tests for the Phase 8 production 500s:
    1. pd.read_csv on a >1GB canonical CSV died with ParserError (out of memory).
    2. groupby(...).sum() on a raw datetime/string axis died with
       StringHashTable.factorize MemoryError.

The fixes: load_canonical_csv (size ceiling + chunked, dtype-optimized load)
and int-backed period keys in _series_for. These tests prove both behaviors
at small scale.
"""

import numpy as np
import pandas as pd
import pytest

from app.core.canonical.reconciler import MAX_CANONICAL_ROWS, load_canonical_csv
from app.core.kpi_engine.validation import _series_for, validate_kpi


def test_load_canonical_csv_downcasts_and_preserves_values(tmp_path):
    """Chunked load keeps values intact and downcasts float64 -> float32."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-04-04", periods=300, freq="D").strftime("%Y-%m-%d"),
            "region": ["APAC", "EMEA", "LATAM", "North America"] * 75,
            "spend": [round(v, 2) for v in np.random.default_rng(1).uniform(500, 900, 300)],
        }
    )
    path = tmp_path / "canonical.csv"
    df.to_csv(path, index=False)

    loaded = load_canonical_csv(path)
    assert len(loaded) == 300
    # Values survive (float32 aggregation-exact for 2-decimal money values).
    assert np.allclose(loaded["spend"].to_numpy(), df["spend"].to_numpy(), rtol=1e-5)
    assert str(loaded["spend"].dtype) == "float32"
    # Low-cardinality object column becomes category (cheap factorization).
    assert str(loaded["region"].dtype) == "category"


def test_load_canonical_csv_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_canonical_csv(tmp_path / "nope.csv")


def test_size_ceiling_rejects_oversized_dataset(tmp_path, monkeypatch):
    """A canonical CSV estimated above MAX_CANONICAL_ROWS is rejected with a
    clear ValueError (API maps it to 413) instead of an opaque MemoryError."""
    df = pd.DataFrame({"date": ["2026-01-01"], "v": [1.0]})
    path = tmp_path / "huge.csv"
    df.to_csv(path, index=False)

    # Path.stat is read-only on the instance; patch the class-wide method but
    # only for this test, faking a huge st_size for this one path.
    from pathlib import Path as _Path

    real_stat = _Path.stat

    def fake_stat(self, *args, **kwargs):
        if self == path:
            return type("S", (), {"st_size": MAX_CANONICAL_ROWS * 10_000})()
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(_Path, "stat", fake_stat)
    with pytest.raises(ValueError, match="too large"):
        load_canonical_csv(path)


def _canonical_frame(n_days=30, rows_per_day=20):
    dates = pd.date_range("2026-04-04", periods=n_days, freq="D")
    rng = np.random.default_rng(7)
    frame = pd.DataFrame(
        {
            "date": np.repeat(dates.strftime("%Y-%m-%d"), rows_per_day),
            "region": rng.choice(["APAC", "EMEA", "LATAM", "North America"], n_days * rows_per_day),
            "revenue": rng.uniform(50, 500, n_days * rows_per_day).round(2),
        }
    )
    return frame


def test_series_for_sum_groups_by_day_exactly():
    """The int-backed groupby yields identical sums to the naive datetime
    groupby (equivalence, memory-safety regressed)."""
    df = _canonical_frame()
    kpi = {
        "measure": "revenue",
        "aggregation": "sum",
        "time_column": "date",
        "slice_columns": [],
    }
    series = _series_for(kpi, df)
    naive = df.assign(d=pd.to_datetime(df["date"])).groupby("d")["revenue"].sum()
    assert len(series) == len(naive)
    assert np.allclose(series.to_numpy(), naive.to_numpy())


def test_series_for_sliced_sum_collapses_slices():
    """Sliced sum KPIs collapse to the per-period total (same as naive)."""
    df = _canonical_frame(n_days=10, rows_per_day=30)
    kpi = {
        "measure": "revenue",
        "aggregation": "sum",
        "time_column": "date",
        "slice_columns": ["region"],
    }
    series = _series_for(kpi, df)
    naive = (
        df.assign(d=pd.to_datetime(df["date"]))
        .groupby(["d", "region"])["revenue"]
        .sum()
        .groupby(level=0)
        .sum()
    )
    assert len(series) == len(naive)
    assert np.allclose(series.to_numpy(), naive.to_numpy())


def test_series_for_avg_matches_naive_weighted_mean():
    """avg aggregation: collapsed value == mean of all rows in the period."""
    df = _canonical_frame(n_days=12, rows_per_day=25)
    kpi = {
        "measure": "revenue",
        "aggregation": "avg",
        "time_column": "date",
        "slice_columns": ["region"],
    }
    series = _series_for(kpi, df)
    naive = df.assign(d=pd.to_datetime(df["date"])).groupby("d")["revenue"].mean()
    assert np.allclose(series.to_numpy(), naive.to_numpy())


def test_series_for_drops_null_dates():
    """Rows with unparseable dates are excluded (no crash, no fabrication)."""
    df = _canonical_frame(n_days=8, rows_per_day=10)
    df.loc[0, "date"] = "not-a-date"
    kpi = {"measure": "revenue", "aggregation": "sum", "time_column": "date", "slice_columns": []}
    series = _series_for(kpi, df)
    assert len(series) == 8  # the 8 clean days remain


def test_validate_kpi_on_daily_frame():
    df = _canonical_frame(n_days=30, rows_per_day=15)
    kpi = {
        "name": "sum(revenue)",
        "measure": "revenue",
        "aggregation": "sum",
        "time_column": "date",
        "slice_columns": [],
    }
    result = validate_kpi(kpi, df)
    assert result["status"] == "valid"
