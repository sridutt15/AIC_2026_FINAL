"""Optional causal path: difference-in-differences estimator.

Used only when a user explicitly flags a driver as "suspected confounded".
Basic 2x2 DiD: outcome movement in the treatment group minus the same movement
in the control group, attributing the difference to the treatment (dimension).

    DiD = (Y_treat_after - Y_treat_before) - (Y_ctrl_after - Y_ctrl_before)

A t-test on the per-row outcomes provides a p-value; small samples fall back
to reporting the effect size only. Deterministic (scipy, no randomness).
"""

import numpy as np
import pandas as pd
from scipy import stats


def diff_in_diff(
    canonical_df: pd.DataFrame,
    treatment_dim: str,
    outcome: str,
    before_period: str,
    after_period: str,
    treatment_value: str = None,
) -> dict:
    """Estimate the causal effect of being in the `treatment_value` slice of a dimension.

    Args:
        canonical_df: canonical dataset (time column auto-detected).
        treatment_dim: dimension defining treatment/control groups.
        outcome: numeric outcome column.
        before_period / after_period: ISO dates (matched exactly).
        treatment_value: the slice treated as the treatment group; defaults to the
            first (sorted) slice, control = the rest.

    Returns {treat_before, treat_after, ctrl_before, ctrl_after, did_estimate,
             p_value, effect_size, n_treat, n_ctrl}.
    """
    from app.core.canonical.reconciler import _find_time_column

    time_col = _find_time_column(canonical_df)
    if time_col is None or treatment_dim not in canonical_df.columns:
        raise ValueError("Dataset lacks a time column or the treatment dimension.")

    times = pd.to_datetime(canonical_df[time_col], errors="coerce")
    frame = canonical_df.assign(_t=times)
    # Match the period on its calendar DAY (canonical CSVs often carry
    # date-only strings; exact Timestamp equality would silently miss rows).
    before = frame[frame["_t"].dt.normalize() == pd.Timestamp(before_period).normalize()]
    after = frame[frame["_t"].dt.normalize() == pd.Timestamp(after_period).normalize()]

    values = sorted(frame[treatment_dim].dropna().astype(str).unique())
    if not values:
        raise ValueError("Treatment dimension has no values.")
    treat_value = treatment_value if treatment_value is not None else values[0]

    def _mean(rows: pd.DataFrame, is_treat: bool) -> tuple:
        mask = rows[treatment_dim].astype(str) == treat_value if is_treat else (
            rows[treatment_dim].astype(str) != treat_value
        )
        group = rows[mask][outcome].dropna()
        return (float(group.mean()) if len(group) else 0.0), len(group)

    treat_before, n_tb = _mean(before, True)
    treat_after, n_ta = _mean(after, True)
    ctrl_before, n_cb = _mean(before, False)
    ctrl_after, n_ca = _mean(after, False)

    did = (treat_after - treat_before) - (ctrl_after - ctrl_before)

    # Two-sample t-test on the after-period outcome between groups (if enough data).
    after_treat = after[after[treatment_dim].astype(str) == treat_value][outcome].dropna()
    after_ctrl = after[after[treatment_dim].astype(str) != treat_value][outcome].dropna()
    p_value = None
    effect_size = None
    if len(after_treat) >= 2 and len(after_ctrl) >= 2:
        t_stat, p_value = stats.ttest_ind(after_treat, after_ctrl, equal_var=False)
        pooled_sd = np.sqrt(
            (after_treat.var(ddof=1) + after_ctrl.var(ddof=1)) / 2.0
        )
        if pooled_sd > 0:
            effect_size = float((after_treat.mean() - after_ctrl.mean()) / pooled_sd)

    return {
        "method": "difference-in-differences",
        "treatment_dim": treatment_dim,
        "treatment_value": treat_value,
        "before_period": before_period,
        "after_period": after_period,
        "treat_before": round(treat_before, 4),
        "treat_after": round(treat_after, 4),
        "ctrl_before": round(ctrl_before, 4),
        "ctrl_after": round(ctrl_after, 4),
        "did_estimate": round(did, 4),
        "p_value": float(p_value) if p_value is not None else None,
        "effect_size": effect_size,
        "n_treat": int(n_ta),
        "n_ctrl": int(n_ca),
    }
