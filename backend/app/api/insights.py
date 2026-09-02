"""Insights API — deterministic bulleted insight text for a KPI (Phases 9/18).

GET /insights/{kpi_id}?refresh=
    Runs the driver decomposition (same pipeline as /drivers), picks the top
    non-abstained finding, renders a short bulleted insight via the
    deterministic template generator, and caches it in the insights table.

    refresh=true regenerates (and re-stores) the insight — the output bullets
    are IDENTICAL because the generator is a pure deterministic function; the
    endpoint also returns the previous and current bullets so the UI can
    visually prove byte-for-byte equality.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.drivers import get_drivers
from app.core.activity.logger import log_activity
from app.core.insight_templates.generator import generate_insight_bullets
from app.core.telemetry.logger import timed_stage
from app.db import get_connection
from app.core.auth.security import get_current_user

router = APIRouter(prefix="/insights", tags=["insights"], dependencies=[Depends(get_current_user)])

# Stage-latency telemetry (Phase 11).
get_drivers = timed_stage("insight generation")(get_drivers)


def _previous_insight(kpi_id: str, user_id: str = "") -> list | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT text FROM insights WHERE kpi_id = ? AND user_id = ? "
            "ORDER BY generated_at DESC LIMIT 1",
            (kpi_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    try:
        parsed = json.loads(row["text"])
        if isinstance(parsed, list):
            return parsed
    except (ValueError, TypeError):
        pass
    return [row["text"]]  # legacy pre-Phase-18 paragraph


def _store_insight(insight_id: str, kpi_id: str, bullets: list, user_id: str = "") -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO insights "
            "(insight_id, kpi_id, user_id, persona_id, text, generated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (insight_id, kpi_id, user_id, None, json.dumps(bullets), generated_at),
        )
        conn.commit()
    finally:
        conn.close()
    return generated_at


@router.get("/{kpi_id}")
def get_insight(kpi_id: str, refresh: bool = False, current_user: dict = Depends(get_current_user)) -> dict:
    """Generate (or return cached) deterministic bulleted insight for a KPI."""
    user_id = current_user["user_id"]
    # The drivers endpoint does the full pipeline: decomposition, evidence,
    # confidence. Reuse it so insights never diverge from the findings they
    # describe.
    drivers_response = get_drivers(kpi_id, refresh=refresh, current_user=current_user)
    definition = drivers_response.get("definition") or {}
    kpi_name = definition.get("name") or kpi_id

    findings = [
        f for f in drivers_response.get("findings", [])
        if not (f.get("finding") or {}).get("abstained")
        and (f.get("finding") or {}).get("slices")
    ]
    if not findings:
        raise HTTPException(
            status_code=422,
            detail=(
                "No confident findings for this KPI — insight generation "
                "requires at least one non-abstained driver finding. "
                "Compute the KPI and run drivers first."
            ),
        )

    top = findings[0]
    inner = top["finding"]
    slices = inner["slices"]
    top_slice = slices[0]

    total_movement = inner.get("total_movement") or drivers_response.get("total_movement")
    before = inner.get("before") or {}
    after = inner.get("after") or {}
    before_value = before.get("value")
    after_value = after.get("value")
    magnitude_pct = None
    if before_value not in (None, 0) and after_value is not None:
        magnitude_pct = (after_value - before_value) / abs(before_value)

    # Direction of the KPI movement, not the top slice's direction.
    direction = (
        "up" if (total_movement or 0) > 0
        else ("down" if (total_movement or 0) < 0 else "flat")
    )

    top_driver = {
        "dimension": inner.get("dimension"),
        "slice": top_slice.get("slice"),
        "contribution": top_slice.get("contribution"),
        "share_pct": top_slice.get("share_pct"),
        "direction": top_slice.get("direction"),
    }

    bullets = generate_insight_bullets(
        kpi_name=kpi_name,
        direction=direction,
        magnitude=total_movement,
        magnitude_pct=magnitude_pct,
        top_driver=top_driver,
        confidence=top.get("confidence"),
        before=before,
        after=after,
    )

    # Read the previously stored bullets BEFORE overwriting, so the UI's
    # regenerate diff-check has both outputs.
    previous = _previous_insight(kpi_id, user_id)
    insight_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"insight:{kpi_id}"))
    generated_at = _store_insight(insight_id, kpi_id, bullets, user_id)

    log_activity(
        user_id, "insight_generated", "kpi", kpi_id,
        f"Generated insight for {kpi_name}",
    )
    return {
        "insight_id": insight_id,
        "kpi_id": kpi_id,
        "kpi_name": kpi_name,
        "bullets": bullets,
        "previous_bullets": previous,
        "deterministic": True,
        "confidence": top.get("confidence"),
        "generated_at": generated_at,
    }
