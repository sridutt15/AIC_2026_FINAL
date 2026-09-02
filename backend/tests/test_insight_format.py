"""Insight format tests (Phase 18): bulleted list output, deterministic."""

from app.core.insight_templates.generator import generate_insight_bullets

INPUTS = dict(
    kpi_name="Revenue",
    direction="up",
    magnitude=1200.0,
    magnitude_pct=0.12,
    top_driver={
        "dimension": "region",
        "slice": "North",
        "contribution": 900.0,
        "share_pct": 75.0,
        "direction": "up",
    },
    confidence={"level": "high", "reasons": ["score 0.9"]},
    before={"period": "2026-01-01", "value": 10000.0},
    after={"period": "2026-02-01", "value": 11200.0},
)


def test_generator_returns_list_not_paragraph():
    """Output is a list of strings — one short bullet per idea."""
    bullets = generate_insight_bullets(**INPUTS)
    assert isinstance(bullets, list), "must be a list, not a paragraph string"
    assert len(bullets) >= 2
    assert all(isinstance(b, str) for b in bullets)
    assert all(b.strip() for b in bullets)
    # Bullets, not sentences jammed together: each is reasonably short.
    assert all(len(b) <= 200 for b in bullets)


def test_generator_is_deterministic():
    """Same input twice -> identical bullets, same order."""
    first = generate_insight_bullets(**INPUTS)
    second = generate_insight_bullets(**INPUTS)
    assert first == second


def test_bullets_cover_the_expected_content():
    """Headline + driver + confidence present across the bullets."""
    joined = " ".join(generate_insight_bullets(**INPUTS))
    assert "Revenue" in joined
    assert "Top driver" in joined
    assert "Confidence" in joined
