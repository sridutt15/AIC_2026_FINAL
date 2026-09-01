"""KPI computation: value, trend, baseline, benchmark, bootstrap confidence interval.

All deterministic: the bootstrap uses a FIXED seed (42) so the same KPI + data
always yields the same CI. No LLM.
"""

import numpy as np
import pandas as pd

from app.core.kpi_engine.validation import _series_for

BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95

# Baseline window: rolling mean of the prior N periods (prior-period average).
BASELINE_WINDOW = 7


def compute_kpi(kpi: dict, canonical_df: pd.DataFrame) -> dict:
    """Compute a KPI's full statistical picture from the canonical dataframe.

    Returns:
        value:               latest period's KPI value
        trend:               [{period, value}] sorted by period
        baseline:            mean of the prior BASELINE_WINDOW periods before the
                             latest one (falls back to full-history mean when short)
        benchmark:           mean across all history
        confidence_interval: {lower, upper} — 95% bootstrap CI of the period-mean,
                             1000 resamples, fixed seed (deterministic)
        period_count:        number of periods in the trend
    """
    series = _series_for(kpi, canonical_df)
    series = pd.Series(series).dropna().sort_index()

    if series.empty:
        return {
            "value": None,
            "trend": [],
            "baseline": None,
            "benchmark": None,
            "confidence_interval": None,
            "period_count": 0,
        }

    values = series.to_numpy(dtype=float)
    periods = [
        p.isoformat() if hasattr(p, "isoformat") else str(p) for p in series.index
    ]
    trend = [{"period": p, "value": float(v)} for p, v in zip(periods, values)]

    value = float(values[-1])
    benchmark = float(np.mean(values))

    # Baseline: mean of the prior BASELINE_WINDOW periods (excluding the latest);
    # when history is shorter, use the full history excluding the latest period.
    prior = values[:-1]
    if len(prior) == 0:
        baseline = None
    else:
        window = prior[-BASELINE_WINDOW:]
        baseline = float(np.mean(window))

    # Bootstrap CI of the mean (fixed seed -> deterministic).
    ci_lower, ci_upper = _bootstrap_ci(values)
    ci = (
        {"lower": float(ci_lower), "upper": float(ci_upper)}
        if ci_lower is not None
        else None
    )

    return {
        "value": value,
        "trend": trend,
        "baseline": baseline,
        "benchmark": benchmark,
        "confidence_interval": ci,
        "period_count": len(values),
    }


def _bootstrap_ci(values: np.ndarray):
    """95% percentile bootstrap CI of the mean with a fixed RNG. None if too small."""
    if len(values) < 3:
        return None, None
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    resamples = rng.choice(values, size=(BOOTSTRAP_RESAMPLES, len(values)), replace=True)
    means = resamples.mean(axis=1)
    alpha = (1.0 - CI_LEVEL) / 2.0
    return float(np.quantile(means, alpha)), float(np.quantile(means, 1.0 - alpha))
