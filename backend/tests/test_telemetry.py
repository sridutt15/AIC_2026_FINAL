"""Telemetry summary tests: aggregation correctness against seeded llm_calls."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection, init_db
from app.main import app


def _seed_llm_calls(rows: list) -> None:
    conn = get_connection()
    try:
        for i, (prompt_tok, comp_tok, latency, cost, cached) in enumerate(rows):
            conn.execute(
                "INSERT INTO llm_calls (call_id, kpi_id, package_hash, prompt_tokens, "
                "completion_tokens, latency_ms, cost_usd, cached, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"call-{i}",
                    "kpi-x",
                    f"hash-{i}",
                    prompt_tok,
                    comp_tok,
                    latency,
                    cost,
                    1 if cached else 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def test_summary_aggregates_seeded_llm_calls(isolated_env):
    init_db()
    _seed_llm_calls([
        (100, 50, 200, 0.000030, False),
        (200, 80, 300, 0.000052, False),
        (0, 0, 5, 0.0, True),  # cache hit: zero new tokens/cost
    ])
    with TestClient(app) as client:
        summary = client.get("/telemetry/summary").json()

    llm = summary["llm"]
    assert llm["total_calls"] == 3
    assert llm["total_prompt_tokens"] == 300  # 100 + 200 + 0
    assert llm["total_completion_tokens"] == 130
    assert abs(llm["total_cost_usd"] - 0.000082) < 1e-9
    assert llm["cached_calls"] == 1
    assert llm["cache_hit_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert llm["avg_latency_ms"] == pytest.approx((200 + 300 + 5) / 3, abs=0.2)
    assert len(summary["llm_calls_over_time"]) == 3
    assert summary["stage_latencies"] == []  # no stage timings seeded yet


def test_summary_cache_hit_rate_zero_when_no_calls(isolated_env):
    init_db()
    with TestClient(app) as client:
        summary = client.get("/telemetry/summary").json()
    assert summary["llm"]["total_calls"] == 0
    assert summary["llm"]["cache_hit_rate"] == 0.0
    assert summary["llm"]["total_cost_usd"] == 0.0


def test_stage_timings_appear_in_summary(isolated_env):
    init_db()
    conn = get_connection()
    try:
        for latency in (100, 200, 300):
            conn.execute(
                "INSERT INTO stage_timings (stage, latency_ms, recorded_at) "
                "VALUES (?, ?, ?)",
                ("driver analysis", latency, datetime.now(timezone.utc).isoformat()),
            )
        conn.commit()
    finally:
        conn.close()

    with TestClient(app) as client:
        summary = client.get("/telemetry/summary").json()

    stage = next(s for s in summary["stage_latencies"] if s["stage"] == "driver analysis")
    assert stage["calls"] == 3
    assert stage["avg_latency_ms"] == pytest.approx(200.0, abs=0.2)
    assert stage["min_latency_ms"] == 100
    assert stage["max_latency_ms"] == 300


def test_timed_stage_decorator_records_latency(isolated_env):
    """Functions wrapped with @timed_stage persist their wall-clock latency."""
    import time

    from app.core.telemetry.logger import timed_stage

    @timed_stage("test stage")
    def slow_add(a, b):
        time.sleep(0.02)
        return a + b

    assert slow_add(1, 2) == 3
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT stage, latency_ms FROM stage_timings WHERE stage = 'test stage'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0]["latency_ms"] >= 15  # at least the slept 20ms (rounded)


def test_summary_includes_feedback_adjustments(isolated_env):
    init_db()
    from app.core.feedback.store import apply_feedback_adjustments, record_feedback

    record_feedback(
        target_type="recommendation", target_id="t1",
        verdict="reject", driver_type="mix",
    )
    apply_feedback_adjustments()
    with TestClient(app) as client:
        summary = client.get("/telemetry/summary").json()
    assert summary["feedback_adjustments"] == {"mix": 0.85}
