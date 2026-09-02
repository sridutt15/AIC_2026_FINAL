"""Canonical naming tests (Phase 18): readable auto-names + collision suffix."""

import io

from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

CSV_1 = (
    "date,region,revenue,order_id\n"
    "2026-01-01,A,100.0,O1\n2026-01-02,A,110.0,O2\n2026-01-03,A,120.0,O3\n"
    "2026-01-01,B,50.0,O4\n2026-01-02,B,55.0,O5\n2026-01-03,B,45.0,O6\n"
)
CSV_2 = "date,bonus\n2026-01-01,1.0\n2026-01-02,2.0\n2026-01-03,3.0\n"


def _upload(client, name, content) -> str:
    resp = client.post(
        "/ingestion/upload",
        files={"file": (name, io.BytesIO(content.encode()), "text/csv")},
        data={"grain": "Daily", "cadence": "Nightly batch"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["source_id"]


def _build(client, s1, s2, cadence=None):
    payload = {"source_ids": [s1, s2], "join_keys": {"date": {"0": "date", "1": "date"}}}
    if cadence:
        payload["target_cadence"] = cadence
    resp = client.post("/canonical/build", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_auto_name_is_readable(isolated_env):
    """Building from two named sources produces a readable name, not an ID."""
    init_db()
    with TestClient(app) as client:
        s1 = _upload(client, "sales.csv", CSV_1)
        s2 = _upload(client, "inventory.csv", CSV_2)
        body = _build(client, s1, s2, cadence="daily")

        name = body["name"]
        assert name, "name must be present in the build response"
        assert name == "sales_and_inventory (daily)"
        # The dataset list shows the same name.
        listing = client.get("/kpi/datasets").json()["datasets"]
        entry = next(d for d in listing if d["dataset_id"] == body["dataset_id"])
        assert entry["name"] == name
        # Preview carries it too.
        preview = client.get(f"/canonical/{body['dataset_id']}/preview").json()
        assert preview["name"] == name


def test_second_build_same_inputs_gets_suffix(isolated_env):
    """Rebuilding the same pair collides -> disambiguating ' 2', not an error."""
    init_db()
    with TestClient(app) as client:
        s1 = _upload(client, "sales.csv", CSV_1)
        s2 = _upload(client, "inventory.csv", CSV_2)
        first = _build(client, s1, s2, cadence="daily")
        second = _build(client, s1, s2, cadence="daily")

        assert first["name"] == "sales_and_inventory (daily)"
        assert second["name"] == "sales_and_inventory (daily) 2"
        assert first["dataset_id"] != second["dataset_id"]


def test_rename_via_patch(isolated_env):
    """PATCH renames; the new name persists and is returned everywhere."""
    init_db()
    with TestClient(app) as client:
        s1 = _upload(client, "sales.csv", CSV_1)
        s2 = _upload(client, "inventory.csv", CSV_2)
        body = _build(client, s1, s2)

        patched = client.patch(
            f"/canonical/{body['dataset_id']}", json={"name": "My Q3 view"}
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "My Q3 view"

        listing = client.get("/kpi/datasets").json()["datasets"]
        entry = next(d for d in listing if d["dataset_id"] == body["dataset_id"])
        assert entry["name"] == "My Q3 view"


def test_rename_other_users_dataset_404(real_auth):
    """Renaming someone else's dataset is a clean 404 (isolation intact)."""
    from app.core.auth.security import get_current_user

    init_db()
    with TestClient(app) as client:
        # user A builds
        user_a = {
            "user_id": "name-user-a", "email": "name-a@example.com",
            "full_name": "A", "role": "member", "created_at": "2026-01-01T00:00:00+00:00",
        }
        from app.db import get_connection
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO users (user_id, email, password_hash, full_name, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (user_id) DO NOTHING",
                (user_a["user_id"], user_a["email"], "x", "A", "member", user_a["created_at"]),
            )
            conn.commit()
        finally:
            conn.close()

        app.dependency_overrides[get_current_user] = lambda: dict(user_a)
        s1 = _upload(client, "a.csv", CSV_1)
        s2 = _upload(client, "b.csv", CSV_2)
        built = _build(client, s1, s2)

        # user B tries to rename A's dataset
        user_b = {
            "user_id": "name-user-b", "email": "name-b@example.com",
            "full_name": "B", "role": "member", "created_at": "2026-01-01T00:00:00+00:00",
        }
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO users (user_id, email, password_hash, full_name, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (user_id) DO NOTHING",
                (user_b["user_id"], user_b["email"], "x", "B", "member", user_b["created_at"]),
            )
            conn.commit()
        finally:
            conn.close()
        app.dependency_overrides[get_current_user] = lambda: dict(user_b)

        resp = client.patch(
            f"/canonical/{built['dataset_id']}", json={"name": "stolen"}
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"
        app.dependency_overrides.pop(get_current_user, None)
