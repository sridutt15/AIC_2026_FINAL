"""Insight generator tests: byte-for-byte determinism + persona tone split."""

from app.core.insight_templates.generator import generate_insight, build_regenerate_proof

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


def test_identical_inputs_produce_identical_strings():
    """Calling the generator twice with identical input -> identical bytes."""
    first = generate_insight(persona_id="category_manager", **SYNTHETIC)
    second = generate_insight(persona_id="category_manager", **SYNTHETIC)
    assert first == second
    assert first.encode("utf-8") == second.encode("utf-8")  # byte-for-byte


def test_regenerate_proof_reports_identical():
    proof = build_regenerate_proof(persona_id="cfo", **SYNTHETIC)
    assert proof["identical"] is True
    assert proof["first"] == proof["second"]


def test_cfo_gets_headline_financial_only():
    """CFO text has headline + confidence, and NO slice-level detail."""
    text = generate_insight(persona_id="cfo", **SYNTHETIC)
    assert "Gross Revenue" in text
    assert "decreased" in text
    assert "EMEA" not in text, "CFO must not see slice-level driver detail"
    assert "Top driver" not in text
    assert "Confidence:" in text


def test_category_manager_gets_driver_detail():
    """Category Manager text names the top driver, its magnitude and share."""
    text = generate_insight(persona_id="category_manager", **SYNTHETIC)
    assert "Gross Revenue" in text
    assert "region" in text
    assert "EMEA" in text
    assert "Top driver" in text
    assert "77.8%" in text
    assert "Confidence:" in text


def test_default_persona_is_balanced():
    text = generate_insight(persona_id=None, **SYNTHETIC)
    assert "Gross Revenue" in text
    assert "EMEA" in text  # balanced view includes the driver summary


def test_directions_and_magnitudes_render():
    up = generate_insight(
        kpi_name="Orders", direction="up", magnitude=320.0, magnitude_pct=0.12,
        top_driver={"dimension": "channel", "slice": "mobile",
                     "contribution": 300.0, "share_pct": 93.75, "direction": "up"},
        confidence={"level": "medium", "reasons": []},
    )
    assert "increased" in up and "(+12.0%)" in up
    flat = generate_insight(kpi_name="Orders", direction="flat", magnitude=0.0)
    assert "held steady" in flat


def test_missing_optional_inputs_still_deterministic():
    """Minimal input (no driver/confidence) — still deterministic + sane."""
    first = generate_insight("Orders", "up", 10.0)
    second = generate_insight("Orders", "up", 10.0)
    assert first == second
    assert "Orders" in first and "increased" in first
    assert "Confidence: unscored." in first
