"""App-wide JSON error shape (Phase 14).

Every error response from every route uses this one shape:
    {"error": {"code": "<short_code>", "message": "<human sentence>"}}
"""

from fastapi import HTTPException


class AppError(Exception):
    """An error with a status code, machine code, and human message."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def token_missing() -> AppError:
    return AppError(401, "token_missing", "You're not logged in. Please log in to continue.")


def token_expired() -> AppError:
    return AppError(401, "token_expired", "Your session has expired. Please log in again.")


def token_invalid() -> AppError:
    return AppError(401, "token_invalid", "Your session is invalid. Please log in again.")


def bad_credentials() -> AppError:
    return AppError(401, "bad_credentials", "Invalid email or password.")


def email_taken() -> AppError:
    return AppError(409, "email_taken", "An account with this email already exists.")


def not_found(resource: str) -> AppError:
    return AppError(404, "not_found", f"{resource} not found.")


def database_unavailable() -> AppError:
    return AppError(
        503,
        "database_unavailable",
        "We're having trouble reaching the database. Please try again in a moment.",
    )


def validation_error(message: str) -> AppError:
    """Field-level message passed through, not swallowed."""
    return AppError(422, "validation_error", message)


def unexpected_error() -> AppError:
    return AppError(
        500, "unexpected_error", "Something went wrong on our end. Please try again."
    )
