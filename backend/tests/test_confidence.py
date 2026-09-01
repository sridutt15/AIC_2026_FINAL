"""Confidence scorer tests: weak evidence abstains; strong evidence scores high."""

from app.core.confidence.scorer import score_confidence


def test_small_sample_low_quality_abstains():
    """Small sample (low-data KPI) + poor data quality -> level 'abstain'."""
    finding = {
        "kpi_status": "low-data",
        "period_count": 4,
    }
    evidence = {
        "method": "waterfall decomposition",
        "statistic": 12.5,
        "p_value_or_effect_size": None,  # no inferential statistic
    }
    quality = {"score": 45.0}  # weak data quality
    result = score_confidence(finding, evidence, quality)
    assert result["level"] == "abstain"
    assert result["missing_evidence"], "abstain must explain what evidence is missing"
    joined = " ".join(result["missing_evidence"]).lower()
    assert "period" in joined, "should name more periods as missing evidence"


def test_strong_significance_high_quality_scores_high():
    """Strong p-value + high quality + valid sample -> level 'high'."""
    finding = {
        "kpi_status": "valid",
        "period_count": 52,
    }
    evidence = {
        "method": "difference-in-differences",
        "statistic": 20.0,
        "p_value_or_effect_size": 0.01,  # strongly significant
        "corroborating_methods": [
            {"method": "control_limit_breaches", "direction": "up"},
        ],
    }
    quality = {"score": 98.0}
    result = score_confidence(finding, evidence, quality)
    assert result["level"] == "high"
    assert all("below" not in r for r in result["reasons"])


def test_contradictory_signals_force_abstain():
    """Two methods disagreeing on direction must force abstain — even with
    strong significance and quality."""
    finding = {"kpi_status": "valid", "period_count": 40}
    evidence = {
        "method": "detector fusion",
        "statistic": 5.0,
        "p_value_or_effect_size": 0.001,
        "corroborating_methods": [
            {"method": "detector_a", "direction": "up"},
            {"method": "detector_b", "direction": "down"},
        ],
    }
    result = score_confidence(finding, evidence, {"score": 99.0})
    assert result["level"] == "abstain"
    assert any("contradictory" in r.lower() for r in result["reasons"])


def test_no_quality_report_lowers_confidence():
    """Missing quality report counts as zero evidence quality."""
    finding = {"kpi_status": "valid", "period_count": 30}
    evidence = {"statistic": 1.0, "p_value_or_effect_size": 0.3}
    result = score_confidence(finding, evidence, None)
    assert result["level"] in ("low", "abstain")


def test_missing_evidence_lists_are_actionable():
    """Every missing_evidence entry is a concrete, human-readable string."""
    finding = {"kpi_status": "low-data", "period_count": 3}
    evidence = {"statistic": None, "p_value_or_effect_size": None}
    result = score_confidence(finding, evidence, {"score": 50.0})
    assert result["level"] == "abstain"
    assert all(isinstance(m, str) and len(m) > 3 for m in result["missing_evidence"])
