"""Persona API — list the seeded personas for the navbar persona switcher."""

import json

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_connection
from app.core.auth.security import get_current_user

router = APIRouter(prefix="/personas", tags=["personas"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_personas() -> dict:
    """List all personas with their access rules (for the UI switcher)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT persona_id, name, access_json FROM personas ORDER BY persona_id"
        ).fetchall()
    finally:
        conn.close()
    return {
        "personas": [
            {
                "persona_id": r["persona_id"],
                "name": r["name"],
                "access": json.loads(r["access_json"]) if r["access_json"] else {},
            }
            for r in rows
        ]
    }


def get_persona(persona_id: str | None) -> dict | None:
    """Fetch one persona row by id; None for empty/unknown ids (no restriction).

    Unknown persona ids raise 404 so callers can't silently bypass filtering
    by passing a bogus id.
    """
    if not persona_id:
        return None
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT persona_id, name, access_json FROM personas WHERE persona_id = ?",
            (persona_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Persona '{persona_id}' not found."
        )
    return {
        "persona_id": row["persona_id"],
        "name": row["name"],
        "access_json": row["access_json"],
    }
