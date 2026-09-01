"""Profiling API — deterministic column profile for an uploaded source."""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.core.ingestion.loaders import load_source
from app.core.profiling.profiler import profile_dataframe
from app.db import get_connection

router = APIRouter(prefix="/profiling", tags=["profiling"])


def _get_source(source_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT source_id, filename, grain, cadence, uploaded_at FROM sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found.")
    return dict(row)


@router.get("/{source_id}")
def get_profile(source_id: str) -> dict:
    """Load the source's raw file, run profile_dataframe, cache and return it.

    Returns the cached result if this source was already profiled.
    """
    source = _get_source(source_id)

    conn = get_connection()
    try:
        cached = conn.execute(
            "SELECT profile_json, created_at FROM profiles WHERE source_id = ?",
            (source_id,),
        ).fetchone()
    finally:
        conn.close()
    if cached is not None:
        return {
            "source_id": source_id,
            "source": source,
            "created_at": cached["created_at"],
            "cached": True,
            "profile": json.loads(cached["profile_json"]),
        }

    uploads_dir = Path(settings.UPLOADS_DIR) / source_id
    files = sorted(uploads_dir.glob("source.*"))
    if not files:
        raise HTTPException(status_code=404, detail=f"No raw file found for source {source_id}.")
    ext = files[0].suffix.lower().lstrip(".")
    try:
        df = load_source(files[0], ext)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load file: {exc}") from exc

    profile = profile_dataframe(df)
    profile_json = json.dumps(profile)
    created_at = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO profiles (source_id, profile_json, created_at) VALUES (?, ?, ?)",
            (source_id, profile_json, created_at),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "source_id": source_id,
        "source": source,
        "created_at": created_at,
        "cached": False,
        "profile": profile,
    }
