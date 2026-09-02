"""Recommendations API — Phase 10 (Phase 18: bulleted output, no personas).

GET /recommendations/{kpi_id}/package
    Phase 9: builds/returns the structured package only — deterministic,
    no LLM. Kept intact for the Insights page and tests.

GET /recommendations/{kpi_id}
    Phase 10: fetches/builds the structured package (Phase 9 logic), checks
    the llm_calls cache by package hash, calls Gemini ONLY on a miss, logs
    every call (tokens, latency, estimated cost) to llm_calls, and returns
    {recommendation_bullets, package, llm_call_metadata}. The LLM sees only
    the structured package fields — never raw data.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.drivers import get_drivers
from app.config import settings
from app.core.activity.logger import log_activity
from app.core.llm.cache import log_llm_call, lookup_cached_call, package_hash
from app.core.llm.client import call_llm
from app.core.llm.prompt_templates import build_prompt
from app.core.recommendation.lever_library import lever_library
from app.core.recommendation.package_builder import build_package
from app.core.telemetry.logger import timed_stage
from app.db import get_connection
from app.core.auth.security import get_current_user

router = APIRouter(prefix="/recommendations", tags=["recommendations"], dependencies=[Depends(get_current_user)])

# Stage-latency telemetry (Phase 11).
call_llm = timed_stage("LLM recommendation")(call_llm)


def _parse_bullets(text: str) -> list:
    """Split an LLM bulleted response into a list of clean strings.

    Accepts '- ' / '* ' / numbered bullets and plain lines; empty lines and
    stray markers are dropped. Non-bulleted legacy text becomes a
    single-element list so the UI always renders a list.
    """
    bullets = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("-*•").strip()
        if len(line) > 2 and line[0].isdigit() and line[1:2] in (".", ")"):
            line = line[2:].strip()
        if line:
            bullets.append(line)
    return bullets or [text.strip()]


def _store_package(package_id: str, kpi_id: str, package: dict, user_id: str = "") -> str:
    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO recommendation_packages "
            "(package_id, kpi_id, user_id, package_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (package_id, kpi_id, user_id, json.dumps(package, sort_keys=True), created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return created_at


def _load_stored_texts(kpi_id: str, user_id: str = "") -> dict:
    """{package_hash: recommendation_bullets} cached for this KPI.

    The llm_calls table holds the cost ledger (schema per plan); the actual
    recommendation bullets are cached alongside the package in
    recommendation_packages as {"hash": text} entries under a fixed id.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT package_json FROM recommendation_packages "
            "WHERE kpi_id = ? AND package_id = ? AND user_id = ?",
            (kpi_id, f"texts:{kpi_id}", user_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {}
    try:
        return json.loads(row["package_json"])
    except (ValueError, TypeError):
        return {}


def _store_texts(kpi_id: str, texts: dict, user_id: str = "") -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO recommendation_packages "
            "(package_id, kpi_id, user_id, package_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"texts:{kpi_id}", kpi_id, user_id, json.dumps(texts), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _build_structured_package(kpi_id: str, current_user: dict = None) -> dict:
    """Phase 9 logic: top non-abstained finding -> seven-field package."""
    drivers_response = get_drivers(kpi_id, refresh=False, current_user=current_user)

    findings = [
        f for f in drivers_response.get("findings", [])
        if not (f.get("finding") or {}).get("abstained")
        and (f.get("finding") or {}).get("slices")
    ]
    if not findings:
        raise HTTPException(
            status_code=422,
            detail=(
                "No confident findings for this KPI — a recommendation "
                "requires at least one non-abstained driver finding."
            ),
        )

    top = findings[0]
    try:
        return build_package(
            top["finding"], top.get("evidence") or {}, top.get("confidence"), lever_library
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{kpi_id}/package")
def get_recommendation_package(kpi_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Build the structured recommendation package (deterministic, no LLM)."""
    user_id = current_user["user_id"]
    package = _build_structured_package(kpi_id, current_user)

    package_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"package:{kpi_id}"))
    created_at = _store_package(package_id, kpi_id, package, user_id)

    return {
        "package_id": package_id,
        "kpi_id": kpi_id,
        "package": package,
        "created_at": created_at,
        "llm_call": False,
    }


@router.get("/{kpi_id}")
def get_recommendation(kpi_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """LLM-phrased bulleted recommendation from the structured package.

    The ONLY endpoint that calls an LLM. Cache-first: an identical package
    (same hash) reuses the stored bullets with no API call. Every call —
    live or cached — is logged to llm_calls with tokens/latency/cost.
    """
    user_id = current_user["user_id"]
    package = _build_structured_package(kpi_id, current_user)
    _store_package(
        str(uuid.uuid5(uuid.NAMESPACE_URL, f"package:{kpi_id}")), kpi_id, package, user_id
    )

    hash_value = package_hash(package)
    texts = _load_stored_texts(kpi_id, user_id)
    cached_row = lookup_cached_call(hash_value, user_id)

    if cached_row is not None and hash_value in texts:
        metadata = log_llm_call(kpi_id, hash_value, cached_row, cached=True, user_id=user_id)
        return {
            "kpi_id": kpi_id,
            "recommendation_bullets": _parse_bullets(texts[hash_value]),
            "package": package,
            "llm_call_metadata": {**metadata, "model": settings.GEMINI_MODEL},
        }

    prompt = build_prompt(package)
    try:
        result = call_llm(prompt)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    metadata = log_llm_call(kpi_id, hash_value, result, cached=False, user_id=user_id)
    texts[hash_value] = result["text"]
    _store_texts(kpi_id, texts, user_id)

    log_activity(
        user_id, "recommendation_generated", "kpi", kpi_id,
        "Generated an LLM recommendation",
    )
    return {
        "kpi_id": kpi_id,
        "recommendation_bullets": _parse_bullets(result["text"]),
        "package": package,
        "llm_call_metadata": {**metadata, "model": result.get("model", settings.GEMINI_MODEL)},
    }
