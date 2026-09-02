"""Data-quality API — GET a deterministic quality report for a source (cached after first run)."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.profiling import load_source_dataframe
from app.core.quality.report_builder import build_quality_report
from app.db import get_connection
from app.core.auth.security import get_current_user
from app.core.errors import AppError, not_found

router = APIRouter(prefix="/data-quality", tags=["data-quality"], dependencies=[Depends(get_current_user)])


def _load_profile_json(source_id: str, user_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT profile_json FROM profiles WHERE source_id = ? AND user_id = ?",
            (source_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    return json.loads(row["profile_json"]) if row else None


@router.get("/{source_id}")
def get_quality_report(source_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Build the quality report on first call; return the stored one afterwards."""
    user_id = current_user["user_id"]
    conn = get_connection()
    try:
        cached = conn.execute(
            "SELECT report_json, created_at FROM quality_reports "
            "WHERE source_id = ? AND user_id = ?",
            (source_id, user_id),
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

    # Prerequisites: source exists (ownership gate) + profile + contract.
    conn = get_connection()
    try:
        source = conn.execute(
            "SELECT source_id, filename, grain, cadence, uploaded_at FROM sources "
            "WHERE source_id = ? AND user_id = ?",
            (source_id, user_id),
        ).fetchone()
        contract_row = conn.execute(
            "SELECT contract_json FROM semantic_contracts "
            "WHERE source_id = ? AND user_id = ?",
            (source_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    if source is None:
        raise not_found(f"Source {source_id}")
    if contract_row is None:
        raise HTTPException(
            status_code=409,
            detail=f"No semantic contract for source {source_id} — create one first.",
        )

    # Ownership verified — safe to touch Supabase Storage now.
    try:
        df = load_source_dataframe(dict(source), user_id)
    except (HTTPException, AppError):
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load file: {exc}") from exc

    contract = json.loads(contract_row["contract_json"])
    profile = _load_profile_json(source_id, user_id)

    report = build_quality_report(df, contract, profile)
    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO quality_reports (source_id, user_id, report_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (source_id, user_id, json.dumps(report), created_at),
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
