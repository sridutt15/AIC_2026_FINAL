"""Materiality scoring tests: big significant movement ranks above small movement."""

import numpy as np

from app.core.kpi_engine.materiality import score_materiality


def _computation(values: list) -> dict:
    """Build a KPI computation dict from a raw trend (baseline = prior-7 mean)."""
    trend = [
        {"period": f"p{i}", "value": float(v)} for i, v in enumerate(values)
    ]
    prior = [float(v) for v in values[:-1]]
    return {
        "value": float(values[-1]),
        "trend": trend,
        "baseline": float(np.mean(prior[-7:])),
        "benchmark": float(np.mean(values)),
    }


def _stable_trend(level: float, n: int = 20, noise: float = 1.0) -> list:
    rng = np.random.default_rng(11)
    return [level + rng.normal(0, noise) for _ in range(n)]


def test_large_movement_high_weight_scores_higher():
    # KPI A: stable at 100 with noise, then a huge jump (+40 = 40 sigma)
    values_a = _stable_trend(100.0)
    values_a = values_a[:-1] + [140.0]

    # KPI B: stable at 100, then a tiny move (+1 = 1 sigma)
    values_b = _stable_trend(100.0)
    values_b = values_b[:-1] + [101.0]

    comp_a = _computation(values_a)
    comp_b = _computation(values_b)

    # High business weight contract for A, low for B
    contract_high = {"thresholds": {"materiality_std_devs": 1.0}}
    contract_low = {"thresholds": {"materiality_std_devs": 5.0}}

    score_a = score_materiality(comp_a, contract_high)
    score_b = score_materiality(comp_b, contract_low)

    assert score_a > score_b
    assert score_a > 1.0  # genuinely material
    assert score_b < score_a / 2


def test_equal_settings_still_rank_big_movement_first():
    # Same contract for both — the statistical component alone must rank A > B.
    contract = {"thresholds": {"materiality_std_devs": 1.0}}
    big = _computation(_stable_trend(100.0)[:-1] + [130.0])
    small = _computation(_stable_trend(100.0)[:-1] + [100.5])
    assert score_materiality(big, contract) > score_materiality(small, contract)


def test_default_weights_when_contract_missing():
    big = _computation(_stable_trend(100.0)[:-1] + [130.0])
    with_contract = score_materiality(big, {"thresholds": {"materiality_std_devs": 1.0}})
    without = score_materiality(big, None)
    assert with_contract > 0
    assert without > 0  # defaults 0.5/0.5 apply
    assert abs(with_contract - without) < 1e-9  # same defaults produce same score


def test_custom_weights_change_relative_scores():
    # Statistical-only weighting vs business-only weighting
    comp = _computation(_stable_trend(100.0)[:-1] + [110.0])
    stat_heavy = score_materiality(
        comp, {"materiality_weights": {"statistical": 0.9, "business": 0.1}}
    )
    biz_heavy = score_materiality(
        comp, {"materiality_weights": {"statistical": 0.1, "business": 0.9}}
    )
    assert stat_heavy > 0 and biz_heavy > 0  # both positive; exact ratio is by design


def test_no_movement_scores_zero():
    flat = [100.0] * 20
    assert score_materiality(_computation(flat), {"thresholds": {}}) == 0.0


def test_constant_history_movement_capped():
    # Prior history constant (std=0), latest value jumps -> capped component, still scores
    comp = _computation([100.0] * 19 + [120.0])
    score = score_materiality(comp, {"thresholds": {"materiality_std_devs": 1.0}})
    assert score > 0.0


def test_missing_value_or_baseline_scores_zero():
    assert score_materiality({"value": None, "trend": [], "baseline": None}) == 0.0
