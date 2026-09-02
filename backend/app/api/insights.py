"""Insights API — deterministic persona-specific insight text for a KPI (Phase 9).

GET /insights/{kpi_id}?persona_id=&refresh=
    Runs the driver decomposition (same pipeline as /drivers), picks the top
    non-abstained finding, renders persona-specific insight text via the
    deterministic template generator, and caches it in the insights table.

    refresh=true regenerates (and re-stores) the insight — the output text
    is IDENTICAL because the generator is a pure deterministic function; the
    endpoint also returns the previous and current text so the UI can
    visually prove byte-for-byte equality.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.drivers import get_drivers
from app.core.activity.logger import log_activity
from app.core.insight_templates.generator import generate_insight
from app.core.persona.access_control import filter_for_persona
from app.core.telemetry.logger import timed_stage
from app.db import get_connection
from app.api.integrations import get_persona, contracts_for_dataset
from app.core.auth.security import get_current_user

router = APIRouter(prefix="/insights", tags=["insights"], dependencies=[Depends(get_current_user)])

# Stage-latency telemetry (Phase 11).
get_drivers = timed_stage("insight generation")(get_drivers)


def _persona_name(persona_id: str | None) -> str | None:
    persona = get_persona(persona_id)
    return persona["name"] if persona else None


def _previous_insight(kpi_id: str, persona_id: str | None, user_id: str = "") -> str | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT text FROM insights WHERE kpi_id = ? AND persona_id IS ? AND user_id = ? "
            "ORDER BY generated_at DESC LIMIT 1",
            (kpi_id, persona_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    return row["text"] if row else None


def _store_insight(insight_id: str, kpi_id: str, persona_id: str | None, text: str, user_id: str = "") -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO insights "
            "(insight_id, kpi_id, user_id, persona_id, text, generated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (insight_id, kpi_id, user_id, persona_id, text, generated_at),
        )
        conn.commit()
    finally:
        conn.close()
    return generated_at


@router.get("/{kpi_id}")
def get_insight(kpi_id: str, persona_id: str | None = None, refresh: bool = False, current_user: dict = Depends(get_current_user)) -> dict:
    """Generate (or return cached) deterministic insight text for a KPI."""
    user_id = current_user["user_id"]
    # The drivers endpoint does the full pipeline: decomposition, evidence,
    # confidence, persona filtering. Reuse it so insights never diverge from
    # the findings they describe.
    drivers_response = get_drivers(kpi_id, refresh=refresh, persona_id=persona_id, current_user=current_user)
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

    # Persona-filter the slice payload again for the top driver detail
    # (Category Manager sees full detail; CFO sees none).
    persona = get_persona(persona_id)
    top_driver = None
    show_detail = not persona or (persona_id == "category_manager")
    if show_detail:
        top_driver = {
            "dimension": inner.get("dimension"),
            "slice": top_slice.get("slice"),
            "contribution": top_slice.get("contribution"),
            "share_pct": top_slice.get("share_pct"),
            "direction": top_slice.get("direction"),
        }

    text = generate_insight(
        kpi_name=kpi_name,
        direction=direction,
        magnitude=total_movement,
        persona_id=persona_id,
        magnitude_pct=magnitude_pct,
        top_driver=top_driver,
        confidence=top.get("confidence"),
        before=before,
        after=after,
    )

    # Read the previously stored text BEFORE overwriting, so the UI's
    # regenerate diff-check has both outputs.
    previous = _previous_insight(kpi_id, persona_id, user_id)
    insight_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"insight:{kpi_id}:{persona_id or 'default'}")
    )
    generated_at = _store_insight(insight_id, kpi_id, persona_id, text, user_id)

    log_activity(
        user_id, "insight_generated", "kpi", kpi_id,
        f"Generated insight for {kpi_name}",
    )
    return {
        "insight_id": insight_id,
        "kpi_id": kpi_id,
        "kpi_name": kpi_name,
        "persona_id": persona_id,
        "persona_name": _persona_name(persona_id),
        "text": text,
        "previous_text": previous,
        "deterministic": True,
        "confidence": top.get("confidence"),
        "generated_at": generated_at,
    }
