"""Recommendations endpoint tests: LLM mocked — second call served from cache."""

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

from .test_evidence import _build_test_dataset


@pytest.fixture()
def ready_kpi(isolated_env):
    """Full pipeline through Phase 8; returns (client, kpi_id)."""
    init_db()
    with TestClient(app) as client:
        _, kpi_id = _build_test_dataset(client)
        return client, kpi_id


def _patch_llm(monkeypatch):
    """Patch call_llm with a counting mock; returns the mock."""
    from app.api import recommendations as rec

    calls = {"n": 0}

    def fake_call_llm(prompt, client=None):
        calls["n"] += 1
        return {
            "text": f"LLM recommendation #{calls['n']}: rebalance the assortment.",
            "prompt_tokens": 150,
            "completion_tokens": 40,
            "latency_ms": 123,
            "cost_usd": 0.000031,
            "model": "gemini-mock",
        }

    monkeypatch.setattr(rec, "call_llm", fake_call_llm)
    return calls


def test_second_call_served_from_cache(ready_kpi, monkeypatch):
    """Same package twice -> identical bullets, second call cached=true, and
    the mocked LLM invoked exactly once (no duplicate API cost)."""
    client, kpi_id = ready_kpi
    calls = _patch_llm(monkeypatch)

    first = client.get(f"/recommendations/{kpi_id}")
    assert first.status_code == 200
    body1 = first.json()
    assert body1["recommendation_bullets"][0].startswith("LLM recommendation #1")
    assert body1["llm_call_metadata"]["cached"] is False
    assert body1["llm_call_metadata"]["prompt_tokens"] == 150
    assert body1["llm_call_metadata"]["completion_tokens"] == 40
    assert body1["package"]  # structured package included

    second = client.get(f"/recommendations/{kpi_id}")
    assert second.status_code == 200
    body2 = second.json()
    assert body2["recommendation_bullets"] == body1["recommendation_bullets"]
    assert body2["llm_call_metadata"]["cached"] is True
    assert calls["n"] == 1, "the LLM must be invoked exactly once for an identical package"


def test_llm_metadata_logged_in_ledger(ready_kpi, monkeypatch):
    client, kpi_id = ready_kpi
    _patch_llm(monkeypatch)

    client.get(f"/recommendations/{kpi_id}")
    ledger = client.get("/telemetry/llm-ledger").json()

    # Every prior stage deterministic; only the LLM recommendation uses an LLM.
    stages = {s["stage"]: s["llm_used"] for s in ledger["stages"]}
    assert ledger["summary"]["llm_stages"] == 1
    assert stages["LLM recommendation"] is True
    assert all(v is False for k, v in stages.items() if k != "LLM recommendation")

    # The live call + the cache-reuse row are both logged with metadata.
    client.get(f"/recommendations/{kpi_id}")
    ledger2 = client.get("/telemetry/llm-ledger").json()
    assert ledger2["totals"]["llm_calls"] >= 2
    assert ledger2["totals"]["cost_usd"] >= 0
    assert ledger2["last_call"]["cached"] is True


def test_package_endpoint_still_llm_free(ready_kpi, monkeypatch):
    """The Phase 9 /package endpoint makes no LLM call even while the
    recommendation endpoint is mocked."""
    client, kpi_id = ready_kpi
    calls = _patch_llm(monkeypatch)
    resp = client.get(f"/recommendations/{kpi_id}/package")
    assert resp.status_code == 200
    assert resp.json()["llm_call"] is False
    assert calls["n"] == 0
