"""Activity logger (Phase 17): one row per completed user action.

Called by endpoint handlers right after the action succeeds. Best-effort:
a logging failure must never break the action it describes.
"""

import uuid
from datetime import datetime, timezone


def log_activity(
    user_id: str,
    action_type: str,
    target_type: str,
    target_id: str,
    summary: str,
) -> None:
    """Insert one activity_log row (never raises — telemetry-grade)."""
    try:
        from app.db import get_connection

        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO activity_log "
                "(log_id, user_id, action_type, target_type, target_id, summary, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    user_id,
                    action_type,
                    target_type,
                    target_id,
                    summary,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — activity logging is best-effort
        pass
