"""Phase 9 API tests: /insights and /recommendations package — deterministic,
persona-specific, zero LLM."""

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

from .test_evidence import _build_test_dataset


@pytest.fixture()
def ready_kpi(isolated_env):
    """Full pipeline through Phase 8: returns (client, kpi_id) with a computed KPI."""
    init_db()
    with TestClient(app) as client:
        _, kpi_id = _build_test_dataset(client)
        return client, kpi_id


def test_insight_generated_and_deterministic(ready_kpi):
    client, kpi_id = ready_kpi
    first = client.get(f"/insights/{kpi_id}")
    assert first.status_code == 200
    body = first.json()
    assert body["deterministic"] is True
    assert body["text"], "insight text must be non-empty"
    assert body["kpi_name"] in body["text"]
    assert body["confidence"] is not None

    # Regenerate: identical text, previous_text reported for the diff check.
    second = client.get(f"/insights/{kpi_id}?refresh=true")
    assert second.status_code == 200
    regen = second.json()
    assert regen["text"] == body["text"], "regeneration must be byte-identical"
    assert regen["previous_text"] == body["text"]


def test_insight_persona_tones_differ(ready_kpi):
    client, kpi_id = ready_kpi
    cm = client.get(f"/insights/{kpi_id}?persona_id=category_manager").json()
    cfo = client.get(f"/insights/{kpi_id}?persona_id=cfo").json()
    assert cm["persona_name"] == "Category Manager"
    assert cfo["persona_name"] == "CFO"
    # CFO gets the headline only; Category Manager gets driver detail.
    assert "Top driver" in cm["text"]
    assert "Top driver" not in cfo["text"]
    assert cm["text"] != cfo["text"]


def test_recommendation_package_has_seven_fields(ready_kpi):
    client, kpi_id = ready_kpi
    resp = client.get(f"/recommendations/{kpi_id}/package")
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_call"] is False, "Phase 9 must make zero LLM calls"
    pkg = body["package"]
    for field in (
        "driver", "controllable_lever", "candidate_action", "expected_impact",
        "owner", "confidence", "monitoring_plan",
    ):
        assert field in pkg and pkg[field], f"field {field} missing/null"
    assert pkg["owner"] in ("cfo", "category_manager")

    # Package build is deterministic too.
    again = client.get(f"/recommendations/{kpi_id}/package").json()
    assert again["package"] == pkg


def test_insights_and_packages_tables_populated(ready_kpi):
    client, kpi_id = ready_kpi
    assert client.get(f"/insights/{kpi_id}").status_code == 200
    assert client.get(f"/recommendations/{kpi_id}/package").status_code == 200

    from app.db import get_connection
    conn = get_connection()
    try:
        n_insights = conn.execute(
            "SELECT COUNT(*) AS n FROM insights WHERE kpi_id = ?", (kpi_id,)
        ).fetchone()["n"]
        n_packages = conn.execute(
            "SELECT COUNT(*) AS n FROM recommendation_packages WHERE kpi_id = ?",
            (kpi_id,),
        ).fetchone()["n"]
    finally:
        conn.close()
    assert n_insights >= 1
    assert n_packages >= 1
