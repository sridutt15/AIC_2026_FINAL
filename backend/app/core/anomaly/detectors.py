"""Anomaly / change-point detectors. All deterministic — fixed seeds and parameters.

Methods:
    - change points:  ruptures PELT (model="rbf", penalty scaled to series length).
                      Returns the indices where the series' distribution shifts.
    - control limits:  points beyond ±3 standard deviations of a rolling 7-point
                      mean (classic SPC-style breach detection).
    - outliers:        robust MAD-based outliers (median absolute deviation,
                      modified z-score > 3.5 — the standard robust cutoff).
"""

import numpy as np
import pandas as pd
import ruptures as rpt

# --- Tunables (documented constants, deterministic behavior) ---
PELT_PENALTY_BASE = 3.0        # PELT penalty multiplier (log(n)-scaled below)
CONTROL_LIMIT_SIGMAS = 3.0     # ±3 sigma beyond rolling mean
CONTROL_WINDOW = 7             # rolling window for the control mean
MAD_CUTOFF = 3.5               # modified z-score cutoff for robust outliers
MAD_SCALE = 0.6745             # 0.75th quantile of the standard normal
MIN_SERIES_LEN = 8             # below this, detectors return empty results


def _clean(series) -> np.ndarray:
    """Extract a float array from a list/dict-trend/Series, dropping nulls' indices."""
    if isinstance(series, pd.Series):
        return series.dropna().to_numpy(dtype=float)
    if isinstance(series, list) and series and isinstance(series[0], dict):
        values = [p["value"] for p in series if p.get("value") is not None]
        return np.array(values, dtype=float)
    arr = np.asarray([v for v in series if v is not None and not pd.isna(v)], dtype=float)
    return arr


def detect_change_points(series) -> list:
    """Indices where the series' level shifts, via ruptures PELT (rbf kernel).

    The penalty grows with log(n) so longer series don't fragment; indices are
    the last points of each detected segment boundary. Returns [] for short series.
    """
    values = _clean(series)
    n = len(values)
    if n < MIN_SERIES_LEN:
        return []
    penalty = PELT_PENALTY_BASE * np.log(n)
    algo = rpt.Pelt(model="rbf").fit(values.reshape(-1, 1))
    breakpoints = algo.predict(pen=penalty)
    # ruptures returns segment END indices (including n); keep interior ones only.
    return [int(b) for b in breakpoints if 0 < b < n]


def detect_control_limit_breaches(series) -> list:
    """Indices beyond ±3 std dev of a TRAILING rolling window (excluding current point).

    SPC-style: the control mean/std at index i are computed over the 7 points
    BEFORE i (window shifted by one), so a spike can't inflate its own limits
    and mask itself. min_periods=3 for the series head.
    """
    values = _clean(series)
    n = len(values)
    if n < MIN_SERIES_LEN:
        return []
    s = pd.Series(values)
    window = min(CONTROL_WINDOW, max(n - 1, 1))
    trailing_mean = s.shift(1).rolling(window=window, min_periods=window).mean()
    trailing_std = s.shift(1).rolling(window=window, min_periods=window).std()
    breach = (s - trailing_mean).abs() > CONTROL_LIMIT_SIGMAS * trailing_std
    return [int(i) for i in np.where(breach.fillna(False).to_numpy())[0]]


def detect_outliers(series) -> list:
    """Robust MAD outliers: modified z-score |0.6745*(x - median)/MAD| > 3.5."""
    values = _clean(series)
    n = len(values)
    if n < MIN_SERIES_LEN:
        return []
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad == 0:
        return []  # constant or constant-except-noise series: no robust outliers
    modified_z = np.abs(MAD_SCALE * (values - median) / mad)
    return [int(i) for i in np.where(modified_z > MAD_CUTOFF)[0]]


def run_all_detectors(series) -> dict:
    """Run all three detectors; map method -> sorted unique flag indices."""
    return {
        "change_points": sorted(detect_change_points(series)),
        "control_limit_breaches": sorted(detect_control_limit_breaches(series)),
        "outliers": sorted(detect_outliers(series)),
    }
