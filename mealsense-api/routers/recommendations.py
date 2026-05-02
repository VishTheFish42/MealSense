from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Optional
from data.sample_menu import SAMPLE_MENU
from services.recommendation_engine import recommend

router = APIRouter()


class RecommendationRequest(BaseModel):
    profile: dict[str, Any]
    meal_period: str
    recent_menu_item_ids: Optional[list[str]] = []


@router.post("/recommendation")
def get_recommendation(req: RecommendationRequest):
    return recommend(
        menu=SAMPLE_MENU,
        profile=req.profile,
        meal_period=req.meal_period,
        recent_ids=req.recent_menu_item_ids or [],
    )
