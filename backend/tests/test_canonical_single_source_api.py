"""Single-source canonical build API tests (Phase 19).

POST /canonical/build with exactly one source_id and no join_keys succeeds,
stores a storage REFERENCE to the original upload (no duplicate write), and
produces a sensible non-merge-implying name.
"""

import io

from fastapi.testclient import TestClient

from app.db import get_connection, init_db
from app.main import app

from .test_evidence import _build_test_dataset  # noqa: F401 (fixture reuse)

CSV = (
    "date,region,revenue,order_id\n"
    "2026-01-01,A,100.0,O1\n2026-01-02,A,110.0,O2\n2026-01-03,A,120.0,O3\n"
    "2026-01-01,B,50.0,O4\n2026-01-02,B,55.0,O5\n2026-01-03,B,45.0,O6\n"
)


def _upload(client, name="sales_data.csv", content=CSV) -> str:
    resp = client.post(
        "/ingestion/upload",
        files={"file": (name, io.BytesIO(content.encode()), "text/csv")},
        data={"grain": "Daily", "cadence": "Nightly batch"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["source_id"]


def _login_env():
    init_db()


def test_single_source_build_without_join_keys(isolated_env):
    """One source, no join_keys -> success + preview matches the raw source."""
    _login_env()
    with TestClient(app) as client:
        s1 = _upload(client)
        assert client.get(f"/profiling/{s1}").status_code == 200
        assert client.get(f"/semantic-contract/{s1}").status_code == 200

        build = client.post("/canonical/build", json={"source_ids": [s1]})
        assert build.status_code == 200, build.text
        body = build.json()

        # Sensible non-merge-implying name: source stem + cadence, no "_and_".
        assert body["name"] == "sales_data"
        assert "_and_" not in body["name"]

        # Preview rows == the source's raw data (unmodified).
        preview = client.get(f"/canonical/{body['dataset_id']}/preview").json()
        assert preview["row_count"] == 6
        assert preview["columns"] == ["date", "region", "revenue", "order_id"]
        values = sorted(r["revenue"] for r in preview["preview"])
        assert values == [45.0, 50.0, 55.0, 100.0, 110.0, 120.0]


def test_single_source_build_with_cadence_name(isolated_env):
    """A declared target cadence shows in the name: 'sales_data (daily)'."""
    _login_env()
    with TestClient(app) as client:
        s1 = _upload(client)
        client.get(f"/profiling/{s1}")
        client.get(f"/semantic-contract/{s1}")
        build = client.post(
            "/canonical/build",
            json={"source_ids": [s1], "target_cadence": "daily"},
        )
        assert build.status_code == 200
        assert build.json()["name"] == "sales_data (daily)"


def test_multi_source_still_requires_join_keys(isolated_env):
    """The 2+ merge path is unchanged: join_keys still required there."""
    _login_env()
    with TestClient(app) as client:
        s1 = _upload(client, "a.csv")
        s2 = _upload(client, "b.csv", "date,bonus\n2026-01-01,1.0\n2026-01-02,2.0\n2026-01-03,3.0\n")
        for s in (s1, s2):
            client.get(f"/profiling/{s}")
            client.get(f"/semantic-contract/{s}")
        resp = client.post("/canonical/build", json={"source_ids": [s1, s2]})
        assert resp.status_code == 422
        assert "join_keys" in resp.json()["error"]["message"]


def test_single_source_storage_reference(isolated_env):
    """The dataset row's stored path points at the ORIGINAL upload — and no
    duplicate object appears under canonical/ (conftest's local store is
    the same dir either way)."""
    _login_env()
    with TestClient(app) as client:
        s1 = _upload(client)
        client.get(f"/profiling/{s1}")
        client.get(f"/semantic-contract/{s1}")
        build = client.post("/canonical/build", json={"source_ids": [s1]}).json()
        dataset_id = build["dataset_id"]

        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT join_config_json FROM canonical_datasets WHERE dataset_id = ?",
                (dataset_id,),
            ).fetchone()
        finally:
            conn.close()
        import json as _json

        config = _json.loads(row["join_config_json"])
        assert config["storage_path"] == f"test-user-0000/{s1}/sales_data.csv"
        assert "/canonical/" not in config["storage_path"]
