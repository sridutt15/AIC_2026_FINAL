"""Health API — liveness (process) + database connectivity (Phase 12)."""

import time

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.db import engine

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Backend liveness only — no database check (unchanged from Phase 0)."""
    return {"status": "ok"}


@router.get("/health/db")
def health_db() -> dict:
    """Run SELECT 1 against the database; report status + latency."""
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Database temporarily unavailable"
        ) from exc
    latency_ms = round((time.perf_counter() - started) * 1000)
    return {"status": "ok", "latency_ms": latency_ms}
