"""Password hashing + JWT utilities (Phases 13-14).

access tokens: short-lived JWTs identifying a user (sub claim = user_id).
refresh tokens: longer-lived JWTs whose id (jti) is persisted in the
refresh_tokens table so logout can revoke them server-side.

decode_token raises the precise AppError for each failure mode
(token_missing / token_expired / token_invalid) so get_current_user can
map each to its own response.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.core.errors import token_expired, token_invalid, token_missing
from app.db import get_connection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    """Signed HS256 JWT expiring after ACCESS_TOKEN_EXPIRE_MINUTES."""
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Signed HS256 refresh JWT; returns (token, token_id) — the caller
    persists the token_id (jti) + SHA-256 hash so it can be revoked."""
    token_id = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "jti": token_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256"), token_id


def decode_token(token: str) -> dict:
    """Decode + verify a JWT, raising the specific AppError for each failure:
    missing token, expired token, or invalid signature/payload."""
    if not token:
        raise token_missing()
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except ExpiredSignatureError as exc:
        raise token_expired() from exc
    except JWTError as exc:
        raise token_invalid() from exc


def hash_refresh_token(token: str) -> str:
    """SHA-256 of the refresh token — stored instead of the raw token."""
    return hashlib.sha256(token.encode()).hexdigest()


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency: decode the bearer token and load the user.

    Raises the distinct AppError for each failure mode; loads the user
    from the database. Used via Depends() on every protected route.
    """
    payload = decode_token(token)  # raises token_missing/expired/invalid
    if payload.get("type") != "access":
        raise token_invalid()
    user_id = payload.get("sub")
    if not user_id:
        raise token_invalid()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id, email, full_name, role, created_at FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise token_invalid()
    return {
        "user_id": row["user_id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"],
        "created_at": row["created_at"],
    }
