"""Ingestion API — upload a raw source file, list, and delete uploaded sources."""

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.config import settings
from app.db import get_connection
from app.core.auth.security import get_current_user

router = APIRouter(prefix="/ingestion", tags=["ingestion"], dependencies=[Depends(get_current_user)])


def _extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        raise HTTPException(status_code=400, detail="Filename must have an extension.")
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in ("csv", "xlsx", "xls", "json"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")
    return ext


@router.post("/upload")
def upload_source(
    file: UploadFile = File(...), grain: str = Form(...), cadence: str = Form(...)
) -> dict:
    """Save the raw file under data/uploads/{source_id}/ and record it in `sources`."""
    ext = _extension(file.filename)
    source_id = str(uuid.uuid4())
    dest_dir = settings.UPLOADS_DIR / source_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"source.{ext}"

    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    dest.write_bytes(content)

    uploaded_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO sources (source_id, filename, grain, cadence, uploaded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_id, file.filename, grain, cadence, uploaded_at),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "source_id": source_id,
        "filename": file.filename,
        "grain": grain,
        "cadence": cadence,
    }


@router.get("/sources")
def list_sources() -> dict:
    """List all uploaded sources, newest first, with derived-dataset counts.

    derived_dataset_count: how many canonical datasets were built (at least
    partly) from this source — shown in the UI's delete confirmation.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT source_id, filename, grain, cadence, uploaded_at "
            "FROM sources ORDER BY uploaded_at DESC"
        ).fetchall()
        dataset_rows = conn.execute(
            "SELECT source_ids FROM canonical_datasets"
        ).fetchall()
    finally:
        conn.close()

    usage: dict = {}
    for row in dataset_rows:
        try:
            for sid in json.loads(row["source_ids"]):
                usage[sid] = usage.get(sid, 0) + 1
        except ValueError:
            continue

    return {
        "sources": [
            {**dict(row), "derived_dataset_count": usage.get(row["source_id"], 0)}
            for row in rows
        ]
    }


def _dataset_ids_for_source(source_id: str) -> list:
    """Canonical dataset ids whose source_ids JSON list contains source_id."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT dataset_id, source_ids FROM canonical_datasets"
        ).fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        try:
            if source_id in json.loads(row["source_ids"]):
                out.append(row["dataset_id"])
        except ValueError:
            continue
    return out


def _delete_dataset_rows(dataset_id: str, conn) -> None:
    """Delete every derived row for a canonical dataset (same transaction)."""
    kpi_ids = [
        r["kpi_id"]
        for r in conn.execute(
            "SELECT kpi_id FROM kpis WHERE dataset_id = ?", (dataset_id,)
        ).fetchall()
    ]
    for kpi_id in kpi_ids:
        for table in (
            "kpi_computations",
            "anomalies",
            "findings",
            "insights",
            "recommendation_packages",
            "llm_calls",
        ):
            conn.execute(f"DELETE FROM {table} WHERE kpi_id = ?", (kpi_id,))
    conn.execute("DELETE FROM kpis WHERE dataset_id = ?", (dataset_id,))
    conn.execute("DELETE FROM canonical_datasets WHERE dataset_id = ?", (dataset_id,))


@router.delete("/sources/{source_id}")
def delete_source(source_id: str) -> dict:
    """Delete an uploaded source and everything derived from it.

    Cascade: the raw uploaded file folder, this source's profile/contract/
    quality report, and any canonical dataset built from this source (with
    the dataset's own cascade: KPIs, computations, anomalies, findings,
    insights, recommendation packages, LLM call ledger rows, and the
    canonical CSV on disk). Idempotent: 200 even if some pieces are already
    gone; 404 only when the source was never uploaded.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT source_id, filename FROM sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Source {source_id} not found.")

        dataset_ids = _dataset_ids_for_source(source_id)
        for dataset_id in dataset_ids:
            _delete_dataset_rows(dataset_id, conn)
            # Canonical CSV on disk.
            csv_path = Path(settings.UPLOADS_DIR) / "canonical" / f"{dataset_id}.csv"
            if csv_path.exists():
                csv_path.unlink()

        for table in ("profiles", "semantic_contracts", "quality_reports", "sources"):
            conn.execute(f"DELETE FROM {table} WHERE source_id = ?", (source_id,))
        conn.commit()
    finally:
        conn.close()

    # Raw uploaded file folder (after the DB commit — file cleanup is
    # best-effort and idempotent).
    uploads_dir = Path(settings.UPLOADS_DIR) / source_id
    if uploads_dir.exists():
        shutil.rmtree(uploads_dir, ignore_errors=True)

    return {
        "deleted": True,
        "source_id": source_id,
        "cascaded_datasets": dataset_ids,
    }
