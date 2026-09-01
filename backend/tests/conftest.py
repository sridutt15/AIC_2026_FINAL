"""Shared fixtures: per-test isolation via a dedicated Postgres schema.

Each test runs inside its own schema in the Supabase Postgres database
(created, then dropped, around the test), so the full Phases 0–11 suite
regresses against the real Postgres engine while tests remain isolated —
exact-count assertions hold because no other test has ever written to that
schema. Uploaded files still go to a temp dir on disk.
"""

import re
import uuid
from pathlib import Path

import pytest

from app.config import settings
from app.db import _initialized_schemas, engine, use_schema


@pytest.fixture()
def isolated_env(tmp_path: Path):
    """Point the app at an isolated per-test Postgres schema + temp uploads."""
    schema = "test_" + re.sub(r"[^0-9a-z]", "_", uuid.uuid4().hex)[:12]

    original_uploads = settings.UPLOADS_DIR
    settings.UPLOADS_DIR = tmp_path / "uploads"
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    use_schema(schema)
    _initialized_schemas.discard(schema)

    try:
        yield tmp_path
    finally:
        settings.UPLOADS_DIR = original_uploads
        use_schema("public")
        # Drop the per-test schema; failures here must not mask test errors.
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                conn.commit()
        except Exception:
            pass
