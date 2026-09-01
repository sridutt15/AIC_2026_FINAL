"""KPI discovery: turn contract kpi_definitions into unique candidate KPIs.

Deterministic: each contract's kpi_definitions (measure + aggregation + slice
dimensions) is cross-referenced against the canonical dataframe's columns.
Candidates are deduplicated by their semantic signature (measure, aggregation,
slice columns) so overlapping contracts from merged sources never yield dupes.
No LLM — pure rule logic.
"""

import pandas as pd

from app.core.canonical.reconciler import _find_time_column  # deterministic date finder

MIN_PERIODS_DEFAULT = 8  # below this, validation flags "low-data"


def _kpi_signature(defn: dict) -> tuple:
    """Stable dedup key for a KPI definition."""
    slices = tuple(sorted(defn.get("slice_columns", [])))
    return (defn["measure"], defn["aggregation"], slices)


def _candidate_name(defn: dict) -> str:
    """Human-readable KPI name, derived generically: agg(measure)[ by dims]."""
    parts = [defn["aggregation"], defn["measure"]]
    name = f"{defn['aggregation']}({defn['measure']})"
    if defn.get("slice_columns"):
        name += " by " + " & ".join(defn["slice_columns"])
    return name


def discover_kpis(canonical_df: pd.DataFrame, contracts: list) -> list:
    """Generate candidate KPIs from merged contracts against the canonical dataframe.

    Args:
        canonical_df: the reconciled canonical dataset.
        contracts: list of contract dicts (each with kpi_definitions).

    Returns a list of candidate dicts:
        {name, measure, aggregation, slice_columns, time_column}
    Deduplicated by (measure, aggregation, sorted slices). Columns referenced by a
    definition but missing from the canonical frame are filtered out.
    """
    columns = set(canonical_df.columns)
    time_column = _find_time_column(canonical_df)

    seen: set = set()
    candidates = []
    for contract in contracts:
        for defn in contract.get("kpi_definitions", []):
            measure = defn.get("column")
            aggregation = defn.get("aggregation", "sum")
            if not measure or measure not in columns:
                continue
            if time_column is not None and time_column == measure:
                continue
            slice_columns = [
                s for s in defn.get("sliceable_by", []) if s in columns and s != time_column
            ]
            candidate = {
                "measure": measure,
                "aggregation": aggregation,
                "slice_columns": slice_columns,
            }
            sig = _kpi_signature(candidate)
            if sig in seen:
                continue
            seen.add(sig)
            candidate["name"] = _candidate_name(candidate)
            candidate["time_column"] = time_column
            candidates.append(candidate)
    return candidates
