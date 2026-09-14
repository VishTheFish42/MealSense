from datetime import date
from fastapi import APIRouter, HTTPException
from google.api_core.exceptions import NotFound
from pydantic import BaseModel
from typing import Any, Optional
from services.firestore_client import FirestoreNotConfiguredError
from services.menu_store import get_menu_for_date
from services.recommendation_engine import recommend
from services.recommendation_history import get_recent_recommendations, set_feedback, write_recommendation

router = APIRouter()


class RecommendationRequest(BaseModel):
    profile: dict[str, Any]
    meal_period: str
    recent_menu_item_ids: Optional[list[str]] = []
    served_on: Optional[str] = None


@router.post("/recommendation")
def get_recommendation(req: RecommendationRequest):
    result = recommend(
        menu=get_menu_for_date(req.served_on or date.today().isoformat()),
        profile=req.profile,
        meal_period=req.meal_period,
        recent_ids=req.recent_menu_item_ids or [],
    )

    if result.get("recommendation"):
        student_id = req.profile.get("uid")
        if student_id:
            try:
                result["recommendation_id"] = write_recommendation(
                    student_id=student_id,
                    menu_item_id=result["recommendation"]["menuItem"]["id"],
                    menu_item_name=result["recommendation"]["menuItem"]["name"],
                    score=result["recommendation"]["score"],
                    meal_period=req.meal_period,
                )
            except FirestoreNotConfiguredError:
                # Feedback isn't available in this environment, but the
                # recommendation itself must still work — same graceful
                # degradation menu_store.py uses for the sample-menu
                # fallback, not a reason to fail the whole request.
                pass

    return result


@router.get("/recommendation/history")
def get_recommendation_history(student_id: str, days: int = 7):
    """README §9.4: "view recommendation history (last 7 days)." No auth
    token verification here — matches the rest of this route family's
    existing trust model (POST /recommendation already trusts a
    client-supplied profile.uid with no server-side identity check); this
    doesn't introduce a new gap, just reads via the same trust boundary
    that already exists."""
    return {"history": get_recent_recommendations(student_id, days=days)}


class FeedbackRequest(BaseModel):
    feedback: str


@router.post("/recommendation/{recommendation_id}/feedback")
def submit_feedback(recommendation_id: str, body: FeedbackRequest):
    try:
        set_feedback(recommendation_id, body.feedback)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NotFound:
        raise HTTPException(status_code=404, detail=f"No recommendation {recommendation_id!r} found")
    return {"recommendation_id": recommendation_id, "feedback": body.feedback}
