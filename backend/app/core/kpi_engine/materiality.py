"""KPI materiality scoring: statistical significance x business-impact weight.

Formula (documented, deterministic):

    materiality = statistical_component * business_weight

    statistical_component = |value - baseline| / baseline_std
        where baseline_std is the standard deviation of the KPI's trend over the
        periods preceding the latest one (how many "sigmas" the latest value has
        moved from its baseline). If baseline_std is 0 (constant history), the
        component is 0 unless the value itself moved, in which case it is
        capped at a large constant (10.0) so real movements still rank.

    business_weight = w_stat * z_norm + w_biz * business_impact
        normalized so weights sum to 1 (default: 0.5/0.5 when the contract does
        not set "materiality_weights": {"statistical": s, "business": b}).

        z_norm          = min(statistical_component / 3, 1.0) — saturating z-score
        business_impact = 1.0 if the movement exceeds the contract's
                          materiality_std_devs threshold, else proportional
                          (statistical_component / threshold, clamped to [0, 1]).

The result is in [0, 10]: a KPI moving >= threshold sigmas with full business
impact scores 10.0; tiny movements score near 0. No LLM — pure arithmetic.
"""

import numpy as np

DEFAULT_STAT_WEIGHT = 0.5
DEFAULT_BIZ_WEIGHT = 0.5
DEFAULT_THRESHOLD_STD_DEVS = 1.0
MAX_STAT_COMPONENT = 10.0


def score_materiality(kpi_computation: dict, contract: dict | None = None, driver_type: str | None = None) -> float:
    """Score a KPI computation's materiality. See module docstring for the formula.

    driver_type (Phase 11 feedback loop): when provided, the score is scaled
    by that driver type's persisted feedback multiplier
    (core/feedback/store.py) — repeated "reject" verdicts nudge the weight
    down deterministically; default multiplier is 1.0 (no feedback yet).
    """
    contract = contract or {}
    thresholds = contract.get("thresholds", {})
    weights_cfg = contract.get("materiality_weights", {})

    w_stat = float(weights_cfg.get("statistical", DEFAULT_STAT_WEIGHT))
    w_biz = float(weights_cfg.get("business", DEFAULT_BIZ_WEIGHT))
    total_w = w_stat + w_biz
    if total_w <= 0:  # degenerate config -> equal weights
        w_stat, w_biz, total_w = 0.5, 0.5, 1.0
    w_stat, w_biz = w_stat / total_w, w_biz / total_w

    threshold = float(thresholds.get("materiality_std_devs", DEFAULT_THRESHOLD_STD_DEVS))
    if threshold <= 0:
        threshold = DEFAULT_THRESHOLD_STD_DEVS

    value = kpi_computation.get("value")
    baseline = kpi_computation.get("baseline")
    trend = kpi_computation.get("trend") or []

    if value is None or baseline is None or len(trend) < 2:
        return 0.0

    # Standard deviation of the trend preceding the latest period.
    prior_values = np.array([p["value"] for p in trend[:-1]], dtype=float)
    baseline_std = float(np.std(prior_values, ddof=1)) if len(prior_values) > 1 else 0.0

    delta = abs(float(value) - float(baseline))
    if baseline_std > 0:
        stat_component = delta / baseline_std
    else:
        # Constant history: any real movement is maximally unusual; cap it.
        stat_component = MAX_STAT_COMPONENT if delta > 0 else 0.0

    z_norm = min(stat_component / 3.0, 1.0)
    if stat_component >= threshold:
        business_impact = 1.0
    else:
        business_impact = max(0.0, min(stat_component / threshold, 1.0))

    score = stat_component * (w_stat * z_norm + w_biz * business_impact)
    score = min(score, MAX_STAT_COMPONENT)

    # Phase 11 feedback loop: scale the CAPPED score by the persisted
    # per-driver-type multiplier (1.0 unless analysts rejected this driver
    # type repeatedly). Adjustments only ever lower the score, so the
    # cap still holds; there is no re-cap that would hide the effect.
    if driver_type:
        from app.core.feedback.store import get_driver_multiplier
        score *= get_driver_multiplier(driver_type)

    return float(round(score, 4))
