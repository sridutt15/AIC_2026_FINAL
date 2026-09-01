"""Per-user data isolation tests (Phase 15) — the core security guarantee.

Seeds two users, A and B. As A: upload a source, profile it, build a
canonical dataset, discover KPIs, compute one, run drivers + recommendations.
As B: every list endpoint must be empty and every direct fetch-by-ID of A's
resources must return a clean 404 — never A's data, never a server error.
"""

import io
import json

from fastapi.testclient import TestClient

from app.db import get_connection, init_db
from app.main import app
from app.core.auth.security import get_current_user

CSV_A = (
    "date,region,revenue,order_id\n"
    "2026-01-01,A,100.0,O1\n"
    "2026-01-02,A,110.0,O2\n"
    "2026-01-03,A,120.0,O3\n"
    "2026-01-01,B,50.0,O4\n"
    "2026-01-02,B,55.0,O5\n"
    "2026-01-03,B,45.0,O6\n"
)
CSV_B = (
    "date,channel,spend,ad_id\n"
    "2026-01-01,search,10.0,P1\n"
    "2026-01-02,search,12.0,P2\n"
    "2026-01-03,search,14.0,P3\n"
    "2026-01-01,social,5.0,P4\n"
    "2026-01-02,social,4.0,P5\n"
    "2026-01-03,social,6.0,P6\n"
)
CSV_A2 = (
    "date,bonus\n"
    "2026-01-01,1.0\n"
    "2026-01-02,2.0\n"
    "2026-01-03,3.0\n"
)
CSV_B2 = (
    "date,impressions\n"
    "2026-01-01,1000\n"
    "2026-01-02,1100\n"
    "2026-01-03,1200\n"
)

USER_A = {
    "user_id": "user-a-0001",
    "email": "user-a@example.com",
    "full_name": "User A",
    "role": "member",
    "created_at": "2026-01-01T00:00:00+00:00",
}
USER_B = {
    "user_id": "user-b-0002",
    "email": "user-b@example.com",
    "full_name": "User B",
    "role": "member",
    "created_at": "2026-01-01T00:00:00+00:00",
}


