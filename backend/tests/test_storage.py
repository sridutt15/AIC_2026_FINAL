"""Storage tests (Phase 16): uploads land at {user_id}/{source_id}/ in the bucket.

Uses the conftest local-storage redirect (same interface as the real
Supabase wrapper), so the suite never touches the real bucket.
"""

import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TEST_USER

CSV = "date,revenue\n2026-01-01,100.0\n2026-01-02,110.0\n"


def _bucket_dir() -> Path:
    """The per-test local bucket the conftest redirected storage to."""
    return TEST_USER and Path(str(Path("data/uploads").resolve()))


def test_upload_writes_to_user_prefixed_storage_path(isolated_env, tmp_path):
    """The ingestion endpoint stores bytes at {user_id}/{source_id}/{filename}."""
    bucket = tmp_path / "bucket"
    with TestClient(app) as client:
        resp = client.post(
            "/ingestion/upload",
            files={"file": ("sales.csv", io.BytesIO(CSV.encode()), "text/csv")},
            data={"grain": "Daily", "cadence": "Nightly batch"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    expected = bucket / TEST_USER["user_id"] / body["source_id"] / "sales.csv"
    assert expected.exists(), f"missing {expected}"
    assert expected.read_bytes() == CSV.encode()
    # No sibling files (only the one upload)
    assert len(list((bucket / TEST_USER["user_id"] / body["source_id"]).iterdir())) == 1


def test_uploaded_file_can_be_read_back_for_profiling(isolated_env, tmp_path):
    """Profiling downloads the bytes from Storage (round-trip)."""
    from app.db import init_db

    init_db()
    bucket = tmp_path / "bucket"
    with TestClient(app) as client:
        up = client.post(
            "/ingestion/upload",
            files={"file": ("sales.csv", io.BytesIO(CSV.encode()), "text/csv")},
            data={"grain": "Daily", "cadence": "Nightly batch"},
        )
        assert up.status_code == 200, up.text
        sid = up.json()["source_id"]

        profile = client.get(f"/profiling/{sid}")
        assert profile.status_code == 200, profile.text
        assert profile.json()["source_id"] == sid
        # The file the profiler read is exactly what was uploaded
        expected = bucket / TEST_USER["user_id"] / sid / "sales.csv"
        assert expected.read_bytes() == CSV.encode()
