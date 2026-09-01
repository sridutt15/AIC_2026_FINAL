"""Evidence API — full evidence record for a finding."""

import json

from fastapi import APIRouter, HTTPException

from app.db import get_connection

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/{finding_id}")
def get_evidence(finding_id: str) -> dict:
    """Return the complete evidence record for a stored finding."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT finding_id, kpi_id, finding_type, finding_json, evidence_json, created_at "
            "FROM findings WHERE finding_id = ?",
            (finding_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found.")
    return {
        "finding_id": row["finding_id"],
        "kpi_id": row["kpi_id"],
        "finding_type": row["finding_type"],
        "finding": json.loads(row["finding_json"]),
        "evidence": json.loads(row["evidence_json"]),
        "created_at": row["created_at"],
    }
