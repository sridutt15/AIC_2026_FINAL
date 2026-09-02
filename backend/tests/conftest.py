"""Shared fixtures: per-test isolation via a dedicated Postgres schema.

Each test runs inside its own schema in the Supabase Postgres database
(created, then dropped, around the test), so the full Phases 0-11 suite
regresses against the real Postgres engine while tests remain isolated —
exact-count assertions hold because no other test has ever written to that
schema.

Phase 14: every route except /auth/* and /health* now requires a logged-in
user. The Phase 0-13 API tests were written before auth existed, so this
conftest overrides get_current_user with a stubbed test user — the tests
stay byte-identical while the real dependency keeps working in production.

Phase 16: uploads go to Supabase Storage in production; under pytest the
storage wrapper is pointed at a per-test local dir so the suite never
touches the real bucket.
"""

import re
import uuid
from pathlib import Path

import pytest

from app.config import settings
from app.db import _initialized_schemas, engine, get_connection, init_db, use_schema


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
    """Isolated per-test Postgres schema + temp uploads + local storage."""
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

    # The stub user must exist as a real row (user_id FK on owned tables).
    init_db()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (user_id, email, password_hash, full_name, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (user_id) DO NOTHING",
            (
                TEST_USER["user_id"],
                TEST_USER["email"],
                "not-a-real-hash",
                TEST_USER["full_name"],
                TEST_USER["role"],
                TEST_USER["created_at"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    # Phase 16: redirect the storage wrappers to a per-test local dir so the
    # suite never reads/writes the real Supabase Storage bucket. The api
    # modules hold `from ... import supabase_client as storage`, so patching
    # the `storage` alias on each gives them the local implementation.
    import app.api.canonical_model as canonical_api
    import app.api.ingestion as ingestion_api
    import app.api.profiling as profiling_api
    import app.core.storage.supabase_client as storage_mod

    store_dir = tmp_path / "bucket"
    store_dir.mkdir()

    class _LocalStorage:
        """Same functions as supabase_client, backed by a temp dir.

        upload_file accepts (and ignores) compress: gzip is a real-Storage
        concern; locally the raw bytes are stored so download_file returns
        exactly what was written.
        """

        @staticmethod
        def upload_file(path, file_bytes, content_type, compress=False):
            target = store_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(file_bytes)

        @staticmethod
        def download_file(path):
            target = store_dir / path
            if not target.exists():
                raise RuntimeError(f"missing {path}")
            return target.read_bytes()

        @staticmethod
        def delete_file(path):
            target = store_dir / path
            if target.exists():
                target.unlink()

    local_storage = _LocalStorage()
    patched = (ingestion_api, canonical_api, profiling_api)
    originals = [getattr(mod, "storage", None) for mod in patched]
    for mod in patched:
        mod.storage = local_storage

    try:
        yield tmp_path
    finally:
        for mod, original in zip(patched, originals):
            mod.storage = original
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
    token enforcement (test_token_errors, test_auth, test_isolation,
    test_storage_isolation) pop the override so routes run the genuine
    auth dependency against the per-test schema."""
    from app.core.auth import security
    from app.main import app

    saved = app.dependency_overrides.pop(security.get_current_user, None)
    try:
        yield isolated_env
    finally:
        if saved is not None:
            app.dependency_overrides[security.get_current_user] = saved
