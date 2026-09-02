"""Storage isolation tests (Phase 16): the DB ownership check gates Storage access.

B attempting to reach A's source must fail on the database ownership check
BEFORE any storage call happens — even knowing A's exact source_id.
Patches the api modules' storage aliases with a recording fake.
"""

import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.core.auth.security import get_current_user

CSV_A = "date,revenue\n2026-01-01,100.0\n2026-01-02,110.0\n"

USER_A = {
    "user_id": "storage-user-a",
    "email": "storage-a@example.com",
    "full_name": "A",
    "role": "member",
    "created_at": "2026-01-01T00:00:00+00:00",
}
USER_B = {
    "user_id": "storage-user-b",
    "email": "storage-b@example.com",
    "full_name": "B",
    "role": "member",
    "created_at": "2026-01-01T00:00:00+00:00",
}

STORE = Path("/tmp/p16_isolation_store")


def _seed_user(user: dict) -> None:
    from app.db import get_connection

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


class _Recorder:
    """Records storage calls; download is forbidden (the test's whole point)."""

    calls: list = []

    @staticmethod
    def upload_file(path, file_bytes, content_type):
        _Recorder.calls.append(("upload", path))
        target = STORE / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_bytes)

    @staticmethod
    def download_file(path):
        _Recorder.calls.append(("download", path))
        raise AssertionError(f"storage read attempted for {path}")

    @staticmethod
    def delete_file(path):
        _Recorder.calls.append(("remove", path))


def _install_recorder():
    import app.api.canonical_model as canonical_api
    import app.api.ingestion as ingestion_api
    import app.api.profiling as profiling_api

    mods = (ingestion_api, canonical_api, profiling_api)
    originals = [m.storage for m in mods]
    for m in mods:
        m.storage = _Recorder
    _Recorder.calls = []
    return mods, originals


def _restore(mods, originals):
    for m, original in zip(mods, originals):
        m.storage = original


def test_no_storage_call_when_not_owner(real_auth):
    """B's profiling request for A's source: 404 with ZERO storage touches."""
    from app.db import init_db

    init_db()
    _seed_user(USER_A)
    _seed_user(USER_B)

    mods, originals = _install_recorder()
    try:
        # A uploads (storage allowed for A)
        app.dependency_overrides[get_current_user] = lambda: dict(USER_A)
        with TestClient(app) as client:
            up = client.post(
                "/ingestion/upload",
                files={"file": ("a.csv", io.BytesIO(CSV_A.encode()), "text/csv")},
                data={"grain": "Daily", "cadence": "x"},
            )
            assert up.status_code == 200, up.text
            sid_a = up.json()["source_id"]

        n_calls_as_a = len(_Recorder.calls)
        assert n_calls_as_a == 1  # exactly A's own upload

        # B (knowing A's exact source_id) tries profiling -> blocked pre-storage
        app.dependency_overrides[get_current_user] = lambda: dict(USER_B)
        with TestClient(app) as client:
            resp = client.get(f"/profiling/{sid_a}")

        assert resp.status_code == 404, resp.text
        assert resp.json()["error"]["code"] == "not_found"
        # No additional storage calls happened during B's rejected request
        assert len(_Recorder.calls) == n_calls_as_a, (
            f"storage was touched during B's rejected request: {_Recorder.calls}"
        )
    finally:
        _restore(mods, originals)
    app.dependency_overrides.pop(get_current_user, None)


def test_data_quality_also_gated_by_db_check(real_auth):
    """B's data-quality request for A's source: 404, zero storage calls."""
    from app.db import init_db

    init_db()
    _seed_user(USER_A)
    _seed_user(USER_B)

    mods, originals = _install_recorder()
    try:
        app.dependency_overrides[get_current_user] = lambda: dict(USER_A)
        with TestClient(app) as client:
            up = client.post(
                "/ingestion/upload",
                files={"file": ("a.csv", io.BytesIO(CSV_A.encode()), "text/csv")},
                data={"grain": "Daily", "cadence": "x"},
            )
            sid_a = up.json()["source_id"]
            # A profiles + contracts so A's own quality path would be ready
            client.get(f"/profiling/{sid_a}")
            client.get(f"/semantic-contract/{sid_a}")

        before = len(_Recorder.calls)

        app.dependency_overrides[get_current_user] = lambda: dict(USER_B)
        with TestClient(app) as client:
            resp = client.get(f"/data-quality/{sid_a}")

        assert resp.status_code == 404
        assert len(_Recorder.calls) == before
    finally:
        _restore(mods, originals)
    app.dependency_overrides.pop(get_current_user, None)
