"""Contribution decomposition tests: designed movements recovered exactly."""

import pandas as pd
import pytest

from app.core.drivers.contribution import decompose_contribution


def _kpi(aggregation: str = "sum") -> dict:
    return {
        "name": f"{aggregation}(revenue)",
        "measure": "revenue",
        "aggregation": aggregation,
        "slice_columns": ["region"],
        "time_column": "date",
    }


def _movement_df() -> pd.DataFrame:
    """Two days, two regions. Day 2: A +10 (110-100), B -3 (47-50) -> total +7."""
    return pd.DataFrame(
        {
            "date": ["2024-01-01"] * 2 + ["2024-01-02"] * 2,
            "region": ["A", "B", "A", "B"],
            "revenue": [100.0, 50.0, 110.0, 47.0],
        }
    )


def test_recovers_designed_contributions():
    result = decompose_contribution(_movement_df(), _kpi(), ["region"])
    assert result["total_movement"] == pytest.approx(7.0, abs=1e-6)
    dims = {d["dimension"]: d for d in result["dimensions"]}
    slices = {s["slice"]: s for s in dims["region"]["slices"]}
    assert slices["A"]["contribution"] == pytest.approx(10.0, abs=1e-6)
    assert slices["B"]["contribution"] == pytest.approx(-3.0, abs=1e-6)
    # Sum of contributions equals total (waterfall identity)
    total = sum(s["contribution"] for s in dims["region"]["slices"])
    assert total == pytest.approx(result["total_movement"], abs=1e-6)
    # Residual reported as ~0
    assert abs(dims["region"]["reconciliation_residual"]) < 1e-4


def test_slices_ranked_by_absolute_contribution():
    result = decompose_contribution(_movement_df(), _kpi(), ["region"])
    slices = result["dimensions"][0]["slices"]
    contributions = [abs(s["contribution"]) for s in slices]
    assert contributions == sorted(contributions, reverse=True)


def test_share_pct_and_direction():
    result = decompose_contribution(_movement_df(), _kpi(), ["region"])
    slices = {s["slice"]: s for s in result["dimensions"][0]["slices"]}
    assert slices["A"]["direction"] == "up"
    assert slices["B"]["direction"] == "down"
    assert slices["A"]["share_pct"] == pytest.approx(10 / 7 * 100, abs=0.1)


def test_new_slice_in_after_period():
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02", "2024-01-02"],
            "region": ["A", "B", "A", "B", "C"],
            "revenue": [100.0, 50.0, 110.0, 47.0, 5.0],
        }
    )
    result = decompose_contribution(df, _kpi(), ["region"])
    slices = {s["slice"]: s for s in result["dimensions"][0]["slices"]}
    assert slices["C"]["before"] == 0.0
    assert slices["C"]["contribution"] == pytest.approx(5.0, abs=1e-6)
    assert result["total_movement"] == pytest.approx(12.0, abs=1e-6)


def test_ratio_metric_decomposition_runs():
    # avg metric: decomposition runs with volume+mix effects and reports residual
    df = pd.DataFrame(
        {
            "date": ["2024-01-01"] * 3 + ["2024-01-02"] * 3,
            "region": ["A", "A", "B", "A", "B", "B"],
            "revenue": [10.0, 20.0, 30.0, 20.0, 40.0, 60.0],
        }
    )
    result = decompose_contribution(df, _kpi("avg"), ["region"])
    assert result["total_movement"] == pytest.approx(40.0 - 20.0, abs=1e-6)
    assert len(result["dimensions"]) == 1
    # all slices present
    slices = {s["slice"] for s in result["dimensions"][0]["slices"]}
    assert slices == {"A", "B"}


def test_before_after_values_reported():
    result = decompose_contribution(_movement_df(), _kpi(), ["region"])
    assert result["before"]["value"] == pytest.approx(150.0)
    assert result["after"]["value"] == pytest.approx(157.0)
    assert result["before"]["period"].startswith("2024-01-01")
    assert result["after"]["period"].startswith("2024-01-02")


def test_insufficient_periods_raises():
    df = pd.DataFrame({"date": ["2024-01-01"], "region": ["A"], "revenue": [1.0]})
    with pytest.raises(ValueError):
        decompose_contribution(df, {**_kpi(), "trend": None}, ["region"])


def test_trend_used_when_provided():
    # KPI trend supplies before/after even when the frame has extra rows
    df = _movement_df()
    trend = [
        {"period": "2024-01-01", "value": 150.0},
        {"period": "2024-01-02", "value": 157.0},
    ]
    result = decompose_contribution(df, {**_kpi(), "trend": trend}, ["region"])
    assert result["total_movement"] == pytest.approx(7.0, abs=1e-6)
