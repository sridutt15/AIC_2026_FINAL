"""Insight generator tests (Phase 18): bulleted output, byte-for-byte determinism."""

from app.core.insight_templates.generator import (
    build_regenerate_proof,
    generate_insight,
    generate_insight_bullets,
)

SYNTHETIC = dict(
    kpi_name="Gross Revenue",
    direction="down",
    magnitude=-15420.5,
    magnitude_pct=-0.083,
    top_driver={
        "dimension": "region",
        "slice": "EMEA",
        "contribution": -12010.25,
        "share_pct": 77.8,
        "direction": "down",
    },
    confidence={"level": "high", "reasons": ["composite evidence score 0.86"]},
    before={"period": "2026-07-01", "value": 185300.0},
    after={"period": "2026-08-01", "value": 169879.5},
)


def test_bullets_are_a_list_of_strings():
    bullets = generate_insight_bullets(**SYNTHETIC)
    assert isinstance(bullets, list)
    assert all(isinstance(b, str) and b.strip() for b in bullets)


def test_identical_inputs_produce_identical_bullets():
    """Calling the generator twice with identical input -> identical list."""
    first = generate_insight_bullets(**SYNTHETIC)
    second = generate_insight_bullets(**SYNTHETIC)
    assert first == second


def test_bullets_carry_headline_driver_confidence():
    """One bullet per idea: headline movement, top driver, confidence."""
    bullets = generate_insight_bullets(**SYNTHETIC)
    joined = " ".join(bullets)
    assert "Gross Revenue" in joined
    assert "decreased" in joined
    assert "Top driver" in joined and "EMEA" in joined
    assert "77.8%" in joined
    assert "Confidence" in joined
    # Each bullet is short (not a paragraph).
    assert all(len(b) < 200 for b in bullets)


def test_regenerate_proof_reports_identical():
    proof = build_regenerate_proof(**SYNTHETIC)
    assert proof["identical"] is True
    assert proof["first"] == proof["second"]


def test_legacy_paragraph_renderer_matches_bullet_join():
    """The legacy single-text renderer joins the same bullets (back-compat)."""
    text = generate_insight(**SYNTHETIC)
    bullets = generate_insight_bullets(**SYNTHETIC)
    assert text == " ".join(bullets)


def test_directions_and_magnitudes_render():
    up = generate_insight_bullets(
        kpi_name="Orders", direction="up", magnitude=320.0, magnitude_pct=0.12,
        top_driver={"dimension": "channel", "slice": "mobile",
                     "contribution": 300.0, "share_pct": 93.75, "direction": "up"},
        confidence={"level": "medium", "reasons": []},
    )
    joined = " ".join(up)
    assert "increased" in joined and "(+12.0%)" in joined
    flat = generate_insight_bullets(kpi_name="Orders", direction="flat", magnitude=0.0)
    assert "held steady" in " ".join(flat)


def test_missing_optional_inputs_still_deterministic():
    """Minimal input (no driver/confidence) — still deterministic + sane."""
    first = generate_insight_bullets("Orders", "up", 10.0)
    second = generate_insight_bullets("Orders", "up", 10.0)
    assert first == second
    joined = " ".join(first)
    assert "Orders" in joined and "increased" in joined
    assert "Confidence: unscored." in joined
