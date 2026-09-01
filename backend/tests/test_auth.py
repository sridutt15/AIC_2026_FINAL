"""Auth API tests (Phase 13): register, login, refresh, logout, /auth/me."""

from fastapi.testclient import TestClient

from app.db import get_connection, init_db
from app.main import app

EMAIL = "phase13@example.com"
PASSWORD = "correct-horse-staple"


def _register(client, email=EMAIL, password=PASSWORD, name="Phase Thirteen"):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": name},
    )


def test_register_stores_bcrypt_hash_not_plaintext(isolated_env):
    """password_hash must be a bcrypt hash ($2b$...), never the plaintext."""
    init_db()
    with TestClient(app) as client:
        resp = _register(client)
        assert resp.status_code == 200
        user = resp.json()["user"]
        assert user["email"] == EMAIL
        assert user["role"] == "member"

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?", (EMAIL,)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    stored = row["password_hash"]
    assert stored != PASSWORD  # never the plaintext
    assert stored.startswith("$2b$")  # bcrypt prefix


def test_register_same_email_twice_fails(isolated_env):
    """Second registration with the same email returns an error."""
    init_db()
    with TestClient(app) as client:
        first = _register(client)
        assert first.status_code == 200
        second = _register(client)
        assert second.status_code == 400
        assert "already" in second.json()["detail"]


def test_login_correct_password_returns_both_tokens(isolated_env):
    init_db()
    with TestClient(app) as client:
        _register(client)
        resp = client.post(
            "/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["user"]["email"] == EMAIL


def test_login_wrong_password_401(isolated_env):
    init_db()
    with TestClient(app) as client:
        _register(client)
        resp = client.post(
            "/auth/login", json={"email": EMAIL, "password": "wrong-pass"}
        )
        assert resp.status_code == 401


def test_me_without_token_401(isolated_env):
    init_db()
    with TestClient(app) as client:
        assert client.get("/auth/me").status_code == 401


def test_me_with_valid_token_returns_user(isolated_env):
    init_db()
    with TestClient(app) as client:
        _register(client)
        login = client.post(
            "/auth/login", json={"email": EMAIL, "password": PASSWORD}
        ).json()
        resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {login['access_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == EMAIL
        assert resp.json()["user_id"] == login["user"]["user_id"]


def test_refresh_and_logout(isolated_env):
    """Refresh mints a new access token; logout revokes the refresh token."""
    init_db()
    with TestClient(app) as client:
        _register(client)
        login = client.post(
            "/auth/login", json={"email": EMAIL, "password": PASSWORD}
        ).json()

        refreshed = client.post(
            "/auth/refresh", json={"refresh_token": login["refresh_token"]}
        )
        assert refreshed.status_code == 200
        assert refreshed.json()["access_token"]

        # The refreshed access token authenticates /auth/me
        me = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["email"] == EMAIL

        # Logout revokes the refresh token -> refresh now fails
        out = client.post(
            "/auth/logout", json={"refresh_token": login["refresh_token"]}
        )
        assert out.status_code == 200
        again = client.post(
            "/auth/refresh", json={"refresh_token": login["refresh_token"]}
        )
        assert again.status_code == 401
