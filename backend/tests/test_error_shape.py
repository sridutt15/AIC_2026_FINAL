"""Error-shape tests (Phase 14): every AppError case returns the exact JSON shape.

Uses a throwaway FastAPI app sharing the main app's exception handlers, so
probe routes never pollute the real route table.
"""

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.core.errors import (
    bad_credentials,
    database_unavailable,
    email_taken,
    not_found,
    token_expired,
    token_invalid,
    token_missing,
    unexpected_error,
    validation_error,
)
from app.main import app


def _hit(maker):
    """Fresh app + the main app's handlers; one probe route raising maker()."""
    probe_app = FastAPI()
    for exc, handler in app.exception_handlers.items():
        probe_app.add_exception_handler(exc, handler)

    router = APIRouter()

    @router.get("/__probe")
    def probe_route():
        raise maker()

    probe_app.include_router(router)
    return TestClient(probe_app).get("/__probe")


def test_token_missing_shape():
    resp = _hit(token_missing)
    assert resp.status_code == 401
    assert resp.json() == {
        "error": {"code": "token_missing", "message": "You're not logged in. Please log in to continue."}
    }


def test_token_expired_shape():
    resp = _hit(token_expired)
    assert resp.status_code == 401
    assert resp.json() == {
        "error": {"code": "token_expired", "message": "Your session has expired. Please log in again."}
    }


def test_token_invalid_shape():
    resp = _hit(token_invalid)
    assert resp.status_code == 401
    assert resp.json() == {
        "error": {"code": "token_invalid", "message": "Your session is invalid. Please log in again."}
    }


def test_bad_credentials_shape():
    resp = _hit(bad_credentials)
    assert resp.status_code == 401
    assert resp.json() == {"error": {"code": "bad_credentials", "message": "Invalid email or password."}}


def test_email_taken_shape():
    resp = _hit(email_taken)
    assert resp.status_code == 409
    assert resp.json() == {
        "error": {"code": "email_taken", "message": "An account with this email already exists."}
    }


def test_not_found_shape():
    resp = _hit(lambda: not_found("Source"))
    assert resp.status_code == 404
    assert resp.json() == {"error": {"code": "not_found", "message": "Source not found."}}


def test_database_unavailable_shape():
    resp = _hit(database_unavailable)
    assert resp.status_code == 503
    assert resp.json() == {
        "error": {
            "code": "database_unavailable",
            "message": "We're having trouble reaching the database. Please try again in a moment.",
        }
    }


def test_validation_error_passes_message_through():
    resp = _hit(lambda: validation_error("grain: field required"))
    assert resp.status_code == 422
    assert resp.json() == {"error": {"code": "validation_error", "message": "grain: field required"}}


def test_unexpected_error_shape():
    resp = _hit(unexpected_error)
    assert resp.status_code == 500
    assert resp.json() == {
        "error": {"code": "unexpected_error", "message": "Something went wrong on our end. Please try again."}
    }


def test_unhandled_exception_never_leaks_traceback():
    """A raw exception maps to unexpected_error with no traceback in body."""
    probe_app = FastAPI()
    for exc, handler in app.exception_handlers.items():
        probe_app.add_exception_handler(exc, handler)

    @probe_app.get("/__boom")
    def boom():
        raise RuntimeError("secret internal detail /Users/somebody/paths")

    resp = TestClient(probe_app, raise_server_exceptions=False).get("/__boom")
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "unexpected_error"
    assert "secret internal detail" not in resp.text
    assert "Traceback" not in resp.text
