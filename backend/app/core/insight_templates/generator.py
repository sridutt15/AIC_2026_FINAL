"""Deterministic insight generator: findings in, persona-specific text out.

NO LLM — plain Python f-strings over a documented template table. The
generator is provably deterministic: identical inputs produce a
byte-for-byte identical string (see tests/test_insight_generator.py).

Inputs (all optional except kpi_name/direction/magnitude):
    kpi_name        : display name of the KPI (e.g. "Gross Revenue")
    direction       : "up" | "down" | "flat" — movement direction
    magnitude       : signed float — the movement amount
    magnitude_pct   : optional relative movement (0.12 = +12%)
    top_driver      : {"dimension": str, "slice": str, "contribution": float,
                       "share_pct": float} — the largest single driver
    confidence      : {"level": "high"|"medium"|"low", reasons: [...]}
    before/after    : {"period": str, "value": float} period endpoints

Persona tone (persona_id):
    category_manager — full driver-level detail: which dimension/slice moved,
        by how much, and the share of the total movement it explains.
    cfo             — headline + financial impact only: direction, size,
        confidence; no slice-level operational detail.
    default/None    — balanced: headline + one-line driver summary.

Every template uses fixed separators and rounding so output never depends on
dict ordering, locale, or wall-clock time.
"""

PERSONA_TONES = {
    "category_manager": "tactical detail",
    "cfo": "headline financial",
}

_LEVEL_PHRASES = {
    "high": "high-confidence",
    "medium": "medium-confidence",
    "low": "low-confidence",
}

_VERB_UP = "increased"
_VERB_DOWN = "decreased"
_VERB_FLAT = "held steady"


def _fmt_number(value: float) -> str:
    """Deterministic number formatting: thousands separators, 2dp, no locale."""
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _direction_phrase(direction: str, magnitude, magnitude_pct=None) -> str:
    """'increased by 1,234.00 (+8.4%)' / 'held steady'.

    magnitude_pct is a FRACTION (0.084 = +8.4%), rendered as a percentage.
    """
    d = (direction or "flat").lower()
    if d == "flat":
        return _VERB_FLAT
    verb = _VERB_UP if d == "up" else _VERB_DOWN
    phrase = f"{verb} by {_fmt_number(magnitude)}"
    if magnitude_pct is not None:
        try:
            phrase += f" ({float(magnitude_pct) * 100:+.1f}%)"
        except (TypeError, ValueError):
            pass
    return phrase


def _headline(kpi_name: str, direction: str, magnitude, magnitude_pct=None) -> str:
    return f"{kpi_name} {_direction_phrase(direction, magnitude, magnitude_pct)}"


def _driver_sentence(top_driver: dict | None) -> str:
    """One-line description of the largest driver; empty string when absent."""
    if not top_driver:
        return ""
    dimension = top_driver.get("dimension") or "unknown dimension"
    slice_name = top_driver.get("slice")
    contribution = top_driver.get("contribution")
    share = top_driver.get("share_pct")
    direction = (top_driver.get("direction") or ("up" if (contribution or 0) >= 0 else "down")).lower()
    where = f"'{slice_name}'" if slice_name is not None else "an unlabeled slice"
    parts = [
        f"Top driver: {dimension} = {where} contributed "
        f"{_fmt_number(contribution)} ({direction})"
    ]
    if share is not None:
        parts[0] += f", {share:.1f}% of the total movement"
    parts[0] += "."
    return " ".join(parts)


def _confidence_phrase(confidence: dict | None) -> str:
    if not confidence:
        return "Confidence: unscored."
    level = str(confidence.get("level", "unscored")).lower()
    phrase = _LEVEL_PHRASES.get(level, level)
    return f"Confidence: {phrase}."


def generate_insight(
    kpi_name: str,
    direction: str,
    magnitude,
    persona_id: str | None = None,
    magnitude_pct=None,
    top_driver: dict | None = None,
    confidence: dict | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> str:
    """Render the persona-specific insight text. Pure function — deterministic.

    Calling this twice with identical arguments returns an identical string.
    """
    headline = _headline(kpi_name, direction, magnitude, magnitude_pct)
    driver = _driver_sentence(top_driver)
    conf = _confidence_phrase(confidence)

    pid = (persona_id or "").lower()

    if pid == "cfo":
        # CFO: headline + financial impact + confidence only. No slice detail.
        return f"{headline}. {conf}"

    if pid == "category_manager":
        # Category Manager: full driver-level detail.
        parts = [f"{headline}."]
        if driver:
            parts.append(driver)
        parts.append(conf)
        return " ".join(parts)

    # Default persona: headline + driver summary + confidence.
    parts = [f"{headline}."]
    if driver:
        parts.append(driver)
    parts.append(conf)
    return " ".join(parts)


def build_regenerate_proof(
    kpi_name: str,
    direction: str,
    magnitude,
    persona_id: str | None = None,
    **kwargs,
) -> dict:
    """Call generate_insight twice and return both outputs for a UI diff check.

    Returns {first: str, second: str, identical: bool} — the visible proof of
    determinism for the Insights page's Regenerate button.
    """
    first = generate_insight(kpi_name, direction, magnitude, persona_id, **kwargs)
    second = generate_insight(kpi_name, direction, magnitude, persona_id, **kwargs)
    return {"first": first, "second": second, "identical": first == second}
