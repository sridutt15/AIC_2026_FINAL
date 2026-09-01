"""KPI computation tests: value/baseline/benchmark against hand-computed numbers."""

import numpy as np
import pandas as pd

from app.core.kpi_engine.computation import compute_kpi


def _kpi(aggregation: str = "sum") -> dict:
    return {
        "name": f"{aggregation}(revenue)",
        "measure": "revenue",
        "aggregation": aggregation,
        "slice_columns": [],
        "time_column": "date",
    }


def _df_from_trend(values: list) -> pd.DataFrame:
    n = len(values)
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "revenue": [float(v) for v in values],
        }
    )


def test_value_benchmark_on_constant_series():
    # 12 daily rows of 100 -> daily KPI value 100, benchmark 100
    df = _df_from_trend([100.0] * 12)
    result = compute_kpi(_kpi(), df)
    assert abs(result["value"] - 100.0) < 1e-9
    assert abs(result["benchmark"] - 100.0) < 1e-9
    assert result["period_count"] == 12
    assert len(result["trend"]) == 12


def test_baseline_prior_period_average():
    # Baseline = mean of the prior 7 periods before the latest.
    # Trend: 10, 11, ..., 21 (12 periods). Prior-7 window = 14..20 -> mean 17.
    values = list(range(10, 22))
    df = _df_from_trend(values)
    result = compute_kpi(_kpi(), df)
    assert abs(result["value"] - 21.0) < 1e-9
    assert abs(result["baseline"] - 17.0) < 1e-9
    assert abs(result["benchmark"] - float(np.mean(values))) < 1e-9


def test_trend_values_and_periods_sorted():
    values = [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0]
    df = _df_from_trend(values)
    result = compute_kpi(_kpi(), df)
    assert [t["value"] for t in result["trend"]] == [float(v) for v in values]
    assert result["trend"][0]["period"].startswith("2024-01-01")
    assert result["trend"][-1]["period"].startswith("2024-01-09")


def test_bootstrap_ci_contains_true_mean():
    # Known distribution: values around mean 100 with noise
    rng = np.random.default_rng(7)
    values = list(100.0 + rng.normal(0.0, 5.0, size=40))
    df = _df_from_trend(values)
    result = compute_kpi(_kpi(), df)
    ci = result["confidence_interval"]
    assert ci is not None
    true_mean = float(np.mean(values))
    assert ci["lower"] <= true_mean <= ci["upper"]
    assert ci["lower"] < ci["upper"]


def test_bootstrap_ci_deterministic():
    values = [10.0, 20.0, 15.0, 25.0, 30.0, 5.0, 12.0, 18.0, 22.0, 28.0]
    df = _df_from_trend(values)
    first = compute_kpi(_kpi(), df)
    second = compute_kpi(_kpi(), df)
    assert first == second  # fixed seed -> identical CI


def test_short_history_ci_none():
    df = _df_from_trend([10.0, 12.0])  # 2 periods -> no CI
    result = compute_kpi(_kpi(), df)
    assert result["confidence_interval"] is None
    assert result["period_count"] == 2


def test_avg_aggregation_matches_mean():
    # avg KPI on a frame where each period has multiple rows
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    rows = []
    for i, d in enumerate(dates):
        rows.append({"date": d, "revenue": float(i)})
        rows.append({"date": d, "revenue": float(i + 10)})
    df = pd.DataFrame(rows)
    result = compute_kpi(_kpi(aggregation="avg"), df)
    # each period's avg = i + 5; latest period i=9 -> 14
    assert abs(result["value"] - 14.0) < 1e-9
    assert abs(result["benchmark"] - float(np.mean([i + 5 for i in range(10)]))) < 1e-9


def test_count_aggregation():
    dates = pd.date_range("2024-01-01", periods=9, freq="D")
    rows = []
    for d in dates:
        rows.append({"date": d, "revenue": 1.0})
        rows.append({"date": d, "revenue": 2.0})
        rows.append({"date": d, "revenue": None})  # not counted
    df = pd.DataFrame(rows)
    result = compute_kpi({**_kpi("count"), "aggregation": "count"}, df)
    assert abs(result["value"] - 2.0) < 1e-9  # 2 non-null per period
