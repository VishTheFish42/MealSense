from datetime import date
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Optional
from services.menu_store import get_menu_for_date
from services.recommendation_engine import recommend

router = APIRouter()


class RecommendationRequest(BaseModel):
    profile: dict[str, Any]
    meal_period: str
    recent_menu_item_ids: Optional[list[str]] = []
    served_on: Optional[str] = None


@router.post("/recommendation")
def get_recommendation(req: RecommendationRequest):
    return recommend(
        menu=get_menu_for_date(req.served_on or date.today().isoformat()),
        profile=req.profile,
        meal_period=req.meal_period,
        recent_ids=req.recent_menu_item_ids or [],
    )
