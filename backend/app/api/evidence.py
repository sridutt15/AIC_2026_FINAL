"""Evidence API — full evidence record for a finding."""

import json

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_connection
from app.core.auth.security import get_current_user
from app.core.errors import not_found

router = APIRouter(prefix="/evidence", tags=["evidence"], dependencies=[Depends(get_current_user)])


@router.get("/{finding_id}")
def get_evidence(finding_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Return the complete evidence record for a stored finding (owner only)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT finding_id, kpi_id, finding_type, finding_json, evidence_json, created_at "
            "FROM findings WHERE finding_id = ? AND user_id = ?",
            (finding_id, current_user["user_id"]),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise not_found(f"Finding {finding_id}")
    return {
        "finding_id": row["finding_id"],
        "kpi_id": row["kpi_id"],
        "finding_type": row["finding_type"],
        "finding": json.loads(row["finding_json"]),
        "evidence": json.loads(row["evidence_json"]),
        "created_at": row["created_at"],
    }
