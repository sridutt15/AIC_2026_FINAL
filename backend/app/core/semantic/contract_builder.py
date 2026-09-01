"""Deterministic semantic-contract builder.

build_contract(profile) turns a Phase 1 column profile into a reviewable contract:
KPI candidates, hierarchy hints, calendar info, default thresholds, and access tags.
Pure function of the profile — same input, same output every time. No ML, no LLM.
"""

from app.core.semantic.rules import classify_columns

# Heuristics ----------------------------------------------------------------


def _default_aggregation(col: dict) -> str:
    """Pick a default aggregation for a measure column.

    Rule (documented, deterministic):
      - ratio-like columns (name suggests share/percent/fraction/rate/avg, or all values
        fall in [0,1]) default to "avg" — summing a percentage is usually meaningless;
      - columns whose name suggests a count (count, qty, qty, units, volume) default to "sum";
      - anything else with "rate" in the name defaults to "rate";
      - otherwise "sum" (additive business measures are the common case).
    """
    name = col["name"]
    if any(k in name for k in ("pct", "percent", "share", "fraction", "ratio")):
        return "avg"
    if "rate" in name:
        return "rate"
    samples = [v for v in col.get("sample_values", []) if isinstance(v, (int, float))]
    if samples and all(0.0 <= float(v) <= 1.0 for v in samples) and len(samples) >= 2:
        return "avg"
    return "sum"


def _detect_hierarchies(dimension_cols: list) -> list:
    """Detect likely parent->child dimension pairs. Documented heuristics, deterministic:

    1. Common-prefix rule: two dimensions where one name is a prefix of the other
       (e.g. region / region_country) -> longer name is the child.
    2. Prefix-token rule: names built from tokens where one name's tokens extend the
       other's (e.g. product / product_line) -> longer is the child.
    Returns [{"parent": str, "child": str}, ...], no duplicates, order by name for stability.
    """
    dims = sorted(dimension_cols, key=lambda c: c["name"])
    hierarchies = []

    def _tokens(name: str) -> list:
        return [t for t in name.split("_") if t]

    for i, parent in enumerate(dims):
        p_name = parent["name"]
        p_tokens = _tokens(p_name)
        for child in dims[i + 1 :]:
            c_name = child["name"]
            if c_name == p_name:
                continue
            c_tokens = _tokens(c_name)
            # Rule 1: exact name prefix (underscore boundary: product_line starts with product)
            if c_name.startswith(p_name):
                hierarchies.append({"parent": p_name, "child": c_name})
                continue
            # Rule 2: child tokens begin with exactly the parent's tokens
            if c_tokens[: len(p_tokens)] == p_tokens:
                hierarchies.append({"parent": p_name, "child": c_name})

    return hierarchies


def _detect_granularity(time_col: dict, row_count: int) -> str:
    """Infer calendar granularity for the detected time column.

    Deterministic rule:
      - default granularity is "day" (the phase spec's default);
      - if the time column's name contains "week" -> "week"; "month" or "monthly" -> "month";
        "quarter" -> "month" (quarterly data still groups by month at coarser steps later);
        "year" -> "month".
    Name-based hints only; the user can correct this in the UI.
    """
    if time_col is None:
        return "day"
    name = time_col["name"]
    if "week" in name:
        return "week"
    if any(k in name for k in ("month", "quarter", "year")):
        return "month"
    return "day"


# Contract builder -----------------------------------------------------------


def build_contract(profile: dict, grain: str | None = None) -> dict:
    """Build a full semantic contract from a Phase 1 profile.

    Args:
        profile: output of profile_dataframe ({"row_count": int, "columns": [...]}).
        grain: optional source grain string, used only for informational fields.

    Returns the contract dict with kpi_definitions, hierarchies, calendar,
    thresholds, access_tags, plus the classified columns for review.
    """
    grouped = classify_columns(profile)
    measures = grouped["measure"]
    dimensions = grouped["dimension"]
    time_cols = grouped["time"]

    dimension_names = [c["name"] for c in dimensions]

    # KPI candidates: one per measure column. Identifiers are never KPI candidates.
    kpi_definitions = []
    for col in measures:
        kpi_definitions.append(
            {
                "column": col["name"],
                "aggregation": _default_aggregation(col),
                "sliceable_by": list(dimension_names),
            }
        )

    # Calendar: first detected time column (profile order), plus granularity.
    time_col = time_cols[0] if time_cols else None
    calendar = {
        "time_column": time_col["name"] if time_col else None,
        "granularity": _detect_granularity(time_col, profile.get("row_count", 0)),
    }

    hierarchies = _detect_hierarchies(dimensions)

    # Default materiality threshold: a movement is material when |z| > 1.0 std devs.
    # Starting default — the user edits this in the UI.
    thresholds = {
        "materiality_std_devs": 1.0,
        "min_support_rows": 10,
    }

    # Default access tag on every column; Phase 8 will let users restrict specific columns.
    access_tags = {
        col["name"]: "public"
        for col in profile.get("columns", [])
    }

    return {
        "grain": grain,
        "kpi_definitions": kpi_definitions,
        "hierarchies": hierarchies,
        "calendar": calendar,
        "thresholds": thresholds,
        "access_tags": access_tags,
        "columns_by_role": {
            "measure": [c["name"] for c in measures],
            "dimension": dimension_names,
            "time": [c["name"] for c in time_cols],
            "identifier": [c["name"] for c in grouped["identifier"]],
        },
    }
