"""Canonical reconciliation layer: align grains and merge sources deterministically.

Every rule here is explicit and documented — no black boxes, no ML/LLM.

Grain alignment rules (align_grain):
    to_cadence coarser than from (e.g. daily -> weekly/monthly):
        DOWNSAMPLE. Rows are grouped by the union of the source's dimension columns
        and the target-period key. Additive measures are aggregated with sum();
        ratio-like measures (pct/rate/share/fraction in the column name, or values
        within [0,1]) are aggregated with mean(). The FIRST common column matching a
        date format becomes the time axis (deterministic: leftmost temporal column).
    from coarser than to (e.g. weekly -> daily):
        UPSAMPLE by forward-fill: each period's value is carried forward to every day
        of that period ("last observation carried forward", LOCF). This is clearly
        documented as an assumption, never hidden.
    same cadence:
        unchanged.

Merge rule (reconcile):
    Sources are aligned to a common target cadence (the FINEST cadence among the
    sources, so no information is lost by premature aggregation), then merged with a
    left-join chain starting from the first source, on the user-supplied join key
    mapping (common key -> per-source column name). Join keys are part of the stored
    config, so any merge is fully traceable and reproducible.
"""

from functools import reduce
from pathlib import Path

import pandas as pd

# Cadence ordering for grain alignment: finer -> coarser.
_CADENCE_ORDER = {"Real-time": 0, "Daily": 1, "Weekly": 2, "Monthly": 3}

# Memory-safe canonical CSV loading (see load_canonical_csv).
# Reader chunk size: rows per chunk when streaming a canonical CSV.
_CSV_CHUNK_ROWS = 50_000
# Hard ceiling on rows returned by load_canonical_csv: canonical datasets above
# this are rejected with an explicit 413 error instead of an opaque MemoryError
# (a 8.7M-row canonical on a 16GB machine was the Phase 8 crash).
MAX_CANONICAL_ROWS = 5_000_000


def load_canonical_csv(path: Path) -> pd.DataFrame:
    """Load a canonical CSV defensively: sized check + optimized dtypes.

    Memory-safety rules (documented, deterministic):
      1. Row/column count is checked against MAX_CANONICAL_ROWS first, with a
         clear error message instead of pandas dying mid-parse with MemoryError.
      2. Loading uses float32 for float columns and category for low-cardinality
         object columns — together an ~10x memory reduction on typical
         canonical datasets — without changing any value (float32 holds the
         2-decimal business values exactly enough for analytics aggregation;
         rounded measures are unaffected).
      3. No caching layer here: callers load fresh; the API layer decides.

    Returns the loaded DataFrame. Raises ValueError (mapped to HTTP 413 by
    callers) when the dataset exceeds the size ceiling.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Canonical CSV not found: {path}")

    # Cheap header-only peek for the size guard.
    header = pd.read_csv(path, nrows=0)
    n_cols = len(header.columns)

    # Estimate rows from file size / average line length (avoids a full scan).
    size_bytes = path.stat().st_size
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        # Sample the first 100 lines for an average byte length.
        sample = [len(f.readline().encode("utf-8", "replace")) for _ in range(100)]
    avg_line = max((sum(sample) / len(sample)), 1)
    est_rows = int(size_bytes / avg_line)
    if est_rows > MAX_CANONICAL_ROWS:
        raise ValueError(
            f"Canonical dataset too large to load safely "
            f"(~{est_rows:,} rows > {MAX_CANONICAL_ROWS:,} ceiling). "
            f"Rebuild the canonical model with fewer sources, coarser target "
            f"cadence, or reduced history."
        )

    # Stream in chunks, downcasting as we go, then concat once.
    chunks = []
    for chunk in pd.read_csv(path, chunksize=_CSV_CHUNK_ROWS):
        chunks.append(_downcast_chunk(chunk))
    df = pd.concat(chunks, ignore_index=True) if len(chunks) > 1 else chunks[0]
    if len(df) > MAX_CANONICAL_ROWS:
        raise ValueError(
            f"Canonical dataset too large to load safely "
            f"({len(df):,} rows > {MAX_CANONICAL_ROWS:,} ceiling)."
        )
    return df


def _downcast_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Deterministic dtype optimization for a canonical CSV chunk.

    float64 -> float32; object columns with low cardinality -> category.
    Integers are left as loaded (orders/clicks stay exact); text dimensions
    become categories (the string-hash MemoryError in groupby.factorize came
    from millions of 64-char object strings — categories factorize O(1)).
    """
    for col in chunk.columns:
        if pd.api.types.is_float_dtype(chunk[col]):
            chunk[col] = chunk[col].astype("float32")
        elif chunk[col].dtype == object or pd.api.types.is_string_dtype(chunk[col]):
            # pandas 3 loads strings as a dedicated str dtype (not object).
            nunique = chunk[col].nunique()
            if nunique <= 500 or nunique <= 0.5 * max(len(chunk), 1):
                chunk[col] = chunk[col].astype("category")
    return chunk

