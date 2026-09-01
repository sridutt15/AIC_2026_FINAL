"""Driver/contribution decomposition: waterfall-style period-over-period movement.

Method (documented, deterministic):

For an ADDITIVE metric (sum), the total movement is
    total_movement = KPI_after - KPI_before.
Each dimension slice s contributes:
    contribution_s = slice_value_after(s) - slice_value_before(s),
and the waterfall identity
    sum_s contribution_s == total_movement
holds EXACTLY (every row belongs to exactly one slice of a given dimension).
The function asserts this reconciliation internally (within a small tolerance
for float error) — a sanity check, not just a test-time assertion.

For a RATIO metric (avg/rate), we use a two-part decomposition per slice:
    contribution_s = volume_effect + mix_effect
      volume_effect_s = (n_after(s) - n_before(s)) * baseline_ratio_s
      mix_effect_s    = (ratio_after(s) - ratio_before(s)) * n_after(s)
Summing over slices approximates the total ratio movement (weighted), so the
output carries both the contributions and a reconciliation residual.
"""

import numpy as np
import pandas as pd

RECONCILIATION_TOLERANCE = 1e-6


def _period_bounds(trend: list) -> tuple:
    """(before_value, after_value, before_period, after_period) from a KPI trend."""
    values = [p["value"] for p in trend if p.get("value") is not None]
    periods = [p["period"] for p in trend if p.get("value") is not None]
    if len(values) < 2:
        return None
    return values[-2], values[-1], periods[-2], periods[-1]


def decompose_contribution(canonical_df: pd.DataFrame, kpi: dict, dimensions: list) -> dict:
    """Decompose a KPI's latest period-over-period movement across dimension slices.

    Args:
        canonical_df: the canonical dataset.
        kpi: KPI definition (measure, aggregation, time_column, trend optional).
        dimensions: dimension columns to decompose across.

    Returns {
        "total_movement": float,
        "before": {period, value}, "after": {period, value},
        "dimensions": [
            {"dimension": str, "slices": [{"slice", "before", "after", "contribution",
                                           "share_pct", "direction"}],
             "reconciliation_residual": float}  # 0.0 for additive metrics
        ]
    }
    """
    time_col = kpi.get("time_column")
    measure = kpi["measure"]
    agg = kpi.get("aggregation", "sum")

    # Trend from the KPI computation if provided; otherwise compute directly.
    trend = kpi.get("trend")
    if trend and len(trend) >= 2:
        before_value, after_value, before_period, after_period = _period_bounds(trend)
    else:
        if time_col is None:
            raise ValueError("KPI has no time column and no trend to decompose.")
        times = pd.to_datetime(canonical_df[time_col], errors="coerce")
        frame = canonical_df.assign(_t=times)
        # Int-backed period keys: same grouping semantics, tiny hash tables
        # (memory-safe on multi-million-row canonical frames). Timestamp.value
        # is always ns regardless of the column's internal resolution.
        frame = frame[frame["_t"].notna()].assign(_p_int=frame["_t"].map(lambda ts: ts.value))
        grouped = frame.groupby("_p_int")[measure]
        series = grouped.mean() if agg in ("avg", "rate") else (
            grouped.count() if agg == "count" else grouped.sum()
        )
        series.index = pd.to_datetime(series.index, unit="ns")
        series = series.sort_index()
        if len(series) < 2:
            raise ValueError("Not enough periods to decompose movement.")
        before_value = float(series.iloc[-2])
        after_value = float(series.iloc[-1])
        before_period = series.index[-2].isoformat()
        after_period = series.index[-1].isoformat()

    times = pd.to_datetime(canonical_df[time_col], errors="coerce")
    frame = canonical_df.assign(_t=times)
    # Day-level matching: canonical CSVs usually store date-only strings, so
    # exact Timestamp equality would silently find zero rows and return empty
    # decompositions. normalize() truncates both sides to midnight.
    before_rows = frame[frame["_t"].dt.normalize() == pd.Timestamp(before_period).normalize()]
    after_rows = frame[frame["_t"].dt.normalize() == pd.Timestamp(after_period).normalize()]

    total_movement = float(after_value) - float(before_value)
    is_additive = agg not in ("avg", "rate")

    result = {
        "total_movement": round(total_movement, 4),
        "before": {"period": before_period, "value": float(before_value)},
        "after": {"period": after_period, "value": float(after_value)},
        "dimensions": [],
    }

    for dim in dimensions:
        if dim not in canonical_df.columns:
            continue
        if is_additive:
            before_sums = before_rows.groupby(dim, dropna=False)[measure].sum()
            after_sums = after_rows.groupby(dim, dropna=False)[measure].sum()
        else:
            before_sums = before_rows.groupby(dim, dropna=False)[measure].mean()
            after_sums = after_rows.groupby(dim, dropna=False)[measure].mean()
            before_counts = before_rows.groupby(dim, dropna=False)[measure].count()
            after_counts = after_rows.groupby(dim, dropna=False)[measure].count()

        all_slices = sorted(
            set(before_sums.index.tolist()) | set(after_sums.index.tolist()),
            key=lambda v: (str(type(v)), str(v)),
        )
        slices = []
        contributions_sum = 0.0
        for s in all_slices:
            b = float(before_sums.get(s, 0.0))
            a = float(after_sums.get(s, 0.0))
            if is_additive:
                contribution = a - b
            else:
                # Volume effect: change in row share times the prior period's global ratio.
                n_b = float(before_counts.get(s, 0.0))
                n_a = float(after_counts.get(s, 0.0))
                baseline_ratio = (
                    float(before_value) if before_value else 0.0
                )
                volume_effect = (n_a - n_b) * baseline_ratio
                mix_effect = (a - b) * n_a
                contribution = volume_effect + mix_effect
            direction = "up" if contribution > 0 else ("down" if contribution < 0 else "flat")
            share = (
                abs(contribution) / abs(total_movement) * 100.0
                if total_movement != 0
                else 0.0
            )
            slices.append(
                {
                    "slice": s if not pd.isna(s) else "(null)",
                    "before": round(b, 4),
                    "after": round(a, 4),
                    "contribution": round(contribution, 4),
                    "share_pct": round(share, 2),
                    "direction": direction,
                }
            )
            contributions_sum += contribution

        residual = contributions_sum - total_movement
        if is_additive:
            # Waterfall identity must hold for additive metrics — assert internally.
            assert abs(residual) <= max(
                RECONCILIATION_TOLERANCE,
                abs(total_movement) * 1e-9,
                1e-6 * max(abs(float(before_value)), abs(float(after_value)), 1.0),
            ), (
                f"Waterfall reconciliation failed for dim '{dim}': "
                f"slices sum {contributions_sum} != total {total_movement}"
            )
        # Rank slices by absolute contribution, descending.
        slices.sort(key=lambda sl: abs(sl["contribution"]), reverse=True)
        result["dimensions"].append(
            {
                "dimension": dim,
                "slices": slices,
                "reconciliation_residual": round(float(residual), 6),
            }
        )

    return result
