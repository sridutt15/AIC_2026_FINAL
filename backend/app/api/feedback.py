"""Feedback API — record/list analyst verdicts on insights & recommendations."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.activity.logger import log_activity
from app.core.auth.security import get_current_user
from app.core.feedback.store import (
    get_feedback,
    recent_feedback,
    record_feedback,
)

router = APIRouter(prefix="/feedback", tags=["feedback"], dependencies=[Depends(get_current_user)])


class FeedbackRequest(BaseModel):
    target_type: str  # "insight" | "recommendation"
    target_id: str
    verdict: str  # "confirm" | "correct" | "reject"
    note: str | None = None
    driver_type: str | None = None


@router.post("")
def post_feedback(req: FeedbackRequest, current_user: dict = Depends(get_current_user)) -> dict:
    """Record one analyst verdict; returns the stored row."""
    try:
        row = record_feedback(
            target_type=req.target_type,
            target_id=req.target_id,
            verdict=req.verdict,
            note=req.note,
            driver_type=req.driver_type,
            user_id=current_user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    log_activity(
        current_user["user_id"], "feedback_submitted", req.target_type, req.target_id,
        f"Feedback: {req.verdict} on {req.target_type} {req.target_id[:8]}",
    )
    return row


@router.get("/recent")
def list_recent_feedback(limit: int = 20, current_user: dict = Depends(get_current_user)) -> dict:
    """Most recent feedback rows (current user's only, for the Feedback page)."""
    return {"feedback": recent_feedback(limit, current_user["user_id"])}


@router.get("/{target_id}")
def get_feedback_for_target(target_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """All feedback for one target (current user's only), newest first."""
    return {
        "target_id": target_id,
        "feedback": get_feedback(target_id, current_user["user_id"]),
    }
