"""Feedback store: record analyst verdicts; adjust materiality weights.

The loop (documented, deterministic):
    1. Analysts leave verdicts on insights/recommendations: "confirm"
       (right), "correct" (partially right), "reject" (wrong).
    2. Feedback rows carry the target's driver type (inferred from the
       target id / stored finding). apply_feedback_adjustments() counts
       repeated "reject" verdicts per driver type.
    3. Each driver type's weight multiplier is nudged DOWN deterministically:
           multiplier = max(0.25, 1.0 - 0.15 * reject_count)
       i.e. the first reject costs 15% of the driver type's materiality
       weight, with a floor of 0.25x. "confirm" verdicts restore weight at
       half that rate (+0.075 each, capped at 1.0). "correct" is neutral.
    4. The multiplier is persisted in driver_weight_adjustments and read by
       materiality.score_materiality — a small persisted config, NOT an LLM
       prompt and NOT in-memory state, so adjustments survive restarts and
       are auditable in the DB.

No LLM, no randomness: the same feedback history always yields the same
multipliers.
"""

from datetime import datetime, timezone
from uuid import uuid4

VERDICTS = ("confirm", "correct", "reject")

REJECT_STEP = 0.15
CONFIRM_STEP = 0.075
MIN_MULTIPLIER = 0.25
MAX_MULTIPLIER = 1.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_feedback(
    target_type: str,
    target_id: str,
    verdict: str,
    note: str | None = None,
    driver_type: str | None = None,
    user_id: str = "",
) -> dict:
    """Store one feedback row. target_type: 'insight' | 'recommendation'.

    verdict: 'confirm' | 'correct' | 'reject'. driver_type (optional) is the
    lever-library driver type the target's finding belongs to; when omitted
    it is inferred from the target id's stored finding dimension, falling
    back to 'other'.
    """
    if target_type not in ("insight", "recommendation"):
        raise ValueError("target_type must be 'insight' or 'recommendation'")
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")

    if driver_type is None:
        driver_type = infer_driver_type_for_target(target_id, user_id)

    from app.db import get_connection

    feedback_id = str(uuid4())
    created_at = _now()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO feedback (feedback_id, user_id, target_type, target_id, verdict, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (feedback_id, user_id, target_type, target_id, verdict, note, created_at),
        )
        # Persist the resolved driver type so apply_feedback_adjustments()
        # never has to re-infer it (deterministic + auditable).
        conn.execute(
            "INSERT INTO feedback_meta (feedback_id, driver_type, created_at) "
            "VALUES (?, ?, ?)",
            (feedback_id, driver_type, created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "feedback_id": feedback_id,
        "target_type": target_type,
        "target_id": target_id,
        "verdict": verdict,
        "note": note,
        "driver_type": driver_type,
        "created_at": created_at,
    }


def get_feedback(target_id: str, user_id: str = "") -> list:
    """All feedback rows for a target (current user's only), newest first."""
    from app.db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT feedback_id, target_type, target_id, verdict, note, created_at "
            "FROM feedback WHERE target_id = ? AND user_id = ? "
            "ORDER BY created_at DESC",
            (target_id, user_id),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def recent_feedback(limit: int = 20, user_id: str = "") -> list:
    """Most recent feedback rows for the current user, across all their targets."""
    from app.db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT feedback_id, target_type, target_id, verdict, note, created_at "
            "FROM feedback WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, int(limit)),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def infer_driver_type_for_target(target_id: str, user_id: str = "") -> str:
    """Infer the driver type for a feedback target from its stored finding.

    Insight/recommendation targets are KPI-scoped: look up the KPI's stored
    driver findings and use the first finding's dimension; fall back to
    'other'. Deterministic.
    """
    from app.core.recommendation.lever_library import driver_type_for_dimension
    from app.db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT finding_json FROM findings WHERE kpi_id = ? AND user_id = ? "
            "ORDER BY created_at DESC LIMIT 5",
            (target_id, user_id),
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        try:
            import json

            finding = json.loads(row["finding_json"])
            dimension = finding.get("dimension")
            if dimension:
                return driver_type_for_dimension(dimension)
        except (ValueError, TypeError):
            continue
    return "other"


def apply_feedback_adjustments(user_id: str = "") -> dict:
    """Recompute per-driver-type weight multipliers from the feedback history.

    Deterministic rule (see module docstring):
        multiplier = clamp(1.0 - REJECT_STEP*rejects + CONFIRM_STEP*confirms,
                           MIN_MULTIPLIER, MAX_MULTIPLIER)
    Persists each multiplier in driver_weight_adjustments and returns the
    full mapping {driver_type: multiplier} plus per-type counts.
    """
    from app.db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT f.verdict AS verdict, m.driver_type AS driver_type "
            "FROM feedback f LEFT JOIN feedback_meta m ON f.feedback_id = m.feedback_id "
            "WHERE f.user_id = ? ORDER BY f.created_at ASC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    counts: dict = {}
    for row in rows:
        # Driver type was resolved at record time and stored in
        # feedback_meta; fall back to 'other' for legacy rows.
        driver_type = row["driver_type"] or "other"
        verdict = row["verdict"]
        tally = counts.setdefault(driver_type, {"reject": 0, "confirm": 0, "correct": 0})
        if verdict in tally:
            tally[verdict] += 1

    adjustments = {}
    for driver_type, tally in sorted(counts.items()):
        raw = (
            1.0
            - REJECT_STEP * tally["reject"]
            + CONFIRM_STEP * tally["confirm"]
        )
        multiplier = round(min(max(raw, MIN_MULTIPLIER), MAX_MULTIPLIER), 4)
        adjustments[driver_type] = multiplier

        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO driver_weight_adjustments "
                "(driver_type, multiplier, updated_at) VALUES (?, ?, ?)",
                (driver_type, multiplier, _now()),
            )
            conn.commit()
        finally:
            conn.close()

    return {"adjustments": adjustments, "counts": counts}


def get_driver_multiplier(driver_type: str) -> float:
    """Current materiality-weight multiplier for a driver type (default 1.0)."""
    from app.db import get_connection

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT multiplier FROM driver_weight_adjustments WHERE driver_type = ?",
            (driver_type,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return 1.0
    return float(row["multiplier"])
