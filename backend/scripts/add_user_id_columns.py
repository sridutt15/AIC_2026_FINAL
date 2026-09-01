"""One-off Phase 15 migration: add user_id to the 13 owned tables.

Run ONCE against the Supabase database:
    venv/bin/python -m scripts.add_user_id_columns

Adds `user_id TEXT REFERENCES users(user_id)` to each owned table (source
through feedback). Idempotent: skips columns that already exist. personas,
refresh_tokens, users, driver_weight_adjustments, and feedback_meta are
intentionally untouched (shared / auth-owned / global config).

Optional flags:
    --assign legacy-data    create (or reuse) a placeholder user and point
                            every existing NULL user_id row at it
    --clear                 DELETE all pre-existing rows from the owned
                            tables instead (fresh start)
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from app.config import settings  # noqa: E402

OWNED_TABLES = [
    "sources",
    "profiles",
    "semantic_contracts",
    "quality_reports",
    "canonical_datasets",
    "kpis",
    "kpi_computations",
    "anomalies",
    "findings",
    "insights",
    "recommendation_packages",
    "llm_calls",
    "feedback",
    "stage_timings",
]

LEGACY_EMAIL = "legacy-data@localhost"
LEGACY_USER_ID = "00000000-0000-4000-8000-000000000001"


def main() -> None:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    inspector = inspect(engine)

    with engine.begin() as conn:
        for table in OWNED_TABLES:
            cols = {c["name"] for c in inspector.get_columns(table)}
            if "user_id" in cols:
                print(f"  {table}: user_id already exists, skipped")
                continue
            conn.execute(
                text(
                    f'ALTER TABLE "{table}" '
                    "ADD COLUMN user_id TEXT REFERENCES users(user_id)"
                )
            )
            print(f"  {table}: added user_id")

    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--assign":
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (user_id, email, password_hash, full_name, role, created_at) "
                    "VALUES (:u, :e, :p, :n, :r, :c) ON CONFLICT (email) DO NOTHING"
                ),
                {
                    "u": LEGACY_USER_ID,
                    "e": LEGACY_EMAIL,
                    "p": "!",
                    "n": "Legacy data",
                    "r": "member",
                    "c": datetime.now(timezone.utc).isoformat(),
                },
            )
            for table in OWNED_TABLES:
                conn.execute(
                    text(f'UPDATE "{table}" SET user_id = :u WHERE user_id IS NULL'),
                    {"u": LEGACY_USER_ID},
                )
            print(f"\nExisting rows assigned to {LEGACY_EMAIL} ({LEGACY_USER_ID})")
    elif mode == "--clear":
        with engine.begin() as conn:
            # children first, then parents
            for table in reversed(OWNED_TABLES):
                conn.execute(text(f'DELETE FROM "{table}"'))
            print("\nOwned tables cleared — every user starts fresh")
    else:
        print("\nNo data mode given — existing rows keep user_id NULL")
        print("usage: add_user_id_columns.py [--assign | --clear]")

    print("done.")


if __name__ == "__main__":
    main()
