"""LLM result cache: stable hash of the structured package -> cached text.

Cost control: before any Gemini call, the recommendation endpoint hashes
the structured package (stable JSON: sorted keys, fixed separators — same
package always hashes identically) plus the persona id, and looks for an
existing llm_calls row with that hash. A hit reuses the stored text and
skips the API call entirely (cached=true).

The cache key intentionally includes ONLY the package and persona — the
prompt is a deterministic function of those two (prompt_templates), so
hashing the package is equivalent to hashing the prompt.
"""

import hashlib
import json


def package_hash(package: dict, persona_id: str | None = None) -> str:
    """Stable SHA-256 of the package + persona (sorted keys, fixed JSON)."""
    canonical = json.dumps(
        {"package": package, "persona_id": persona_id or ""},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def lookup_cached_call(package_hash_value: str, user_id: str = "") -> dict | None:
    """Find the newest llm_calls row for a package hash; None if absent.

    The ORIGINAL live call (cached=0) is the row whose result we reuse; a
    cache-hit row (cached=1) only records that a reuse happened.
    """
    from app.db import get_connection

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT call_id, package_hash, prompt_tokens, completion_tokens, "
            "latency_ms, cost_usd, cached, created_at FROM llm_calls "
            "WHERE package_hash = ? AND cached = 0 AND user_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (package_hash_value, user_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {
        "call_id": row["call_id"],
        "package_hash": row["package_hash"],
        "prompt_tokens": row["prompt_tokens"],
        "completion_tokens": row["completion_tokens"],
        "latency_ms": row["latency_ms"],
        "cost_usd": row["cost_usd"],
        "cached": bool(row["cached"]),
        "created_at": row["created_at"],
    }


def log_llm_call(
    kpi_id: str,
    package_hash_value: str,
    result: dict,
    cached: bool,
    user_id: str = "",
) -> dict:
    """Persist one llm_calls row (a live call or a cache hit) and return it.

    The recommendation text itself is cached by the caller via
    recommendation_packages (see api/recommendations.py) so the llm_calls
    schema stays exactly as the plan specifies.
    """
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.db import get_connection

    call_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO llm_calls "
            "(call_id, kpi_id, user_id, package_hash, prompt_tokens, completion_tokens, "
            "latency_ms, cost_usd, cached, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                call_id,
                kpi_id,
                user_id,
                package_hash_value,
                int(result.get("prompt_tokens") or 0),
                int(result.get("completion_tokens") or 0),
                int(result.get("latency_ms") or 0),
                float(result.get("cost_usd") or 0.0),
                1 if cached else 0,
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "call_id": call_id,
        "kpi_id": kpi_id,
        "package_hash": package_hash_value,
        "prompt_tokens": int(result.get("prompt_tokens") or 0),
        "completion_tokens": int(result.get("completion_tokens") or 0),
        "latency_ms": int(result.get("latency_ms") or 0),
        "cost_usd": float(result.get("cost_usd") or 0.0),
        "cached": cached,
        "created_at": created_at,
    }
