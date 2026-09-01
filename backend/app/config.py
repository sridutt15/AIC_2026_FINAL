"""Application settings loaded from .env via python-dotenv."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env relative to this file: backend/app/config.py -> backend/.env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Global settings for the KPI Intelligence-to-Action Engine backend."""

    def __init__(self) -> None:
        self.PORT: int = int(os.getenv("PORT", "8000"))
        # Gemini key for Phase 10's LLM recommendation layer. Never logged.
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        # Model + per-token rates for cost estimation. Defaults target
        # gemini-2.0-flash (published $0.10/M input, $0.40/M output).
        self.GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        self.GEMINI_INPUT_USD_PER_MTOK: float = float(
            os.getenv("GEMINI_INPUT_USD_PER_MTOK", "0.10")
        )
        self.GEMINI_OUTPUT_USD_PER_MTOK: float = float(
            os.getenv("GEMINI_OUTPUT_USD_PER_MTOK", "0.40")
        )
        # Kept for backward compatibility (unused — Phase 10 uses Gemini).
        self.ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
        # Postgres connection string (Supabase transaction pooler, port 6543).
        # Required — the app refuses to start without it (no SQLite fallback).
        database_url = os.getenv("DATABASE_URL", "")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is required but missing. Set it in backend/.env "
                "to the Supabase Transaction pooler connection string "
                "(Project Settings -> Database -> Connection string, port 6543)."
            )
        self.DATABASE_URL: str = database_url
        # Auth (Phase 13): JWT signing key + token lifetimes.
        secret_key = os.getenv("SECRET_KEY", "")
        if not secret_key:
            raise RuntimeError(
                "SECRET_KEY is required but missing. Generate one with "
                "`openssl rand -hex 32` and set it in backend/.env."
            )
        self.SECRET_KEY: str = secret_key
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )
        self.REFRESH_TOKEN_EXPIRE_DAYS: int = int(
            os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
        )
        # Raw uploaded files live here, one subfolder per source_id.
        self.UPLOADS_DIR: Path = BASE_DIR / "data" / "uploads"


settings = Settings()
