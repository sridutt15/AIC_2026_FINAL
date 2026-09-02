"""Delete-endpoint tests: cascading deletes for sources and datasets."""

import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_connection, init_db
from app.main import app

from .test_evidence import _build_test_dataset


def _upload_source(client, name="del.csv") -> str:
    csv = (
        "date,region,revenue,order_id\n"
        "2024-01-01,A,100.0,O1\n"
        "2024-01-02,A,110.0,O2\n"
        "2024-01-03,A,100.0,O3\n"
        "2024-01-04,A,120.0,O4\n"
        "2024-01-05,A,110.0,O5\n"
        "2024-01-06,A,125.0,O6\n"
        "2024-01-07,A,100.0,O7\n"
        "2024-01-08,A,130.0,O8\n"
    )
    up = client.post(
        "/ingestion/upload",
        data={"grain": "Daily", "cadence": "Nightly batch"},
        files={"file": (name, io.BytesIO(csv.encode()), "text/csv")},
    )
    assert up.status_code == 200
    source_id = up.json()["source_id"]
    assert client.get(f"/profiling/{source_id}").status_code == 200
    assert client.get(f"/semantic-contract/{source_id}").status_code == 200
    return source_id


def _counts() -> dict:
    conn = get_connection()
    try:
        return {
            t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
            for t in (
                "sources",
                "profiles",
                "semantic_contracts",
                "canonical_datasets",
                "kpis",
                "kpi_computations",
                "anomalies",
                "findings",
                "insights",
                "recommendation_packages",
                "llm_calls",
            )
        }
    finally:
        conn.close()


def test_delete_source_cascades_everything(isolated_env):
    """Deleting a source removes its files, profile/contract/quality rows,
    derived datasets, and all dataset-derived rows."""
    init_db()
    with TestClient(app) as client:
        dataset_id, kpi_id = _build_test_dataset(client)  # builds the full pipeline
        sources = client.get("/ingestion/sources").json()["sources"]
        # _build_test_dataset makes 2 sources; delete the first.
        target = sources[-1]["source_id"]

        # Materialize derived rows that only exist after insight generation.
        assert client.get(f"/drivers/{kpi_id}").status_code == 200
        assert client.get(f"/insights/{kpi_id}").status_code == 200
        before = _counts()
        assert before["sources"] >= 2
        assert before["findings"] > 0
        assert before["insights"] > 0

        # (Phase 16) files lived in Storage; local disk stays empty throughout.
        assert not (Path(settings.UPLOADS_DIR) / "canonical" / f"{dataset_id}.csv").exists()

        deleted = client.delete(f"/ingestion/sources/{target}")
        assert deleted.status_code == 200
        body = deleted.json()
        assert body["deleted"] is True
        assert dataset_id in body["cascaded_datasets"]

        # DB cascade: everything tied to the dataset/KPI is gone.
        after = _counts()
        assert after["canonical_datasets"] == before["canonical_datasets"] - 1
        assert after["kpis"] == 0
        assert after["findings"] == 0
        assert after["insights"] == 0
        assert after["kpi_computations"] == 0

        # (Phase 16) files lived in Storage, not on disk; local stays empty.
        assert not (Path(settings.UPLOADS_DIR) / "canonical" / f"{dataset_id}.csv").exists()

        # The source's profile/contract rows are gone too.
        conn = get_connection()
        try:
            for table in ("profiles", "semantic_contracts", "quality_reports"):
                n = conn.execute(
                    f"SELECT COUNT(*) AS n FROM {table} WHERE source_id = ?",
                    (target,),
                ).fetchone()["n"]
                assert n == 0
        finally:
            conn.close()

        # The dataset endpoints now 404.
        assert client.get(f"/canonical/{dataset_id}/preview").status_code == 404
        # Double delete -> 404 (idempotent on unknown ids).
        assert client.delete(f"/ingestion/sources/{target}").status_code == 404


def test_delete_dataset_keeps_sources(isolated_env):
    """Deleting a canonical dataset cascades its derived rows but keeps the
    raw uploaded sources (they can build other datasets)."""
    init_db()
    with TestClient(app) as client:
        dataset_id, kpi_id = _build_test_dataset(client)
        assert client.get(f"/drivers/{kpi_id}").status_code == 200

        before_sources = len(client.get("/ingestion/sources").json()["sources"])
        csv_path = Path(settings.UPLOADS_DIR) / "canonical" / f"{dataset_id}.csv"

        deleted = client.delete(f"/canonical/{dataset_id}")
        assert deleted.status_code == 200
        assert deleted.json()["cascaded_kpis"], "KPI ids should be listed"

        # Sources untouched.
        assert len(client.get("/ingestion/sources").json()["sources"]) == before_sources
        # Dataset + KPI + derived rows gone; CSV gone.
        assert client.get(f"/canonical/{dataset_id}/preview").status_code == 404
        assert not csv_path.exists()
        after = _counts()
        assert after["kpis"] == 0
        assert after["findings"] == 0

        # Unknown dataset -> 404.
        assert client.delete("/canonical/does-not-exist").status_code == 404


def test_delete_unknown_source_404(isolated_env):
    init_db()
    with TestClient(app) as client:
        assert client.delete("/ingestion/sources/nope").status_code == 404
