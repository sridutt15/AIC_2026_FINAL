"""Database connection tests (Phase 12): DATABASE_URL connectivity + /health/db."""

from fastapi.testclient import TestClient

from app.config import settings
from app.db import engine
from app.main import app
from sqlalchemy import text


def test_settings_has_database_url():
    """The app configured a real Postgres DATABASE_URL (not SQLite)."""
    assert settings.DATABASE_URL.startswith("postgresql"), (
        "DATABASE_URL must be a Postgres connection string"
    )


def test_engine_connects_and_selects_one():
    """The SQLAlchemy engine reaches the database and executes SELECT 1."""
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_health_db_returns_ok_with_latency():
    """GET /health/db -> 200 {status: ok, latency_ms: n} when DB reachable."""
    client = TestClient(app)
    resp = client.get("/health/db")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["latency_ms"], int)
    assert body["latency_ms"] >= 0


def test_health_liveness_unchanged():
    """GET /health still answers liveness only (no DB check)."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