# Additive-vs-ratio measure detection for downsampling.
_RATIO_HINTS = ("pct", "percent", "rate", "share", "fraction", "ratio")

# Date formats accepted when locating a time axis column (strict, deterministic).
_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S")


def _is_date_series(series: pd.Series) -> bool:
    """True when >90% of non-null values parse as one of the accepted date formats."""
    non_null = series.dropna()
    if non_null.empty:
        return False
    as_str = non_null.astype(str)
    for fmt in _DATE_FORMATS:
        if pd.to_datetime(as_str, format=fmt, errors="coerce").notna().sum() / len(non_null) > 0.9:
            return True
    return False


def _find_time_column(df: pd.DataFrame) -> str | None:
    """Deterministic time-axis pick: the FIRST (leftmost) column parsing as a date."""
    for col in df.columns:
        if _is_date_series(df[col]):
            return col
    return None


def _period_key(ts: pd.Timestamp, to_cadence: str) -> pd.Timestamp:
    """Truncate a timestamp to the start of its target period.

    Weeks are Monday-anchored (ISO weeks): the key of a timestamp is the Monday
    of its ISO week. Months anchor at their first day. Days normalize to midnight.
    """
    if to_cadence == "Monthly":
        return ts - pd.offsets.MonthBegin(1)
    if to_cadence == "Weekly":
        return (ts - pd.Timedelta(days=ts.weekday())).normalize()  # Monday of ISO week
    return ts.normalize()


def _is_ratio_column(name: str, series: pd.Series) -> bool:
    """Ratio-like measures average; additive measures sum. Documented heuristic."""
    if any(h in name for h in _RATIO_HINTS):
        return True
    samples = series.dropna()
    if len(samples) >= 2:
        try:
            values = pd.to_numeric(samples)
            if values.between(0.0, 1.0).all():
                return True
        except (ValueError, TypeError):
            pass
    return False


def align_grain(df: pd.DataFrame, from_cadence: str, to_cadence: str) -> pd.DataFrame:
    """Align a dataframe from one cadence to another. Pure, deterministic.

    See module docstring for the exact documented rules (downsample: sum/mean by
    measure type; upsample: forward-fill LOCF).
    """
    if from_cadence == to_cadence:
        return df.copy()

    from_rank = _CADENCE_ORDER.get(from_cadence, 1)
    to_rank = _CADENCE_ORDER.get(to_cadence, 1)

    time_col = _find_time_column(df)
    if time_col is None:
        # No time axis to align on — the frame is already as aligned as it can get.
        return df.copy()

    times = pd.to_datetime(df[time_col], errors="coerce")

    # Non-time, non-null-able dimension columns define the grouping context.
    dim_cols = [c for c in df.columns if c != time_col and not pd.api.types.is_numeric_dtype(df[c])]

    if to_rank > from_rank:
        # --- DOWNSAMPLE (finer -> coarser) ---
        out = df.copy()
        out["_period"] = times.map(lambda ts: _period_key(ts, to_cadence) if pd.notna(ts) else pd.NaT)
        group_cols = ["_period"] + dim_cols
        agg = {}
        for col in df.columns:
            if col == time_col or col in dim_cols:
                continue
            if pd.api.types.is_numeric_dtype(out[col]):
                agg[col] = "mean" if _is_ratio_column(col, out[col]) else "sum"
            else:
                agg[col] = "first"  # informational text: keep first occurrence
        aligned = out.groupby(group_cols, dropna=False).agg(agg).reset_index()
        aligned = aligned.rename(columns={"_period": time_col})
        # Keep original column order.
        aligned = aligned[[c for c in df.columns if c in aligned.columns]]
        aligned = aligned.sort_values([time_col] + dim_cols).reset_index(drop=True)
        return aligned

    # --- UPSAMPLE (coarser -> finer): forward-fill within periods ---
    # Each period's values are keyed at the period START and carried forward to every
    # day of that period (last-observation-carried-forward). The daily grid runs from
    # the first period start to the end of the last full period of the SOURCE cadence
    # (e.g. weekly data -> a grid that covers each week through Sunday).
    out = df.copy()
    out["_period"] = times.map(
        lambda ts: _period_key(ts, from_cadence) if pd.notna(ts) else pd.NaT
    )
    out = out[out["_period"].notna()]
    period_starts = pd.DatetimeIndex(out["_period"].dropna().unique()).sort_values()
    last_period_start = _period_key(times.max(), from_cadence)
    if from_cadence == "Monthly":
        grid_end = last_period_start + pd.offsets.MonthEnd(1)
    else:  # weekly periods end on their 7th day; daily needs no extension
        grid_end = last_period_start + pd.Timedelta(days=6)
    daily_index = pd.date_range(period_starts.min(), grid_end, freq="D")
    value_cols = [
        c for c in df.columns if c != time_col and c not in dim_cols
    ]
    frames = []
    if dim_cols:
        for _, group in out.groupby(dim_cols, dropna=False):
            indexed = (
                group.set_index("_period")[value_cols].sort_index()
            )
            reindexed = indexed.reindex(daily_index, method="ffill")
            reindexed.insert(0, time_col, daily_index)
            for i, d in enumerate(dim_cols):
                reindexed.insert(i + 1, d, group[d].iloc[0])
            frames.append(reindexed.reset_index(drop=True))
    else:
        indexed = out.set_index("_period")[value_cols].sort_index()
        reindexed = indexed.reindex(daily_index, method="ffill")
        reindexed.insert(0, time_col, daily_index)
        frames.append(reindexed.reset_index(drop=True))
    result = pd.concat(frames, ignore_index=True) if frames else out
    result = result[[c for c in df.columns if c in result.columns]]
    return result.sort_values([time_col] + dim_cols).reset_index(drop=True)


