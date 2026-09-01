"""Token-error tests (Phase 14): distinct codes for missing/expired/tampered tokens."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.db import init_db
from app.main import app

client = TestClient(app)


def _make_token(payload: dict) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def test_no_token(real_auth):
    init_db()
    resp = client.get("/ingestion/sources")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_missing"


def test_expired_token(real_auth):
    init_db()
    token = _make_token(
        {
            "sub": "some-user",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        }
    )
    resp = client.get("/ingestion/sources", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_expired"


def test_tampered_token(real_auth):
    init_db()
    token = _make_token(
        {
            "sub": "some-user",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
    )
    tampered = token[:-6] + ("AAAAAA" if not token.endswith("AAAAAA") else "BBBBBB")
    resp = client.get("/ingestion/sources", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_invalid"


def test_wrong_secret_token(real_auth):
    """A token signed by a different key is token_invalid, not expired."""
    init_db()
    token = jwt.encode(
        {
            "sub": "some-user",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        "not-the-real-secret",
        algorithm="HS256",
    )
    resp = client.get("/ingestion/sources", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_invalid"


def test_valid_user_but_garbage_subject(real_auth):
    """Well-signed token for a nonexistent user -> token_invalid."""
    init_db()
    token = _make_token(
        {
            "sub": "no-such-user-exists",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
    )
    resp = client.get("/ingestion/sources", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_invalid"


def test_refresh_token_used_as_access(real_auth):
    """A refresh token presented as an access token -> token_invalid."""
    init_db()
    from app.core.auth.security import create_refresh_token

    refresh, _ = create_refresh_token("some-user")
    resp = client.get("/ingestion/sources", headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_invalid"
