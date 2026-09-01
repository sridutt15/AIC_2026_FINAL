"""Auth API (Phase 13): register, login, refresh, logout, me."""

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.config import settings
from app.core.auth.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db import get_connection, init_db

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_response(row) -> dict:
    return {
        "user_id": row["user_id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


def _issue_token_pair(user_id: str, conn) -> tuple[str, str]:
    """Create access + refresh JWTs; persist the refresh token record."""
    access = create_access_token(user_id)
    refresh, token_id = create_refresh_token(user_id)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    ).isoformat()
    conn.execute(
        "INSERT INTO refresh_tokens (token_id, user_id, token_hash, expires_at, revoked, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (token_id, user_id, hash_refresh_token(refresh), expires_at, 0, _now_iso()),
    )
    return access, refresh


@router.post("/register")
def register(body: RegisterRequest) -> dict:
    """Create an account; 400 if the email is already taken."""
    init_db()
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT user_id FROM users WHERE email = ?", (body.email,)
        ).fetchone()
        if existing is not None:
            raise HTTPException(status_code=400, detail="Email already registered")
        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (user_id, email, password_hash, full_name, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, body.email, hash_password(body.password), body.full_name, "member", _now_iso()),
        )
        access, refresh = _issue_token_pair(user_id, conn)
        conn.commit()
    finally:
        conn.close()
    row = _fetch_user_by_email(body.email)
    return {"access_token": access, "refresh_token": refresh, "user": _user_response(row)}


def _fetch_user_by_email(email: str):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT user_id, email, password_hash, full_name, role, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()


@router.post("/login")
def login(body: LoginRequest) -> dict:
    """Verify credentials; 401 on wrong email or password."""
    init_db()
    row = _fetch_user_by_email(body.email)
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    conn = get_connection()
    try:
        access, refresh = _issue_token_pair(row["user_id"], conn)
        conn.commit()
    finally:
        conn.close()
    return {"access_token": access, "refresh_token": refresh, "user": _user_response(row)}


@router.post("/refresh")
def refresh_tokens(body: RefreshRequest) -> dict:
    """Exchange a valid, unrevoked refresh token for a new access token."""
    from jose import JWTError

    from app.core.auth.security import decode_token

    invalid = HTTPException(status_code=401, detail="Invalid refresh token")
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise invalid
    if payload.get("type") != "refresh":
        raise invalid
    token_id = payload.get("jti")
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT token_id, user_id, revoked FROM refresh_tokens WHERE token_id = ?",
            (token_id,),
        ).fetchone()
        if row is None or row["revoked"]:
            raise invalid
        access = create_access_token(row["user_id"])
    finally:
        conn.close()
    return {"access_token": access}


@router.post("/logout")
def logout(body: LogoutRequest) -> dict:
    """Revoke a refresh token so it can no longer mint access tokens."""
    from jose import JWTError

    from app.core.auth.security import decode_token

    try:
        payload = decode_token(body.refresh_token)
        token_id = payload.get("jti")
    except JWTError:
        token_id = None
    conn = get_connection()
    try:
        if token_id:
            conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE token_id = ?", (token_id,)
            )
            conn.commit()
    finally:
        conn.close()
    return {"logged_out": True}


@router.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    """Return the authenticated user's profile."""
    return user
