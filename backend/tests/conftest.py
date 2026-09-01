"""Shared fixtures: per-test isolation via a dedicated Postgres schema.

Each test runs inside its own schema in the Supabase Postgres database
(created, then dropped, around the test), so the full Phases 0-11 suite
regresses against the real Postgres engine while tests remain isolated —
exact-count assertions hold because no other test has ever written to that
schema. Uploaded files still go to a temp dir on disk.

Phase 14: every route except /auth/* and /health* now requires a logged-in
user. The Phase 0-13 API tests were written before auth existed, so this
conftest overrides get_current_user with a stubbed test user — the tests
stay byte-identical while the real dependency keeps working in production.
"""

import re
import uuid
from pathlib import Path

import pytest

from app.config import settings
from app.db import _initialized_schemas, engine, init_db, use_schema


class _TestAuthUser(dict):
    """Marker: the stubbed user get_current_user resolves to under tests."""


TEST_USER = _TestAuthUser(
    {
        "user_id": "test-user-0000",
        "email": "test@example.com",
        "full_name": "Test User",
        "role": "member",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
)


@pytest.fixture()
def isolated_env(tmp_path: Path):
    """Point the app at an isolated per-test Postgres schema + temp uploads."""
    schema = "test_" + re.sub(r"[^0-9a-z]", "_", uuid.uuid4().hex)[:12]

    original_uploads = settings.UPLOADS_DIR
    settings.UPLOADS_DIR = tmp_path / "uploads"
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    use_schema(schema)
    _initialized_schemas.discard(schema)

    # Override the auth dependency so pre-auth tests keep passing unchanged.
    from app.core.auth import security
    from app.main import app

    app.dependency_overrides[security.get_current_user] = lambda: dict(TEST_USER)

    try:
        yield tmp_path
    finally:
        settings.UPLOADS_DIR = original_uploads
        use_schema("public")
        app.dependency_overrides.pop(security.get_current_user, None)
        # Drop the per-test schema; failures here must not mask test errors.
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                conn.commit()
        except Exception:
            pass


@pytest.fixture()
def real_auth(isolated_env):
    """isolated_env WITHOUT the get_current_user override: tests of real
    token enforcement (test_token_errors, test_auth) pop the override so
    routes run the genuine auth dependency against the per-test schema."""
    from app.core.auth import security
    from app.main import app

    saved = app.dependency_overrides.pop(security.get_current_user, None)
    try:
        yield isolated_env
    finally:
        if saved is not None:
            app.dependency_overrides[security.get_current_user] = saved
