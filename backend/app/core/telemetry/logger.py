"""Stage-latency logger: a timing decorator other modules wrap key functions with.

Usage:
    from app.core.telemetry.logger import timed_stage

    @timed_stage("driver analysis")
    def run_drivers(...): ...

Each wrapped call records (stage, latency_ms, recorded_at) into the
stage_timings table, aggregated by /telemetry/summary into per-stage average
latency alongside the existing llm_calls cost data. Pure bookkeeping —
deterministic, no LLM, negligible overhead (one INSERT per call).
"""

import functools
import time
from datetime import datetime, timezone


def _record(stage: str, latency_ms: int, user_id: str = "") -> None:
    """Persist one stage timing row (best-effort: never break the caller)."""
    try:
        from app.db import get_connection, init_db

        init_db()  # idempotent: guarantees stage_timings exists (fresh DBs)
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO stage_timings (stage, user_id, latency_ms, recorded_at) "
                "VALUES (?, ?, ?, ?)",
                (stage, user_id, int(latency_ms), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — telemetry must never break the pipeline
        pass


def timed_stage(stage: str):
    """Decorator: record the wrapped function's wall-clock latency per call.

    Passes through a `user_id` kwarg (when the caller provides one) so each
    timing row is owned by the user whose request caused it.
    """

    def decorator(func):
        import inspect

        accepts_user_id = "user_id" in inspect.signature(func).parameters

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            started = time.perf_counter()
            user_id = kwargs.pop("user_id", "") if not accepts_user_id else kwargs.get("user_id", "")
            try:
                return func(*args, **kwargs)
            finally:
                _record(stage, (time.perf_counter() - started) * 1000.0, user_id)

        return wrapper

    return decorator


def stage_latency_summary(user_id: str = "") -> list:
    """Average + count latency per stage (current user's rows only)."""
    from app.db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT stage, COUNT(*) AS n, AVG(latency_ms) AS avg_ms, "
            "MIN(latency_ms) AS min_ms, MAX(latency_ms) AS max_ms "
            "FROM stage_timings WHERE user_id = ? GROUP BY stage ORDER BY avg_ms DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "stage": r["stage"],
            "calls": int(r["n"]),
            "avg_latency_ms": round(float(r["avg_ms"]), 1),
            "min_latency_ms": int(r["min_ms"]),
            "max_latency_ms": int(r["max_ms"]),
        }
        for r in rows
    ]
