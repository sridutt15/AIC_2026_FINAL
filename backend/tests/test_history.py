"""History tests (Phase 17): tracked actions produce exact row counts, per-user."""

import io

from fastapi.testclient import TestClient

from app.main import app
from app.core.auth.security import get_current_user
from app.db import get_connection, init_db

CSV_A = (
    "date,region,revenue,order_id\n"
    "2026-01-01,A,100.0,O1\n2026-01-02,A,110.0,O2\n2026-01-03,A,120.0,O3\n"
    "2026-01-01,B,50.0,O4\n2026-01-02,B,55.0,O5\n2026-01-03,B,45.0,O6\n"
)
CSV_A2 = "date,bonus\n2026-01-01,1.0\n2026-01-02,2.0\n2026-01-03,3.0\n"

USER_A = {
    "user_id": "hist-user-a",
    "email": "hist-a@example.com",
    "full_name": "A",
    "role": "member",
    "created_at": "2026-01-01T00:00:00+00:00",
}
USER_B = {
    "user_id": "hist-user-b",
    "email": "hist-b@example.com",
    "full_name": "B",
    "role": "member",
    "created_at": "2026-01-01T00:00:00+00:00",
}


def _seed_user(user: dict) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (user_id, email, password_hash, full_name, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (user_id) DO NOTHING",
            (user["user_id"], user["email"], "x", user["full_name"], user["role"], user["created_at"]),
        )
        conn.commit()
    finally:
        conn.close()


def _act_as(user: dict) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: dict(user)
    return TestClient(app)


def _upload(client, name, content) -> str:
    resp = client.post(
        "/ingestion/upload",
        files={"file": (name, io.BytesIO(content.encode()), "text/csv")},
        data={"grain": "Daily", "cadence": "Nightly batch"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["source_id"]


def test_tracked_actions_produce_exact_activity_rows(real_auth):
    """A known number of tracked actions -> exactly that many rows for A."""
    init_db()
    _seed_user(USER_A)
    _seed_user(USER_B)

    client_a = _act_as(USER_A)
    s1 = _upload(client_a, "sales.csv", CSV_A)          # 1: upload
    s2 = _upload(client_a, "bonus.csv", CSV_A2)         # 2: upload
    for sid in (s1, s2):
        assert client_a.get(f"/profiling/{sid}").status_code == 200
        assert client_a.get(f"/semantic-contract/{sid}").status_code == 200
    build = client_a.post(
        "/canonical/build",
        json={"source_ids": [s1, s2], "join_keys": {"date": {"0": "date", "1": "date"}}},
    )
    assert build.status_code == 200, build.text
    ds = build.json()["dataset_id"]
    disc = client_a.post(f"/kpi/discover/{ds}")          # 3: kpi_discovery
    assert disc.status_code == 200, disc.text
    kpi = disc.json()["kpis"][0]["kpi_id"]
    assert client_a.get(f"/kpi/{kpi}/compute").status_code == 200
    assert client_a.get(f"/anomaly/{kpi}").status_code == 200
    drv = client_a.get(f"/drivers/{kpi}")                # 4: driver_analysis
    assert drv.status_code == 200, drv.text
    insight_resp = client_a.get(f"/insights/{kpi}")     # 5: insight_generated (may abstain)
    insight_ok = insight_resp.status_code == 200
    fb = client_a.post(                                   # 6: feedback_submitted
        "/feedback",
        json={"target_type": "insight", "target_id": kpi, "verdict": "confirm"},
    )
    assert fb.status_code == 200, fb.text

    history = client_a.get("/history").json()
    # Always-logged: 2 uploads + 1 kpi_discovery + 2 driver_analysis (direct +
    # inside insights) + 1 feedback = 6. When the fixture yields confident
    # findings, +1 insight_generated and drivers ran once more = 8.
    expected = 8 if insight_ok else 6
    assert history["total"] == expected, (history["total"], expected, history)

    # Filters work
    uploads_only = client_a.get("/history?action_type=upload").json()
    assert uploads_only["total"] == 2
    assert all(a["action_type"] == "upload" for a in uploads_only["activities"])

    # B sees none of A's history
    client_b = _act_as(USER_B)
    hb = client_b.get("/history").json()
    assert hb["total"] == 0
    assert hb["activities"] == []

    app.dependency_overrides.pop(get_current_user, None)


def test_history_requires_auth(real_auth):
    """GET /history without a token -> 401 token_missing."""
    init_db()
    client = TestClient(app)
    resp = client.get("/history")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_missing"
