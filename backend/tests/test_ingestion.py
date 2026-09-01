"""Ingestion API tests: upload a synthetic CSV, verify DB row and on-disk file."""

import io

from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_connection, init_db
from app.main import app

CSV_CONTENT = (
    "transaction_id,transaction_date,customer_segment,revenue,units\n"
    "T001,2024-01-05,Consumer,120.50,3\n"
    "T002,2024-01-06,Enterprise,8300.00,42\n"
    "T003,2024-01-07,Consumer,45.99,1\n"
)


def _client() -> TestClient:
    with TestClient(app) as client:  # context manager triggers lifespan -> init_db()
        yield client


def test_upload_creates_source_row_and_file(isolated_env):
    init_db()
    client = next(_client())

    response = client.post(
        "/ingestion/upload",
        data={"grain": "Transactional", "cadence": "Nightly batch"},
        files={"file": ("transactions.csv", io.BytesIO(CSV_CONTENT.encode()), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "transactions.csv"
    assert body["grain"] == "Transactional"
    assert body["cadence"] == "Nightly batch"
    source_id = body["source_id"]
    assert source_id  # non-empty UUID string

    # Raw file saved under data/uploads/{source_id}/
    saved = list((settings.UPLOADS_DIR / source_id).glob("source.*"))
    assert len(saved) == 1
    assert saved[0].suffix == ".csv"
    assert saved[0].read_bytes() == CSV_CONTENT.encode()

    # Row appears in sources table
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT filename, grain, cadence FROM sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row == ("transactions.csv", "Transactional", "Nightly batch")


def test_upload_rejects_unsupported_extension(isolated_env):
    init_db()
    client = next(_client())

    response = client.post(
        "/ingestion/upload",
        data={"grain": "Daily", "cadence": "Nightly batch"},
        files={"file": ("data.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["error"]["message"]


def test_list_sources_returns_uploaded(isolated_env):
    init_db()
    client = next(_client())

    client.post(
        "/ingestion/upload",
        data={"grain": "Daily", "cadence": "Weekly"},
        files={"file": ("a.csv", io.BytesIO(CSV_CONTENT.encode()), "text/csv")},
    )
    response = client.get("/ingestion/sources")
    assert response.status_code == 200
    sources = response.json()["sources"]
    assert len(sources) == 1
    assert sources[0]["filename"] == "a.csv"
    assert sources[0]["grain"] == "Daily"
    assert sources[0]["cadence"] == "Weekly"
    assert sources[0]["uploaded_at"]
