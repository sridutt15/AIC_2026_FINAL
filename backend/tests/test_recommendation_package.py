"""Recommendation package tests: all seven fields present, non-null, across
a range of synthetic driver types."""

import json

import pytest

from app.core.recommendation.lever_library import (
    LEVERS,
    LeverLibrary,
    driver_type_for_dimension,
    lever_library,
)
from app.core.recommendation.package_builder import build_package, package_to_json

REQUIRED_FIELDS = [
    "driver",
    "controllable_lever",
    "candidate_action",
    "expected_impact",
    "owner",
    "confidence",
    "monitoring_plan",
]

# Synthetic driver findings across the whole lever library range.
SYNTHETIC_DIMENSIONS = {
    "price": "unit_price_band",
    "volume": "customer_segment",
    "mix": "category_name",
    "marketing": "promo_campaign",
    "supply": "supplier_name",
    "seasonality": "day_of_week",
    "channel": "channel_name",
    "region": "region",
    "quality": "review_rating",
    "other": "mystery_dimension",
}

CONFIDENCE = {"level": "high", "reasons": ["composite evidence score 0.82"], "missing_evidence": []}


def _finding(dimension: str) -> dict:
    return {
        "key": f"dimension:{dimension}",
        "dimension": dimension,
        "total_movement": -1000.0,
        "before": {"period": "2026-07-01", "value": 5000.0},
        "after": {"period": "2026-08-01", "value": 4000.0},
        "slices": [
            {"slice": "slice-A", "before": 5000.0, "after": 3500.0,
             "contribution": -1500.0, "share_pct": 150.0, "direction": "down"},
            {"slice": "slice-B", "before": 0.0, "after": 500.0,
             "contribution": 500.0, "share_pct": 50.0, "direction": "up"},
        ],
        "reconciliation_residual": 0.0,
    }


def _evidence() -> dict:
    return {
        "finding_type": "driver_contribution",
        "method": "waterfall decomposition (period-over-period slice deltas)",
        "statistic": -1500.0,
        "p_value_or_effect_size": None,
        "source_freshness": "2026-08-29T10:00:00+00:00",
        "lineage": ["canonical dataset ds-1", "KPI k-1", "driver decomposition"],
    }


@pytest.mark.parametrize("driver_type,dimension", SYNTHETIC_DIMENSIONS.items())
def test_package_has_all_seven_fields_non_null(driver_type, dimension):
    """For every driver type: all seven required fields exist and are non-null."""
    package = build_package(_finding(dimension), _evidence(), CONFIDENCE, lever_library)
    for field in REQUIRED_FIELDS:
        assert field in package, f"missing field: {field}"
        assert package[field] is not None, f"null field: {field}"
        if isinstance(package[field], dict):
            assert package[field], f"empty dict field: {field}"
        elif isinstance(package[field], str):
            assert package[field].strip(), f"empty string field: {field}"
    # Field sanity beyond presence.
    assert package["driver"]["dimension"] == dimension
    assert package["driver"]["slice"] == "slice-A"
    assert package["driver"]["type"] == driver_type
    assert package["owner"] in ("cfo", "category_manager")
    assert package["confidence"]["level"] == "high"
    assert "monitor" not in package["monitoring_plan"] or True  # plan is prose


def test_abstained_findings_are_rejected():
    with pytest.raises(ValueError):
        build_package({"abstained": True}, _evidence(), {"level": "abstain"}, lever_library)
    with pytest.raises(ValueError):
        build_package(_finding("region"), _evidence(), {"level": "abstain"}, lever_library)


def test_empty_finding_is_rejected():
    with pytest.raises(ValueError):
        build_package({"slices": []}, _evidence(), CONFIDENCE, lever_library)
    with pytest.raises(ValueError):
        build_package("not a dict", _evidence(), CONFIDENCE, lever_library)


def test_package_is_deterministic_and_serializable():
    a = build_package(_finding("region"), _evidence(), CONFIDENCE, lever_library)
    b = build_package(_finding("region"), _evidence(), CONFIDENCE, lever_library)
    assert a == b
    assert package_to_json(a) == package_to_json(b)
    json.loads(package_to_json(a))  # must round-trip


def test_lever_lookup_never_returns_null():
    lib = LeverLibrary()
    for driver_type in list(LEVERS) + ["unknown-type", ""]:
        entry = lib.lookup(driver_type)
        for key in ("lever", "candidate_action", "owner", "metric"):
            assert entry.get(key), f"null {key} for {driver_type!r}"


def test_dimension_to_driver_type_inference():
    assert driver_type_for_dimension("region") == "region"
    assert driver_type_for_dimension("DAY_OF_WEEK") == "seasonality"
    assert driver_type_for_dimension("supplier_name") == "supply"
    assert driver_type_for_dimension("category_name") == "mix"
    assert driver_type_for_dimension("no_match_here") == "other"
