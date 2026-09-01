"""Canonical reconciliation tests: align_grain + reconcile against hand-computed values."""

import pandas as pd
import pytest

from app.core.canonical.reconciler import align_grain, reconcile


def _daily_df() -> pd.DataFrame:
    """14 days x 2 regions, daily revenue (additive) and a [0,1] ratio column."""
    dates = pd.date_range("2024-01-01", periods=14, freq="D")
    regions = ["north", "south"]
    rows = []
    for region in regions:
        for i, d in enumerate(dates):
            rows.append(
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "region": region,
                    "revenue": 10.0 + i,  # north & south identical values for hand-math
                    "conversion_pct": 0.5,  # ratio-like: avg, not sum
                }
            )
    return pd.DataFrame(rows)


def _weekly_df() -> pd.DataFrame:
    """2 ISO weeks x 2 regions, weekly budget."""
    rows = []
    for region in ["north", "south"]:
        for week_start in ["2024-01-01", "2024-01-08"]:
            rows.append(
                {
                    "week_starting": week_start,
                    "region_code": region,
                    "budget": 700.0,
                }
            )
    return pd.DataFrame(rows)


# --- align_grain: daily -> weekly (downsample) -------------------------------


def test_downsample_daily_to_weekly_sums_additive():
    aligned = align_grain(_daily_df(), "Daily", "Weekly")
    # 14 days -> 2 ISO weeks (2024-01-01 is Monday; weeks Jan 1-7, Jan 8-14)
    assert len(aligned) == 4  # 2 weeks x 2 regions
    north = aligned[aligned["region"] == "north"].sort_values("date")
    # Week 1 revenue: sum(10..16) = 91; Week 2: sum(17..23) = 140
    assert north["revenue"].tolist() == [91.0, 140.0]


def test_downsample_averages_ratio_columns():
    aligned = align_grain(_daily_df(), "Daily", "Weekly")
    north = aligned[aligned["region"] == "north"].sort_values("date")
    # conversion_pct is ratio-like -> mean of 0.5s stays 0.5 (not 3.5)
    assert north["conversion_pct"].tolist() == [0.5, 0.5]


def test_upsample_weekly_to_daily_forward_fill():
    aligned = align_grain(_weekly_df(), "Weekly", "Daily")
    # 2 weekly rows per region -> 14 daily rows per region (LOCF)
    assert len(aligned) == 28
    north = aligned[aligned["region_code"] == "north"].sort_values("week_starting")
    assert north["budget"].nunique() == 1  # every carried value is 700.0
    assert north["budget"].iloc[0] == 700.0
    # 14 daily dates per region
    assert north["week_starting"].nunique() == 14


def test_align_grain_same_cadence_noop():
    df = _daily_df()
    aligned = align_grain(df, "Daily", "Daily")
    assert len(aligned) == len(df)
    assert aligned["revenue"].tolist() == df["revenue"].tolist()


# --- reconcile: daily + weekly -> daily canonical ------------------------------


def test_reconcile_daily_and_weekly_on_date_region():
    daily = _daily_df()  # 28 rows, daily
    weekly = _weekly_df()  # 4 rows, weekly
    sources = [
        {"df": daily, "cadence": "Daily"},
        {"df": weekly, "cadence": "Weekly"},
    ]
    join_keys = {
        "date": {0: "date", 1: "week_starting"},
        "region": {0: "region", 1: "region_code"},
    }
    canonical = reconcile(sources, join_keys)  # finest cadence = Daily

    # 28 rows (daily grain preserved), budget forward-filled onto every day
    assert len(canonical) == 28
    assert set(canonical.columns) >= {"date", "region", "revenue", "budget"}

    north_jan1 = canonical[(canonical["region"] == "north") & (canonical["date"] == "2024-01-01")]
    assert len(north_jan1) == 1
    # Hand-computed: revenue on Jan 1 = 10.0, budget (week of Jan 1) = 700.0
    assert float(north_jan1["revenue"].iloc[0]) == 10.0
    assert float(north_jan1["budget"].iloc[0]) == 700.0

    north_jan10 = canonical[(canonical["region"] == "north") & (canonical["date"] == "2024-01-10")]
    assert float(north_jan10["revenue"].iloc[0]) == 19.0  # 10 + 9 days
    assert float(north_jan10["budget"].iloc[0]) == 700.0  # week 2, still 700


