"""Storage-reference tests (Phase 19): single-source datasets don't duplicate bytes.

Single-source build: the dataset row references the ORIGINAL upload's path —
no new object under canonical/. Multi-source merge: a genuinely new derived
CSV is still written, exactly as before.
"""

import io
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import get_connection, init_db
from app.main import app
from tests.conftest import TEST_USER

CSV_1 = (
    "date,region,revenue,order_id\n"
    + "".join(
        f"2026-01-{d:02d},{r},{100 + d}.0,O{d}{r}\n"
        for d in range(1, 29)
        for r in ("A", "B")
    )
)
CSV_2 = "date,bonus\n" + "".join(f"2026-01-{d:02d},{d}.0\n" for d in range(1, 29))


def _upload(client, name, content) -> str:
    resp = client.post(
        "/ingestion/upload",
        files={"file": (name, io.BytesIO(content.encode()), "text/csv")},
        data={"grain": "Daily", "cadence": "Nightly batch"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["source_id"]


def _prep(client, sid):
    assert client.get(f"/profiling/{sid}").status_code == 200
    assert client.get(f"/semantic-contract/{sid}").status_code == 200


def _config_for(dataset_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT join_config_json FROM canonical_datasets WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchone()
    finally:
        conn.close()
    return json.loads(row["join_config_json"])


def test_single_source_references_original_upload(isolated_env, tmp_path):
    """Dataset points at the source's existing object; canonical/ stays empty."""
    init_db()
    bucket = tmp_path / "bucket"
    with TestClient(app) as client:
        s1 = _upload(client, "sales.csv", CSV_1)
        _prep(client, s1)
        build = client.post("/canonical/build", json={"source_ids": [s1]}).json()

        config = _config_for(build["dataset_id"])
        expected = f"{TEST_USER['user_id']}/{s1}/sales.csv"
        assert config["storage_path"] == expected

        # The referenced object exists (the original upload)…
        assert (bucket / expected).exists()
        # …and NO duplicate was written under canonical/.
        canonical_dir = bucket / TEST_USER["user_id"] / "canonical"
        assert not canonical_dir.exists() or not any(canonical_dir.iterdir()), (
            "single-source build must not write a duplicate canonical file"
        )


def test_multi_source_merge_still_writes_new_file(isolated_env, tmp_path):
    """2+ merge keeps the copy-on-build behavior: a new derived CSV appears."""
    init_db()
    bucket = tmp_path / "bucket"
    with TestClient(app) as client:
        s1 = _upload(client, "sales.csv", CSV_1)
        s2 = _upload(client, "bonus.csv", CSV_2)
        _prep(client, s1)
        _prep(client, s2)
        build = client.post(
            "/canonical/build",
            json={"source_ids": [s1, s2], "join_keys": {"date": {"0": "date", "1": "date"}}},
        ).json()

        config = _config_for(build["dataset_id"])
        expected = f"{TEST_USER['user_id']}/canonical/{build['dataset_id']}.csv"
        assert config["storage_path"] == expected
        assert (bucket / expected).exists(), "merged dataset must write its derived CSV"


def test_delete_single_source_dataset_keeps_original_upload(isolated_env, tmp_path):
    """Deleting the dataset must NOT delete the referenced original file."""
    init_db()
    bucket = tmp_path / "bucket"
    with TestClient(app) as client:
        s1 = _upload(client, "sales.csv", CSV_1)
        _prep(client, s1)
        build = client.post("/canonical/build", json={"source_ids": [s1]}).json()

        original = bucket / f"{TEST_USER['user_id']}/{s1}/sales.csv"
        assert original.exists()

        deleted = client.delete(f"/canonical/{build['dataset_id']}")
        assert deleted.status_code == 200
        # The upload survives dataset deletion — it belongs to the source.
        assert original.exists(), "deleting the dataset deleted the source's file!"


def test_delete_source_cascades_single_source_dataset(isolated_env):
    """Deleting the SOURCE removes its single-source dataset (and its reference)."""
    init_db()
    with TestClient(app) as client:
        s1 = _upload(client, "sales.csv", CSV_1)
        _prep(client, s1)
        build = client.post("/canonical/build", json={"source_ids": [s1]}).json()

        deleted = client.delete(f"/ingestion/sources/{s1}")
        assert deleted.status_code == 200

        preview = client.get(f"/canonical/{build['dataset_id']}/preview")
        assert preview.status_code == 404, "source delete must cascade its dataset"
