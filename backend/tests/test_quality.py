"""Data-quality engine tests: exact issue counts on a dirty DataFrame + score ordering."""

import pandas as pd

from app.core.quality.checks import (
    check_duplicates,
    check_invalid_ranges,
    check_missing_values,
    check_outliers,
    check_type_violations,
)
from app.core.quality.report_builder import build_quality_report


def _make_contract(measures: list) -> dict:
    return {"columns_by_role": {"measure": measures}}


def _make_dirty_df() -> pd.DataFrame:
    """8 rows: 2 nulls in one column, 1 exact duplicate row, 1 negative measure value,
    1 extreme statistical outlier."""
    return pd.DataFrame(
        {
            "order_date": [
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
                "2024-01-04",
                "2024-01-05",
                "2024-01-06",
                "2024-01-07",
                "2024-01-08",
            ],
            "region": ["N", "S", "N", "E", None, None, "W", "S"],
            "revenue": [100.0, 150.0, -50.0, 200.0, 175.0, 160.0, 120.0, 10000.0],
        }
    )


def _make_clean_df() -> pd.DataFrame:
    """Same shape, no nulls, no duplicates, no negatives, no outliers."""
    return pd.DataFrame(
        {
            "order_date": [
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
                "2024-01-04",
                "2024-01-05",
                "2024-01-06",
                "2024-01-07",
                "2024-01-08",
            ],
            "region": ["N", "S", "N", "E", "W", "S", "N", "S"],
            "revenue": [100.0, 150.0, 120.0, 200.0, 175.0, 160.0, 120.0, 145.0],
        }
    )


def test_missing_values_exact_count():
    issues = check_missing_values(_make_dirty_df())
    # region has exactly 2 nulls of 8 rows (25% > 5%) -> flagged
    assert len(issues) == 1
    assert issues[0]["column"] == "region"
    assert issues[0]["affected_row_count"] == 2
    # order_date and revenue have 0 nulls -> not flagged
    flagged = {i["column"] for i in issues}
    assert "order_date" not in flagged and "revenue" not in flagged


def test_missing_values_threshold_respected():
    df = pd.DataFrame({"a": [1.0, None, 2.0, 3.0]})  # 25% nulls
    assert len(check_missing_values(df, threshold=0.3)) == 0  # 0.25 <= 0.3
    assert len(check_missing_values(df, threshold=0.2)) == 1  # 0.25 > 0.2


def test_duplicates_exact_count():
    dirty = _make_dirty_df()
    # Row 8 (2024-01-08, S, 10000.0) is NOT a duplicate. Add one exact dup:
    dirty = pd.concat(
        [dirty, pd.DataFrame([dirty.iloc[1]])], ignore_index=True
    )  # 9 rows, 1 dup
    issues = check_duplicates(dirty)
    assert len(issues) == 1
    assert issues[0]["issue_type"] == "duplicate_rows"
    assert issues[0]["affected_row_count"] == 1


def test_invalid_ranges_negative_in_measure():
    issues = check_invalid_ranges(_make_dirty_df(), _make_contract(["revenue"]))
    assert len(issues) == 1
    assert issues[0]["column"] == "revenue"
    assert issues[0]["affected_row_count"] == 1  # exactly one negative (-50.0)


def test_invalid_ranges_allow_negative_overrides():
    contract = _make_contract(["revenue"])
    contract["allow_negative"] = ["revenue"]
    assert check_invalid_ranges(_make_dirty_df(), contract) == []


def test_outliers_exact_count():
    # revenue IQR fences: [-50.0, 10000.0] both fall outside -> exactly 2 outliers.
    # (The negative is also a statistical outlier; that's expected and fine.)
    issues = check_outliers(_make_dirty_df(), _make_contract(["revenue"]))
    flagged = [i for i in issues if i["column"] == "revenue"]
    assert len(flagged) == 1
    assert flagged[0]["affected_row_count"] == 2  # -50.0 and 10000.0
    # The clean frame has no outliers at all
    assert check_outliers(_make_clean_df(), _make_contract(["revenue"])) == []


def test_outliers_skips_small_samples():
    df = pd.DataFrame({"x": [1.0, 2.0, 1e9]})  # 3 values < MIN_OUTLIER_SUPPORT of 8
    assert check_outliers(df) == []


def test_type_violations_detects_string_in_numeric():
    profile = {
        "columns": [
            {"name": "revenue", "dtype": "float64", "detected_role": "numerical"},
        ]
    }
    df = pd.DataFrame({"revenue": ["100.0", "abc", "50.0", None, "20.0"]})
    issues = check_type_violations(df, profile)
    assert len(issues) == 1
    assert issues[0]["column"] == "revenue"
    assert issues[0]["affected_row_count"] == 1  # only "abc" fails coercion


def test_type_violations_none_when_dtype_matches():
    profile = {
        "columns": [
            {"name": "revenue", "dtype": "float64", "detected_role": "numerical"},
        ]
    }
    df = pd.DataFrame({"revenue": [1.0, 2.0, 3.0]})
    assert check_type_violations(df, profile) == []


def test_dirty_scores_lower_than_clean():
    dirty_report = build_quality_report(
        _make_dirty_df(), _make_contract(["revenue"])
    )
    clean_report = build_quality_report(
        _make_clean_df(), _make_contract(["revenue"])
    )
    assert clean_report["score"] == 100.0  # nothing to penalize
    assert dirty_report["score"] < clean_report["score"]
    # Dirty frame must have flagged at least: nulls(1) + negatives(1) + outliers(1)
    assert len(dirty_report["issues"]) >= 3


def test_score_never_below_zero():
    df = pd.DataFrame(
        {
            "a": [None] * 10,
            "b": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "c": [-1.0] * 10,
        }
    )
    contract = _make_contract(["b", "c"])
    report = build_quality_report(df, contract)
    assert 0.0 <= report["score"] <= 100.0


def test_report_deterministic():
    dirty = _make_dirty_df()
    contract = _make_contract(["revenue"])
    assert build_quality_report(dirty, contract) == build_quality_report(dirty, contract)
