"""History API (Phase 17): the current user's own activity log, newest first."""

from fastapi import APIRouter, Depends

from app.core.auth.security import get_current_user
from app.db import get_connection

router = APIRouter(prefix="/history", tags=["history"], dependencies=[Depends(get_current_user)])


@router.get("")
def get_history(
    action_type: str | None = None,
    target_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
    page: int = 1,
    page_size: int = 25,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """The user's own activity rows, newest first, with filters + pagination.

    Filters: action_type (exact), target_type (exact), since/until (ISO
    timestamps, inclusive bounds on created_at).
    """
    clauses = ["user_id = ?"]
    params: list = [current_user["user_id"]]
    if action_type:
        clauses.append("action_type = ?")
        params.append(action_type)
    if target_type:
        clauses.append("target_type = ?")
        params.append(target_type)
    if since:
        clauses.append("created_at >= ?")
        params.append(since)
    if until:
        clauses.append("created_at <= ?")
        params.append(until)
    where = " AND ".join(clauses)

    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size

    conn = get_connection()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM activity_log WHERE {where}", tuple(params)
        ).fetchone()["n"]
        rows = conn.execute(
            f"SELECT log_id, action_type, target_type, target_id, summary, created_at "
            f"FROM activity_log WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, page_size, offset),
        ).fetchall()
    finally:
        conn.close()

    return {
        "activities": [dict(r) for r in rows],
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "total_pages": max(1, -(-int(total) // page_size)),
    }
