"""Profiling API — deterministic column profile for an uploaded source."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.ingestion import source_file_path
from app.config import settings
from app.core.ingestion.loaders import load_source
from app.core.profiling.profiler import profile_dataframe
from app.core.storage import supabase_client as storage
from app.db import get_connection
from app.core.auth.security import get_current_user
from app.core.errors import AppError, not_found

router = APIRouter(prefix="/profiling", tags=["profiling"], dependencies=[Depends(get_current_user)])


def _get_source(source_id: str, user_id: str) -> dict:
    """Ownership check FIRST — before any storage call."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT source_id, filename, grain, cadence, uploaded_at FROM sources "
            "WHERE source_id = ? AND user_id = ?",
            (source_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise not_found(f"Source {source_id}")
    return dict(row)


def load_source_dataframe(source: dict, user_id: str):
    """Download the source's raw file from Storage and parse it.

    Call only AFTER the ownership check (the service-role key can read any
    path — the database check is the gate). Uses a temp file because the
    Phase 1 loaders take filesystem paths. A missing Storage object raises
    a clean not_found (e.g. pre-Phase-16 uploads never migrated to Storage).
    """
    import tempfile
    from pathlib import Path

    path = source_file_path(user_id, source["source_id"], source["filename"])
    try:
        file_bytes = storage.download_file(path)
    except HTTPException:
        raise
    except Exception as exc:
        raise not_found(
            f"Raw file for source {source['source_id']}"
        ) from exc
    ext = source["filename"].rsplit(".", 1)[-1].lower()
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_name = Path(tmp.name)
    try:
        return load_source(tmp_name, ext)
    finally:
        tmp_name.unlink(missing_ok=True)


@router.get("/{source_id}")
def get_profile(source_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Load the source's raw file, run profile_dataframe, cache and return it.

    Returns the cached result if this source was already profiled.
    """
    user_id = current_user["user_id"]
    source = _get_source(source_id, user_id)  # ownership gate first

    conn = get_connection()
    try:
        cached = conn.execute(
            "SELECT profile_json, created_at FROM profiles "
            "WHERE source_id = ? AND user_id = ?",
            (source_id, user_id),
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

    try:
        df = load_source_dataframe(source, user_id)
    except (HTTPException, AppError):
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load file: {exc}") from exc

    profile = profile_dataframe(df)
    profile_json = json.dumps(profile)
    created_at = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO profiles (source_id, user_id, profile_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (source_id, user_id, profile_json, created_at),
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
