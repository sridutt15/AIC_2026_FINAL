"""Data-quality API — GET a deterministic quality report for a source (cached after first run)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.core.ingestion.loaders import load_source
from app.core.quality.report_builder import build_quality_report
from app.db import get_connection
from app.core.auth.security import get_current_user

router = APIRouter(prefix="/data-quality", tags=["data-quality"], dependencies=[Depends(get_current_user)])


def _load_df(source_id: str):
    """Load the raw dataframe for a source from its uploads folder."""
    uploads_dir = Path(settings.UPLOADS_DIR) / source_id
    files = sorted(uploads_dir.glob("source.*"))
    if not files:
        raise HTTPException(status_code=404, detail=f"No raw file found for source {source_id}.")
    ext = files[0].suffix.lower().lstrip(".")
    try:
        return load_source(files[0], ext)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load file: {exc}") from exc


def _load_profile_json(source_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT profile_json FROM profiles WHERE source_id = ?", (source_id,)
        ).fetchone()
    finally:
        conn.close()
    return json.loads(row["profile_json"]) if row else None


@router.get("/{source_id}")
def get_quality_report(source_id: str) -> dict:
    """Build the quality report on first call; return the stored one afterwards."""
    conn = get_connection()
    try:
        cached = conn.execute(
            "SELECT report_json, created_at FROM quality_reports WHERE source_id = ?",
            (source_id,),
        ).fetchone()
    finally:
        conn.close()
    if cached is not None:
        return {
            "source_id": source_id,
            "cached": True,
            "created_at": cached["created_at"],
            "report": json.loads(cached["report_json"]),
        }

    # Prerequisites: source exists, profile exists, contract exists.
    conn = get_connection()
    try:
        source = conn.execute(
            "SELECT source_id, filename FROM sources WHERE source_id = ?", (source_id,)
        ).fetchone()
        contract_row = conn.execute(
            "SELECT contract_json FROM semantic_contracts WHERE source_id = ?",
            (source_id,),
        ).fetchone()
    finally:
        conn.close()
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found.")
    if contract_row is None:
        raise HTTPException(
            status_code=409,
            detail=f"No semantic contract for source {source_id} — create one first.",
        )

    df = _load_df(source_id)
    contract = json.loads(contract_row["contract_json"])
    profile = _load_profile_json(source_id)

    report = build_quality_report(df, contract, profile)
    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO quality_reports (source_id, report_json, created_at) VALUES (?, ?, ?)",
            (source_id, json.dumps(report), created_at),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "source_id": source_id,
        "cached": False,
        "created_at": created_at,
        "report": report,
    }
