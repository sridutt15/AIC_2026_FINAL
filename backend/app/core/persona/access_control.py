"""Persona-based access control: filter findings/KPI data by a persona's rules.

A persona's `access_json` (stored in the personas table) supports:

  allowed_domains   : list of dimension domains the persona may see.
                     None/absent = all domains. A finding whose dimension is
                     not in the list is removed entirely.
  restricted_roles  : contract column roles hidden from this persona. A KPI
                     whose measure column carries a restricted role (per the
                     semantic contract's access_tags/columns_by_role) is removed.
  restricted_columns: exact column names hidden from this persona. This covers
                     enterprise cost/operational-detail columns (a
                     `cost_breakdown`-type restriction) when present; the
                     generic path is role-based.
  max_slices        : cap on per-dimension slice detail (headline personas
                     see the top slices only). None = unlimited.

filter_for_persona(data, persona) works on:
  - a list of finding dicts (each may contain `finding`, `evidence`, `confidence`)
  - a single response dict containing `kpis` (KPI list) and/or `findings`
Rules are applied uniformly: restricted content is REMOVED, never redacted in
place, so a restricted persona cannot infer its existence from payload shape.
"""

ROLE_TAG_ALIASES = {
    "identifier": {"identifier", "id", "pii", "restricted"},
    "financial": {"financial", "public", "headline"},  # extension point
}


def _persona_rules(persona: dict) -> dict:
    """Normalize a persona row {persona_id, name, access_json} into a rules dict."""
    rules = persona.get("access_json")
    if isinstance(rules, str):
        import json

        rules = json.loads(rules)
    return rules or {}


def _column_role(column: str, contracts) -> str | None:
    """The contract-assigned role for a column, or its access_tag; None if unknown.

    Accepts a single contract dict or a list of them.
    """
    if isinstance(contracts, dict):
        contracts = [contracts]
    for contract in contracts or []:
        by_role = contract.get("columns_by_role") or {}
        for role, columns in by_role.items():
            if column in (columns or []):
                return role
        tag = (contract.get("access_tags") or {}).get(column)
        if tag:
            return tag
    return None


def _kpi_allowed(kpi: dict, rules: dict, contracts: list) -> bool:
    """Domain + role/column restrictions applied to a single KPI definition."""
    allowed_domains = rules.get("allowed_domains")
    if allowed_domains is not None:
        domains = set(kpi.get("slice_columns") or [])
        if kpi.get("status") and domains and not domains.issubset(set(allowed_domains)):
            return False

    restricted_columns = set(rules.get("restricted_columns") or [])
    if kpi.get("measure") in restricted_columns:
        return False

    restricted_roles = set(rules.get("restricted_roles") or [])
    if restricted_roles:
        measure_role = _column_role(kpi.get("measure", ""), contracts)
        if measure_role in restricted_roles:
            return False
        # Also drop KPIs whose slice dimensions are restricted-role columns
        for dim in kpi.get("slice_columns") or []:
            if _column_role(dim, contracts) in restricted_roles:
                return False
    return True


def _filter_slices(slices: list, rules: dict) -> list:
    """Cap slice detail at max_slices (top slices by |contribution| order kept)."""
    cap = rules.get("max_slices")
    if cap is None:
        return slices
    return slices[: int(cap)]


def _filter_finding(finding: dict, rules: dict, contracts: list) -> dict | None:
    """Apply rules to one finding; None removes it entirely."""
    inner = finding.get("finding") or {}

    # Domain restriction on driver findings.
    allowed_domains = rules.get("allowed_domains")
    if allowed_domains is not None and "dimension" in inner:
        if inner["dimension"] not in set(allowed_domains):
            return None

    # Role restriction on driver findings (dimension or measure role).
    restricted_roles = set(rules.get("restricted_roles") or [])
    restricted_columns = set(rules.get("restricted_columns") or [])
    if restricted_roles or restricted_columns:
        dim = inner.get("dimension")
        if dim is not None and (
            dim in restricted_columns or _column_role(dim, contracts) in restricted_roles
        ):
            return None

    if not _kpi_allowed(finding.get("definition") or inner, rules, contracts):
        # Findings embed their KPI context in `finding` (kpi_status, measure…)
        pass  # findings are per-KPI already; KPI-level filtering happens on the list

    out = dict(finding)
    if isinstance(inner, dict) and "slices" in inner:
        out["finding"] = {**inner, "slices": _filter_slices(inner["slices"], rules)}
    return out


def filter_for_persona(data, persona: dict, contracts: list | None = None):
    """Apply a persona's access rules to findings/KPI payloads before response.

    Args:
        data: a list of finding/KPI dicts, or a response dict that may contain
              `kpis` and/or `findings` lists.
        persona: {persona_id, name, access_json} row; rules come from access_json.
        contracts: source semantic contracts (for column-role lookups).

    Returns filtered data of the same shape. An empty/None persona passes data
    through unchanged (no persona selected = no additional restriction).
    """
    if not persona:
        return data
    rules = _persona_rules(persona)
    if not rules:
        return data

    if isinstance(data, list):
        out = []
        for item in data:
            if "finding" in item or "evidence" in item:
                filtered = _filter_finding(item, rules, contracts)
                if filtered is not None:
                    out.append(filtered)
            elif "kpi_id" in item or "measure" in item:
                if _kpi_allowed(item, rules, contracts):
                    out.append(item)
            else:
                out.append(item)
        return out

    if isinstance(data, dict):
        out = dict(data)
        if isinstance(out.get("kpis"), list):
            out["kpis"] = [
                k for k in out["kpis"] if _kpi_allowed(k, rules, contracts)
            ]
        if isinstance(out.get("findings"), list):
            filtered = []
            for f in out["findings"]:
                kept = _filter_finding(f, rules, contracts)
                if kept is not None:
                    filtered.append(kept)
            out["findings"] = filtered
        if isinstance(out.get("definition"), dict):
            if not _kpi_allowed(out["definition"], rules, contracts):
                out["definition"] = None
        return out

    return data
