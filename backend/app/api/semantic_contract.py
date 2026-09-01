"""Semantic contract API — GET (build if missing) and PUT (user-edited overwrite)."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.semantic.contract_builder import build_contract
from app.db import get_connection
from app.core.auth.security import get_current_user
from app.core.errors import not_found

router = APIRouter(prefix="/semantic-contract", tags=["semantic-contract"], dependencies=[Depends(get_current_user)])

# Fields every contract must carry so downstream phases can rely on them.
_REQUIRED_FIELDS = (
    "kpi_definitions",
    "hierarchies",
    "calendar",
    "thresholds",
    "access_tags",
)


def _get_profile_row(source_id: str, user_id: str):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT profile_json FROM profiles WHERE source_id = ? AND user_id = ?",
            (source_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def _get_source_row(source_id: str, user_id: str):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT source_id, filename, grain, cadence FROM sources "
            "WHERE source_id = ? AND user_id = ?",
            (source_id, user_id),
        ).fetchone()
    finally:
        conn.close()


class ContractIn(BaseModel):
    """Full edited contract JSON submitted by the user via PUT."""

    contract: dict


@router.get("/{source_id}")
def get_contract(source_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Return the stored contract, or build one from the stored profile if none exists."""
    user_id = current_user["user_id"]
    if _get_source_row(source_id, user_id) is None:
        raise not_found(f"Source {source_id}")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT contract_json, updated_at FROM semantic_contracts "
            "WHERE source_id = ? AND user_id = ?",
            (source_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    if row is not None:
        return {
            "source_id": source_id,
            "contract": json.loads(row["contract_json"]),
            "updated_at": row["updated_at"],
            "built": False,
        }

    profile_row = _get_profile_row(source_id, user_id)
    if profile_row is None:
        raise HTTPException(
            status_code=409,
            detail=f"Source {source_id} has not been profiled yet — profile it first.",
        )

    source = _get_source_row(source_id, user_id)
    contract = build_contract(json.loads(profile_row["profile_json"]), grain=source["grain"])
    updated_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO semantic_contracts (source_id, user_id, contract_json, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (source_id, user_id, json.dumps(contract), updated_at),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "source_id": source_id,
        "contract": contract,
        "updated_at": updated_at,
        "built": True,
    }


@router.put("/{source_id}")
def put_contract(source_id: str, payload: ContractIn, current_user: dict = Depends(get_current_user)) -> dict:
    """Overwrite the stored contract with the user's edited version."""
    user_id = current_user["user_id"]
    if _get_source_row(source_id, user_id) is None:
        raise not_found(f"Source {source_id}")

    contract = payload.contract
    missing = [f for f in _REQUIRED_FIELDS if f not in contract]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Contract is missing required fields: {', '.join(missing)}",
        )

    updated_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO semantic_contracts (source_id, user_id, contract_json, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(source_id) DO UPDATE SET contract_json = excluded.contract_json, "
            "updated_at = excluded.updated_at",
            (source_id, user_id, json.dumps(contract), updated_at),
        )
        conn.commit()
    finally:
        conn.close()
    return {"source_id": source_id, "updated_at": updated_at, "saved": True}
