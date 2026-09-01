"""Telemetry API — LLM ledger (Phase 10) + full cost/latency summary (Phase 11).

GET /telemetry/llm-ledger
    Static, documented table listing every architecture stage and whether
    that stage uses an LLM, plus the last llm_calls row and running totals.

GET /telemetry/summary
    Aggregated operations view: average latency per stage (stage_timings),
    total LLM calls, total prompt/completion tokens, total estimated cost,
    and the cache hit rate from llm_calls. Real logged data, no placeholders.
"""

from fastapi import APIRouter, Depends

from app.core.feedback.store import apply_feedback_adjustments
from app.core.telemetry.logger import stage_latency_summary
from app.db import get_connection
from app.core.auth.security import get_current_user

router = APIRouter(prefix="/telemetry", tags=["telemetry"], dependencies=[Depends(get_current_user)])

# The stage ledger: (stage, llm_used). Order mirrors the pipeline.
STAGE_LEDGER = [
    {"stage": "ingestion", "llm_used": False},
    {"stage": "profiling", "llm_used": False},
    {"stage": "semantic contract", "llm_used": False},
    {"stage": "data quality", "llm_used": False},
    {"stage": "canonical model", "llm_used": False},
    {"stage": "KPI discovery", "llm_used": False},
    {"stage": "KPI validation", "llm_used": False},
    {"stage": "KPI computation", "llm_used": False},
    {"stage": "materiality", "llm_used": False},
    {"stage": "anomaly detection", "llm_used": False},
    {"stage": "driver analysis", "llm_used": False},
    {"stage": "evidence", "llm_used": False},
    {"stage": "confidence", "llm_used": False},
    {"stage": "insight generation", "llm_used": False},
    {"stage": "recommendation packaging", "llm_used": False},
    {"stage": "LLM recommendation", "llm_used": True},
]


@router.get("/llm-ledger")
def llm_ledger() -> dict:
    """The documented stage-by-stage LLM usage table + last call metadata."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT call_id, kpi_id, prompt_tokens, completion_tokens, "
            "latency_ms, cost_usd, cached, created_at FROM llm_calls "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        n_calls = conn.execute("SELECT COUNT(*) AS n FROM llm_calls").fetchone()["n"]
        total_cost = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) AS c FROM llm_calls"
        ).fetchone()["c"]
    finally:
        conn.close()

    last_call = None
    if row is not None:
        last_call = {
            "call_id": row["call_id"],
            "kpi_id": row["kpi_id"],
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "latency_ms": row["latency_ms"],
            "cost_usd": row["cost_usd"],
            "cached": bool(row["cached"]),
            "created_at": row["created_at"],
        }

    return {
        "stages": STAGE_LEDGER,
        "summary": {
            "total_stages": len(STAGE_LEDGER),
            "llm_stages": sum(1 for s in STAGE_LEDGER if s["llm_used"]),
            "deterministic_stages": sum(1 for s in STAGE_LEDGER if not s["llm_used"]),
        },
        "last_call": last_call,
        "totals": {"llm_calls": n_calls, "cost_usd": round(float(total_cost), 6)},
    }


@router.get("/summary")
def telemetry_summary() -> dict:
    """Aggregated operations telemetry: latency, LLM usage, cost, cache rate.

    All numbers come from the llm_calls + stage_timings tables (real logged
    data). Cache hit rate = cached rows / total rows over llm_calls.
    """
    conn = get_connection()
    try:
        agg = conn.execute(
            "SELECT COUNT(*) AS n, "
            "COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens, "
            "COALESCE(SUM(completion_tokens), 0) AS completion_tokens, "
            "COALESCE(SUM(cost_usd), 0.0) AS cost_usd, "
            "COALESCE(SUM(CASE WHEN cached = 1 THEN 1 ELSE 0 END), 0) AS cached_n, "
            "COALESCE(AVG(latency_ms), 0.0) AS avg_latency_ms "
            "FROM llm_calls"
        ).fetchone()
        llm_calls_over_time = conn.execute(
            "SELECT created_at, prompt_tokens, completion_tokens, cost_usd, cached "
            "FROM llm_calls ORDER BY created_at ASC"
        ).fetchall()
    finally:
        conn.close()

    n_calls = int(agg["n"])
    cached_n = int(agg["cached_n"])
    cache_hit_rate = round(cached_n / n_calls, 4) if n_calls else 0.0

    return {
        "stage_latencies": stage_latency_summary(),
        "llm": {
            "total_calls": n_calls,
            "total_prompt_tokens": int(agg["prompt_tokens"]),
            "total_completion_tokens": int(agg["completion_tokens"]),
            "total_cost_usd": round(float(agg["cost_usd"]), 6),
            "avg_latency_ms": round(float(agg["avg_latency_ms"]), 1),
            "cached_calls": cached_n,
            "cache_hit_rate": cache_hit_rate,
        },
        "llm_calls_over_time": [
            {
                "created_at": r["created_at"],
                "prompt_tokens": r["prompt_tokens"],
                "completion_tokens": r["completion_tokens"],
                "cost_usd": r["cost_usd"],
                "cached": bool(r["cached"]),
            }
            for r in llm_calls_over_time
        ],
        "feedback_adjustments": apply_feedback_adjustments()["adjustments"],
    }
