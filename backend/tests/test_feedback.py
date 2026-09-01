"""Feedback loop tests: repeated rejects measurably lower materiality weight."""

from app.core.feedback.store import (
    apply_feedback_adjustments,
    get_driver_multiplier,
    record_feedback,
)
from app.core.kpi_engine.materiality import score_materiality
from app.db import init_db


def _record_reject(n: int, driver_type: str = "mix") -> None:
    for i in range(n):
        record_feedback(
            target_type="recommendation",
            target_id="test-target",
            verdict="reject",
            note=f"reject #{i}",
            driver_type=driver_type,
        )


def test_repeated_rejects_lower_driver_weight(isolated_env):
    """3 rejects -> multiplier 0.55 (1.0 - 0.15*3), measurably lower score."""
    init_db()
    computation = {
        "value": 130.0,
        "baseline": 100.0,
        "trend": [
            {"period": "p1", "value": 100.0},
            {"period": "p2", "value": 102.0},
            {"period": "p3", "value": 98.0},
            {"period": "p4", "value": 100.0},
            {"period": "p5", "value": 130.0},
        ],
    }
    before = score_materiality(computation, driver_type="mix")
    assert before > 0

    _record_reject(3)
    adjustments = apply_feedback_adjustments()
    assert adjustments["adjustments"]["mix"] == 0.55  # 1.0 - 0.15*3

    after = score_materiality(computation, driver_type="mix")
    assert after < before, "repeated rejects must lower the materiality score"
    assert abs(after - before * 0.55) < 1e-3


def test_rejects_floor_at_minimum_multiplier(isolated_env):
    """Many rejects clamp at 0.25x — the weight never reaches zero."""
    init_db()
    _record_reject(10)
    apply_feedback_adjustments()
    assert get_driver_multiplier("mix") == 0.25


def test_confirms_restore_weight(isolated_env):
    """Confirm verdicts walk the multiplier back up at half the reject rate."""
    init_db()
    _record_reject(2)
    apply_feedback_adjustments()
    assert get_driver_multiplier("mix") == 0.70  # 1.0 - 0.30

    for _ in range(4):
        record_feedback(
            target_type="insight",
            target_id="test-target",
            verdict="confirm",
            driver_type="mix",
        )
    apply_feedback_adjustments()
    assert get_driver_multiplier("mix") == 1.0  # 0.70 + 0.075*4 = 1.0 (capped)


def test_adjustments_are_deterministic(isolated_env):
    """Same feedback history -> identical multipliers, every time."""
    init_db()
    _record_reject(2)
    first = apply_feedback_adjustments()["adjustments"]
    second = apply_feedback_adjustments()["adjustments"]
    assert first == second


def test_invalid_verdict_rejected(isolated_env):
    init_db()
    import pytest

    with pytest.raises(ValueError):
        record_feedback("insight", "t", "maybe")
    with pytest.raises(ValueError):
        record_feedback("weather", "t", "confirm")


def test_feedback_round_trip_via_api(isolated_env):
    """POST /feedback stores; GET /feedback/{id} and /feedback/recent return it."""
    import pytest
    from fastapi.testclient import TestClient

    from app.main import app

    init_db()
    with TestClient(app) as client:
        posted = client.post(
            "/feedback",
            json={
                "target_type": "insight",
                "target_id": "kpi-abc",
                "verdict": "reject",
                "note": "driver feels wrong",
                "driver_type": "mix",
            },
        )
        assert posted.status_code == 200
        body = posted.json()
        assert body["verdict"] == "reject"

        fetched = client.get(f"/feedback/kpi-abc")
        assert fetched.status_code == 200
        rows = fetched.json()["feedback"]
        assert len(rows) == 1 and rows[0]["note"] == "driver feels wrong"

        recent = client.get("/feedback/recent").json()["feedback"]
        assert any(r["target_id"] == "kpi-abc" for r in recent)