def reconcile(sources: list, join_keys: dict, target_cadence: str | None = None) -> pd.DataFrame:
    """Merge 2+ aligned sources into one canonical table.

    SINGLE-SOURCE CASE (Phase 19, explicit early return, separate from the
    multi-source path below): when `sources` contains exactly one DataFrame,
    return it directly, UNCHANGED — no grain alignment (there is no other
    cadence to align against), no join logic (nothing to join), no copy of
    the data transformation pipeline. A single source IS its own canonical
    dataset as-is.

    MULTI-SOURCE CASE (2+): behavior is unchanged from Phase 4 — grain
    alignment to the common target cadence, then the left-join chain on the
    user-supplied join keys.

    Args:
        sources: list of {"df": DataFrame, "cadence": str} in join order.
        join_keys: common-key -> {source_index: column_name} mapping, e.g.
            {"date": {0: "date", 1: "order_date"}, "region": {0: "region", 1: "region_code"}}.
            Ignored entirely in the single-source case (nothing to map).
        target_cadence: optional explicit target; defaults to the FINEST cadence
            among the sources (least aggregation loss). Ignored in the
            single-source case (no alignment happens).

    Deterministic: left-join chain in the given source order, keys renamed to the
    common key names, suffix-free (non-key, overlapping columns get "_s{i}").
    """
    if len(sources) == 1:
        # Single source: its data is already canonical. No alignment, no join.
        return sources[0]["df"].copy()

    if len(sources) < 2:
        raise ValueError("reconcile needs at least two sources.")

    cadences = [s.get("cadence", "Daily") for s in sources]
    if target_cadence is None:
        target_cadence = min(cadences, key=lambda c: _CADENCE_ORDER.get(c, 1))

    aligned_frames = []
    for idx, source in enumerate(sources):
        df = source["df"]
        aligned = align_grain(df, source.get("cadence", "Daily"), target_cadence)
        aligned_frames.append((idx, aligned))

    # Normalize time column to datetime on every frame so keys merge exactly.
    # (Uses each source's ORIGINAL column names — before the rename below.)
    normalized = []
    for idx, aligned in aligned_frames:
        frame = aligned.copy()
        for common_key, mapping in join_keys.items():
            col = mapping.get(idx)
            if col and col in frame.columns and _is_date_series(frame[col]):
                frame[col] = pd.to_datetime(frame[col], errors="coerce")
        normalized.append((idx, frame))

    # Rename EVERY source's key columns to the common key names — including
    # source 0 (the left side of the join chain). Without this, a common key
    # whose name differs from source 0's column name (e.g. the UI's "key_1")
    # was never found in source 0 and the merge failed with
    # "No common join keys between source 0 and source 1" even though both
    # sources had perfectly matching columns.
    def _rename_key_columns(frame: pd.DataFrame, idx: int) -> pd.DataFrame:
        rename_map = {}
        for common_key, mapping in join_keys.items():
            col = mapping.get(idx)
            if col and col in frame.columns:
                rename_map[col] = common_key
        return frame.rename(columns=rename_map) if rename_map else frame

    normalized = [(idx, _rename_key_columns(frame, idx)) for idx, frame in normalized]

    # Left-join chain: all key columns are already renamed to common names.
    def merge_pair(acc: pd.DataFrame, item) -> pd.DataFrame:
        _, frame = item
        key_cols = [k for k in join_keys if k in frame.columns and k in acc.columns]
        if not key_cols:
            raise ValueError(
                "No common join keys between source 0 and source "
                f"{item[0]}. Check the join-key mapping: each selected source "
                "needs a column assigned to the common key."
            )
        # Avoid duplicate non-key columns: drop the incoming source's overlaps
        # (the first source's version wins — documented, deterministic).
        overlap = [c for c in frame.columns if c in acc.columns and c not in key_cols]
        frame = frame.drop(columns=overlap, errors="ignore")
        return acc.merge(frame, how="left", on=key_cols, sort=True)

    result = reduce(merge_pair, normalized[1:], normalized[0][1].copy())
    return result.reset_index(drop=True)