def _seed_user(user: dict) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (user_id, email, password_hash, full_name, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (user_id) DO NOTHING",
            (
                user["user_id"],
                user["email"],
                "not-a-real-hash",
                user["full_name"],
                user["role"],
                user["created_at"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _act_as(user: dict):
    """Point get_current_user at `user` (real dependency, no stub)."""
    app.dependency_overrides[get_current_user] = lambda: dict(user)
    return TestClient(app)


def _upload(client: TestClient, filename: str, content: str) -> str:
    resp = client.post(
        "/ingestion/upload",
        files={"file": (filename, io.BytesIO(content.encode()), "text/csv")},
        data={"grain": "Daily", "cadence": "Nightly batch"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["source_id"]


def _run_pipeline(client: TestClient, source_ids: list) -> dict:
    """Profile sources, build a canonical dataset, discover + compute a KPI."""
    for sid in source_ids:
        assert client.get(f"/profiling/{sid}").status_code == 200
        assert client.get(f"/semantic-contract/{sid}").status_code == 200
    join_keys = {"date": {str(i): "date" for i in range(len(source_ids))}}
    build = client.post(
        "/canonical/build",
        json={"source_ids": source_ids, "join_keys": join_keys},
    )
    assert build.status_code == 200, build.text
    dataset_id = build.json()["dataset_id"]

    disc = client.post(f"/kpi/discover/{dataset_id}")
    assert disc.status_code == 200, disc.text
    kpis = disc.json()["kpis"]
    assert kpis, "expected KPI candidates"

    kpi_id = kpis[0]["kpi_id"]
    comp = client.get(f"/kpi/{kpi_id}/compute")
    assert comp.status_code == 200, comp.text
    return {"dataset_id": dataset_id, "kpi_id": kpi_id}


def test_full_isolation_between_users(real_auth):
    """B sees nothing of A's: empty lists + 404 direct fetches everywhere."""
    init_db()
    _seed_user(USER_A)
    _seed_user(USER_B)

    # --- As A: build a full analysis pipeline -------------------------------
    client_a = _act_as(USER_A)
    sid_a = _upload(client_a, "sales.csv", CSV_A)
    sid_a2 = _upload(client_a, "bonus.csv", CSV_A2)
    pipe_a = _run_pipeline(client_a, [sid_a, sid_a2])
    ds_a, kpi_a = pipe_a["dataset_id"], pipe_a["kpi_id"]

    # A runs drivers (generates findings) and the recommendation package.
    drv_a = client_a.get(f"/drivers/{kpi_a}")
    assert drv_a.status_code == 200, drv_a.text
    pkg_a = client_a.get(f"/recommendations/{kpi_a}/package")
    # Tiny 3-period fixture may legitimately abstain (no confident finding);
    # both outcomes prove A's pipeline ran — what matters is B sees neither.
    assert pkg_a.status_code in (200, 422), pkg_a.text
    finding_a = drv_a.json()["findings"][0]["finding_id"]

    # A's own view works
    assert client_a.get("/ingestion/sources").json()["sources"]

    # --- As B: nothing of A is visible --------------------------------------
    client_b = _act_as(USER_B)

    # Lists: B has uploaded nothing — all empty, no trace of A
    assert client_b.get("/ingestion/sources").json()["sources"] == []
    assert client_b.get("/kpi/datasets").json()["datasets"] == []

    # Direct fetches of A's resources -> clean 404s with the standard shape
    for path in (
        f"/profiling/{sid_a}",
        f"/semantic-contract/{sid_a}",
        f"/data-quality/{sid_a}",
        f"/canonical/{ds_a}/preview",
        f"/kpi/dataset/{ds_a}",
        f"/kpi/{kpi_a}/compute",
        f"/anomaly/{kpi_a}",
        f"/drivers/{kpi_a}",
        f"/insights/{kpi_a}",
        f"/recommendations/{kpi_a}/package",
        f"/evidence/{finding_a}",
    ):
        resp = client_b.get(path)
        assert resp.status_code == 404, f"{path} -> {resp.status_code} (leak!)"

    # Every 404 body carries the standard error shape
    body = client_b.get(f"/profiling/{sid_a}").json()
    assert body["error"]["code"] == "not_found"
    assert "not found" in body["error"]["message"].lower()

    # B cannot delete A's dataset or source either
    del_ds = client_b.delete(f"/canonical/{ds_a}")
    assert del_ds.status_code == 404
    del_src = client_b.delete(f"/ingestion/sources/{sid_a}")
    assert del_src.status_code == 404

    # --- As B with their own data: everything works normally -----------------
    sid_b = _upload(client_b, "ads.csv", CSV_B)
    sid_b2 = _upload(client_b, "impressions.csv", CSV_B2)
    pipe_b = _run_pipeline(client_b, [sid_b, sid_b2])
    kpi_b = pipe_b["kpi_id"]
    assert client_b.get(f"/drivers/{kpi_b}").status_code == 200

    # B still sees nothing of A's
    sources_b = client_b.get("/ingestion/sources").json()["sources"]
    assert sorted(s["source_id"] for s in sources_b) == sorted([sid_b, sid_b2])

    # A still sees only their own (override back to A first — one global state)
    _act_as(USER_A)
    sources_a = client_a.get("/ingestion/sources").json()["sources"]
    assert sorted(s["source_id"] for s in sources_a) == sorted([sid_a, sid_a2])
    assert client_a.get(f"/profiling/{sid_b}").status_code == 404

    # Back to B for the feedback/telemetry checks
    _act_as(USER_B)

    # Feedback isolation: A records feedback, B's list stays empty
    _act_as(USER_A)
    fb_a = client_a.post(
        "/feedback",
        json={
            "target_type": "insight",
            "target_id": kpi_a,
            "verdict": "confirm",
            "note": "looks right",
        },
    )
    assert fb_a.status_code == 200, fb_a.text
    _act_as(USER_B)
    assert client_b.get("/feedback/recent").json()["feedback"] == []
    assert client_b.get(f"/feedback/{kpi_a}").json()["feedback"] == []

    # Telemetry isolation: B's llm ledger has no rows from A's activity
    ledger_b = client_b.get("/telemetry/llm-ledger").json()
    assert ledger_b["totals"]["llm_calls"] == 0
    assert ledger_b["last_call"] is None

    app.dependency_overrides.pop(get_current_user, None)


def test_isolation_kpis_drivers_recommendations_lists(real_auth):
    """Explicit coverage for the phase file's named leak vectors."""
    init_db()
    _seed_user(USER_A)
    _seed_user(USER_B)

    client_a = _act_as(USER_A)
    sid_a = _upload(client_a, "sales.csv", CSV_A)
    sid_a2 = _upload(client_a, "bonus.csv", CSV_A2)
    pipe_a = _run_pipeline(client_a, [sid_a, sid_a2])
    ds_a, kpi_a = pipe_a["dataset_id"], pipe_a["kpi_id"]

    client_b = _act_as(USER_B)

    # KPIs list for A's dataset: empty for B
    resp = client_b.get(f"/kpi/dataset/{ds_a}")
    assert resp.status_code == 404  # dataset itself is invisible to B

    # Drivers for A's kpi: 404, not data
    assert client_b.get(f"/drivers/{kpi_a}").status_code == 404

    # Recommendations (LLM route) for A's kpi: 404 before any LLM call
    assert client_b.get(f"/recommendations/{kpi_a}").status_code == 404

    app.dependency_overrides.pop(get_current_user, None)
