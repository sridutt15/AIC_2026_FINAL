"""KPI validation tests: 3 periods -> low-data; 20 healthy periods -> valid."""

import pandas as pd

from app.core.kpi_engine.validation import validate_kpi


def _kpi(measure: str = "revenue", aggregation: str = "sum") -> dict:
    return {
        "name": f"{aggregation}({measure})",
        "measure": measure,
        "aggregation": aggregation,
        "slice_columns": [],
        "time_column": "date",
    }


def _df(values: list) -> pd.DataFrame:
    n = len(values)
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "revenue": [float(v) for v in values],
        }
    )


def test_three_periods_flags_low_data():
    result = validate_kpi(_kpi(), _df([10.0, 12.0, 11.0]))
    assert result["status"] == "low-data"
    assert "3" in result["reason"]


def test_twenty_healthy_periods_valid():
    values = [100.0 + i * 5 + (i % 3) for i in range(20)]  # real trend + variance
    result = validate_kpi(_kpi(), _df(values))
    assert result["status"] == "valid"


def test_exactly_eight_periods_valid():
    values = [10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5, 15.0]
    result = validate_kpi(_kpi(), _df(values))
    assert result["status"] == "valid"  # >= 8 periods


def test_seven_periods_low_data():
    values = [10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5]
    result = validate_kpi(_kpi(), _df(values))
    assert result["status"] == "low-data"


def test_all_null_measure_invalid():
    df = _df([10.0, 12.0, 11.0, 13.0, 12.0, 14.0, 13.0, 15.0, 12.0, 11.0])
    df["revenue"] = None
    result = validate_kpi(_kpi(), df)
    assert result["status"] == "invalid"
    assert "null" in result["reason"]


def test_zero_denominator_ratio_invalid():
    # avg/rate aggregation over an all-zero measure -> zero denominator
    values = [0.0] * 10
    result = validate_kpi(_kpi(aggregation="rate"), _df(values))
    assert result["status"] == "invalid"
    assert "denominator" in result["reason"]


def test_missing_measure_column_invalid():
    df = _df([10.0] * 10).rename(columns={"revenue": "other"})
    result = validate_kpi(_kpi(), df)
    assert result["status"] == "invalid"


def test_sliced_kpi_collapses_slices_in_trend():
    # 10 periods x 2 regions; trend must be 10 periods (sum across regions)
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    rows = []
    for d in dates:
        rows.append({"date": d, "region": "north", "revenue": 5.0})
        rows.append({"date": d, "region": "south", "revenue": 7.0})
    df = pd.DataFrame(rows)
    kpi = {**_kpi(), "slice_columns": ["region"]}
    result = validate_kpi(kpi, df)
    assert result["status"] == "valid"
