"""Deterministic insight generator: findings in, bulleted text out (Phase 18).

NO LLM — plain Python f-strings over a documented template table. The
generator is provably deterministic: identical inputs produce a
byte-for-byte identical list (see tests/test_insight_generator.py).

Inputs (all optional except kpi_name/direction/magnitude):
    kpi_name        : display name of the KPI (e.g. "Gross Revenue")
    direction       : "up" | "down" | "flat" — movement direction
    magnitude       : signed float — the movement amount
    magnitude_pct   : optional relative movement (0.12 = +12%)
    top_driver      : {"dimension": str, "slice": str, "contribution": float,
                       "share_pct": float} — the largest single driver
    confidence      : {"level": "high"|"medium"|"low", reasons: [...]}
    before/after    : {"period": str, "value": float} period endpoints

Every template uses fixed separators and rounding so output never depends on
dict ordering, locale, or wall-clock time.
"""

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


def generate_insight_bullets(
    kpi_name: str,
    direction: str,
    magnitude,
    magnitude_pct=None,
    top_driver: dict | None = None,
    confidence: dict | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> list:
    """Render the insight as a list of short bullet strings (Phase 18).

    Pure function — deterministic: identical inputs produce a byte-for-byte
    identical list. Bullets: headline movement, top driver, confidence.
    """
    headline = _headline(kpi_name, direction, magnitude, magnitude_pct)
    driver = _driver_sentence(top_driver)
    conf = _confidence_phrase(confidence)

    bullets = [f"{headline}."]
    if driver:
        # Trim the trailing period so each bullet reads as one clean point.
        bullets.append(driver.rstrip("."))
        bullets[-1] += "."
    bullets.append(conf)
    return bullets


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
    """Legacy single-paragraph renderer (kept for pre-Phase-18 callers/tests).

    Calls the bullet generator and joins the bullets into one paragraph.
    """
    bullets = generate_insight_bullets(
        kpi_name, direction, magnitude,
        magnitude_pct=magnitude_pct, top_driver=top_driver,
        confidence=confidence, before=before, after=after,
    )
    return " ".join(bullets)


def build_regenerate_proof(
    kpi_name: str,
    direction: str,
    magnitude,
    persona_id: str | None = None,
    **kwargs,
) -> dict:
    """Call generate_insight_bullets twice and return both outputs for a UI diff check.

    Returns {first, second, identical} — the visible proof of determinism for
    the Insights page's Regenerate button.
    """
    first = generate_insight_bullets(kpi_name, direction, magnitude, **kwargs)
    second = generate_insight_bullets(kpi_name, direction, magnitude, **kwargs)
    return {"first": first, "second": second, "identical": first == second}
