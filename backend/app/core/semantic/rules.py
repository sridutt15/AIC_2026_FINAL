"""Deterministic semantic role rules, derived purely from the Phase 1 profile output.

Mapping (per the semantic contract spec):
    temporal profile role  -> "time"
    numerical profile role -> "measure"
    categorical role       -> "dimension"
    identifier role        -> "identifier"

No ML, no LLM — pure rule logic. Enterprise-generic: roles come from the profile,
never from hardcoded column names.
"""

# Semantic roles a column can take in the contract.
SEMANTIC_ROLES = ("measure", "dimension", "time", "identifier")

# Profile detected_role -> semantic role. Direct, explicit, deterministic.
_ROLE_MAP = {
    "temporal": "time",
    "numerical": "measure",
    "categorical": "dimension",
    "identifier": "identifier",
}


def semantic_role(profiled_column: dict) -> str:
    """Map a single profiled column (dict from profile_dataframe output) to a semantic role."""
    return _ROLE_MAP.get(profiled_column.get("detected_role", ""), "dimension")


def classify_columns(profile: dict) -> dict:
    """Group all profiled columns by semantic role.

    Returns {"measure": [col dicts], "dimension": [...], "time": [...], "identifier": [...]}.
    """
    grouped: dict = {role: [] for role in SEMANTIC_ROLES}
    for col in profile.get("columns", []):
        grouped[semantic_role(col)].append(col)
    return grouped
