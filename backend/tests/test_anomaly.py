"""Anomaly detector tests: injected level shift detected at the right index; no false positives."""

import numpy as np

from app.core.anomaly.detectors import (
    detect_change_points,
    detect_control_limit_breaches,
    detect_outliers,
    run_all_detectors,
)


def _stable(n: int, level: float, seed: int = 3, noise: float = 1.0):
    rng = np.random.default_rng(seed)
    return list(level + rng.normal(0, noise, size=n))


def test_change_point_detects_level_shift():
    # 50 points at 100, then 50 points at 130 — shift at index 50.
    series = _stable(50, 100.0, noise=2.0) + _stable(50, 130.0, noise=2.0)
    cps = detect_change_points(series)
    assert len(cps) >= 1
    # Some detected index within [45, 55] of the true shift
    assert any(abs(cp - 50) <= 5 for cp in cps), f"change points: {cps}"


def test_no_change_point_on_flat_series():
    series = _stable(100, 100.0, noise=1.5)
    cps = detect_change_points(series)
    assert cps == [], f"false positives: {cps}"


def test_control_limit_breaches_catch_spike():
    series = _stable(30, 100.0, noise=1.0, seed=5)
    series[25] = 160.0  # 60 above the ~100 level, far beyond 3 rolling sigmas
    breaches = detect_control_limit_breaches(series)
    assert 25 in breaches


def test_control_limit_no_breach_on_stable():
    # 60 quiet points (noise 0.3): no point strays 3 trailing-sigmas from its window
    series = _stable(60, 100.0, noise=0.3, seed=0)
    assert detect_control_limit_breaches(series) == []


def test_mad_outliers_catch_extreme_value():
    series = _stable(50, 100.0, noise=2.0)
    series[10] = 180.0  # extreme vs median
    outliers = detect_outliers(series)
    assert 10 in outliers


def test_mad_outliers_stable_series_clean():
    # noise 0.5 -> max modified z stays well under the 3.5 cutoff
    series = _stable(60, 100.0, noise=0.5, seed=9)
    assert detect_outliers(series) == []


def test_run_all_combines_methods():
    series = _stable(50, 100.0, noise=2.0) + _stable(50, 130.0, noise=2.0)
    series[70] = 250.0  # extreme spike inside the second regime
    result = run_all_detectors(series)
    assert set(result.keys()) == {
        "change_points",
        "control_limit_breaches",
        "outliers",
    }
    assert any(abs(cp - 50) <= 5 for cp in result["change_points"])
    assert 70 in result["outliers"]


def test_short_series_returns_empty():
    short = [1.0, 2.0, 3.0]
    assert detect_change_points(short) == []
    assert detect_control_limit_breaches(short) == []
    assert detect_outliers(short) == []


def test_trend_dict_input_supported():
    trend = [{"period": f"p{i}", "value": float(v)} for i, v in enumerate(
        _stable(50, 100.0, noise=2.0) + _stable(50, 130.0, noise=2.0)
    )]
    cps = detect_change_points(trend)
    assert any(abs(cp - 50) <= 5 for cp in cps)
