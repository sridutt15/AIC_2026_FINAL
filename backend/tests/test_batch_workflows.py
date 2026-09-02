"""Batch workflow tests: compute-all / run-all endpoints.

Covers: one operation processes every computable KPI, invalid KPIs are
skipped, per-item failures are reported without failing the batch, and a
second user's batch request can't touch someone else's dataset.
"""

import io

from fastapi.testclient import TestClient

from app.core.auth.security import get_current_user
from app.db import get_connection, init_db
from app.main import app

CSV_1 = (
    "date,region,revenue,order_id\n"
    + "".join(
        f"2026-04-{d:02d},{r},{100 + d}.0,O{d}{r}\n"
        for d in range(1, 29)
        for r in ("A", "B")
    )
)
CSV_2 = "date,bonus\n" + "".join(f"2026-04-{d:02d},{d}.0\n" for d in range(1, 29))


def _upload(client, name, content) -> str:
    resp = client.post(
        "/ingestion/upload",
        files={"file": (name, io.BytesIO(content.encode()), "text/csv")},
        data={"grain": "Daily", "cadence": "Nightly batch"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["source_id"]


def _seeded_dataset(client) -> str:
    """Upload + profile + contract + build + discover; returns dataset_id."""
    s1 = _upload(client, "sales.csv", CSV_1)
    s2 = _upload(client, "bonus.csv", CSV_2)
    for sid in (s1, s2):
        assert client.get(f"/profiling/{sid}").status_code == 200
        assert client.get(f"/semantic-contract/{sid}").status_code == 200
    build = client.post(
        "/canonical/build",
        json={"source_ids": [s1, s2], "join_keys": {"date": {"0": "date", "1": "date"}}},
    )
    assert build.status_code == 200, build.text
    ds = build.json()["dataset_id"]
    disc = client.post(f"/kpi/discover/{ds}")
    assert disc.status_code == 200, disc.text
    return ds


def test_compute_all_computes_every_kpi(isolated_env):
    """One batch call computes every discovered KPI — no per-KPI clicking."""
    init_db()
    with TestClient(app) as client:
        ds = _seeded_dataset(client)
        listed = client.get(f"/kpi/dataset/{ds}").json()["kpis"]
        assert listed, "expected discovered KPIs"

        resp = client.post(f"/kpi/compute-all/{ds}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["dataset_id"] == ds
        assert body["failed"] == 0
        assert body["computed"] == len(body["results"])
        assert len(body["results"]) == len(
            [k for k in listed if k["status"] != "invalid"]
        )
        for r in body["results"]:
            assert r["error"] is None
            assert r["computation"] is not None
            assert "trend" in r["computation"]

        # A second batch call reuses the per-KPI cache (all cached now).
        again = client.post(f"/kpi/compute-all/{ds}").json()
        assert all(r["cached"] for r in again["results"])


def test_anomaly_run_all_processes_every_kpi(isolated_env):
    """One batch call detects anomalies for every computable KPI."""
    init_db()
    with TestClient(app) as client:
        ds = _seeded_dataset(client)
        resp = client.post(f"/anomaly/run-all/{ds}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["failed"] == 0
        assert len(body["results"]) > 0
        for r in body["results"]:
            assert r["error"] is None
            assert r["anomalies"] is not None
            assert "change_points" in r["anomalies"]

        # Cached the second time.
        again = client.post(f"/anomaly/run-all/{ds}").json()
        assert all(r["cached"] for r in again["results"])


def test_drivers_run_all_processes_every_kpi(isolated_env):
    """One batch call decomposes every computable KPI."""
    init_db()
    with TestClient(app) as client:
        ds = _seeded_dataset(client)
        resp = client.post(f"/drivers/run-all/{ds}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["failed"] == 0
        assert len(body["results"]) > 0
        for r in body["results"]:
            assert r["error"] is None
            assert r["findings"], "expected driver findings"


def test_batch_isolated_per_user(real_auth):
    """User B's batch call on user A's dataset is a clean 404."""
    init_db()
    users = {
        "user_id": "batch-user-b",
        "email": "batch-b@example.com",
        "full_name": "B",
        "role": "member",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (user_id, email, password_hash, full_name, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (user_id) DO NOTHING",
            (users["user_id"], users["email"], "x", "B", "member", users["created_at"]),
        )
        conn.commit()
    finally:
        conn.close()

    from tests.conftest import TEST_USER

    app.dependency_overrides[get_current_user] = lambda: dict(TEST_USER)
    with TestClient(app) as client:
        ds = _seeded_dataset(client)  # TEST_USER owns this

        app.dependency_overrides[get_current_user] = lambda: dict(users)
        for path in (f"/kpi/compute-all/{ds}", f"/anomaly/run-all/{ds}", f"/drivers/run-all/{ds}"):
            resp = TestClient(app).post(path)
            assert resp.status_code == 404, f"{path} leaked!"
            assert resp.json()["error"]["code"] == "not_found"
    app.dependency_overrides.pop(get_current_user, None)


def test_batch_on_empty_dataset(isolated_env):
    """A dataset with no KPIs returns an empty batch, not an error."""
    init_db()
    with TestClient(app) as client:
        s1 = _upload(client, "sales.csv", CSV_1)
        s2 = _upload(client, "bonus.csv", CSV_2)
        for sid in (s1, s2):
            client.get(f"/profiling/{sid}")
            client.get(f"/semantic-contract/{sid}")
        build = client.post(
            "/canonical/build",
            json={"source_ids": [s1, s2], "join_keys": {"date": {"0": "date", "1": "date"}}},
        )
        ds = build.json()["dataset_id"]  # never discovered

        for path in (f"/kpi/compute-all/{ds}", f"/anomaly/run-all/{ds}", f"/drivers/run-all/{ds}"):
            resp = client.post(path)
            assert resp.status_code == 200
            body = resp.json()
            assert body["results"] == []
            assert body["failed"] == 0