def test_reconcile_left_join_missing_budget_stays_null():
    daily = _daily_df()
    # Keep only week 2 rows (dates >= 2024-01-08) for both regions.
    weekly = _weekly_df()
    weekly = weekly[weekly["week_starting"] >= "2024-01-08"].reset_index(drop=True)
    assert len(weekly) == 2  # one week-2 row per region
    sources = [
        {"df": daily, "cadence": "Daily"},
        {"df": weekly, "cadence": "Weekly"},
    ]
    join_keys = {
        "date": {0: "date", 1: "week_starting"},
        "region": {0: "region", 1: "region_code"},
    }
    canonical = reconcile(sources, join_keys)
    north = canonical[canonical["region"] == "north"].sort_values("date").reset_index(drop=True)
    # Week 1 (Jan 1-7): no budget row in source 1 -> null after left join
    assert north["budget"].iloc[:7].isna().all()
    # Week 2 (Jan 8-14): budget present on every day (forward-filled 700)
    assert north["budget"].iloc[7:].notna().all()
    assert float(north["budget"].iloc[7]) == 700.0


def test_reconcile_requires_two_sources():
    with pytest.raises(ValueError):
        reconcile([{"df": _daily_df(), "cadence": "Daily"}], {"date": {0: "date", 1: "date"}})


def test_reconcile_overlapping_nonkey_columns_dropped_from_secondary():
    daily = _daily_df()
    weekly = _weekly_df()
    weekly = weekly.rename(columns={"budget": "revenue"})  # now overlaps with daily
    sources = [
        {"df": daily, "cadence": "Daily"},
        {"df": weekly, "cadence": "Weekly"},
    ]
    join_keys = {
        "date": {0: "date", 1: "week_starting"},
        "region": {0: "region", 1: "region_code"},
    }
    canonical = reconcile(sources, join_keys)
    # The daily source's revenue wins; the weekly 'revenue' is dropped, not merged
    north_jan1 = canonical[(canonical["region"] == "north") & (canonical["date"] == "2024-01-01")]
    assert float(north_jan1["revenue"].iloc[0]) == 10.0


def test_reconcile_deterministic():
    sources = [
        {"df": _daily_df(), "cadence": "Daily"},
        {"df": _weekly_df(), "cadence": "Weekly"},
    ]
    join_keys = {
        "date": {0: "date", 1: "week_starting"},
        "region": {0: "region", 1: "region_code"},
    }
    first = reconcile(sources, join_keys)
    second = reconcile(
        [
            {"df": _daily_df(), "cadence": "Daily"},
            {"df": _weekly_df(), "cadence": "Weekly"},
        ],
        join_keys,
    )
    pd.testing.assert_frame_equal(first, second)


def test_reconcile_renames_source0_keys_too():
    """Regression: the common key name differing from source 0's column
    name must still work — source 0's key columns are renamed to the common
    key like every other source (previously only sources 1..n were renamed,
    so any custom common-key name failed with 'No common join keys')."""
    sources = [
        {"df": _daily_df(), "cadence": "Daily"},
        {"df": _weekly_df(), "cadence": "Weekly"},
    ]
    # Common key names deliberately differ from BOTH sources' column names.
    join_keys = {
        "day": {0: "date", 1: "week_starting"},
        "geo": {0: "region", 1: "region_code"},
    }
    canonical = reconcile(sources, join_keys)
    assert {"day", "geo", "revenue", "budget"} <= set(canonical.columns)
    assert len(canonical) == 28
    north_jan1 = canonical[(canonical["geo"] == "north") & (canonical["day"] == "2024-01-01")]
    assert float(north_jan1["revenue"].iloc[0]) == 10.0
    assert float(north_jan1["budget"].iloc[0]) == 700.0
