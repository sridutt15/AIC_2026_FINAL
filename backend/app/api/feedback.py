"""Feedback API — record/list analyst verdicts on insights & recommendations."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.feedback.store import (
    get_feedback,
    recent_feedback,
    record_feedback,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    target_type: str  # "insight" | "recommendation"
    target_id: str
    verdict: str  # "confirm" | "correct" | "reject"
    note: str | None = None
    driver_type: str | None = None


@router.post("")
def post_feedback(req: FeedbackRequest) -> dict:
    """Record one analyst verdict; returns the stored row."""
    try:
        row = record_feedback(
            target_type=req.target_type,
            target_id=req.target_id,
            verdict=req.verdict,
            note=req.note,
            driver_type=req.driver_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return row


@router.get("/recent")
def list_recent_feedback(limit: int = 20) -> dict:
    """Most recent feedback rows (for the Feedback page list)."""
    return {"feedback": recent_feedback(limit)}


@router.get("/{target_id}")
def get_feedback_for_target(target_id: str) -> dict:
    """All feedback for one target, newest first."""
    return {"target_id": target_id, "feedback": get_feedback(target_id)}
