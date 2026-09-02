"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api import (
    health,
    ingestion,
    profiling,
    semantic_contract,
    data_quality,
    canonical_model,
    kpi,
    anomaly,
    drivers,
    evidence,
    persona,
    insights,
    recommendations,
    telemetry,
    feedback,
    auth,
    history,
)
from app.core.errors import AppError, database_unavailable, unexpected_error, validation_error
from app.db import init_db

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Boot even when the database is unreachable (routes then report
    # database_unavailable; /health/db shows the failure) instead of
    # crashing the process at startup.
    try:
        init_db()
    except OperationalError as exc:
        logger.error("Database unavailable at startup: %s", exc)
    yield


app = FastAPI(title="KPI Intelligence-to-Action Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    """Return the AppError's shape and status directly."""
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.message),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    """Map any legacy HTTPException into the standard error shape."""
    logger.warning("HTTPException %s: %s", exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body("http_error", str(exc.detail)),
    )


@app.exception_handler(OperationalError)
async def database_error_handler(_: Request, exc: OperationalError):
    """Map any database connection failure to database_unavailable."""
    logger.error("Database unavailable: %s", exc)
    return JSONResponse(
        status_code=503,
        content=_error_body("database_unavailable", database_unavailable().message),
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    """Pass through the specific field-level message, not a generic blob."""
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(part) for part in first.get("loc", []) if part != "body")
    detail = first.get("msg", "Invalid request.")
    message = f"{loc}: {detail}" if loc else detail
    return JSONResponse(
        status_code=422,
        content=_error_body("validation_error", message),
    )


@app.exception_handler(Exception)
async def unexpected_handler(_: Request, exc: Exception):
    """Catch-all: log the real traceback server-side, never leak it."""
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=_error_body("unexpected_error", unexpected_error().message),
    )


app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(profiling.router)
app.include_router(semantic_contract.router)
app.include_router(data_quality.router)
app.include_router(canonical_model.router)
app.include_router(kpi.router)
app.include_router(anomaly.router)
app.include_router(drivers.router)
app.include_router(evidence.router)
app.include_router(persona.router)
app.include_router(insights.router)
app.include_router(recommendations.router)
app.include_router(telemetry.router)
app.include_router(feedback.router)
app.include_router(auth.router)
app.include_router(history.router)
