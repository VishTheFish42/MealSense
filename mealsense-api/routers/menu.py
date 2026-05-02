from fastapi import APIRouter
from typing import Optional
from data.sample_menu import SAMPLE_MENU

router = APIRouter()


@router.get("/menu")
def get_menu(meal_period: Optional[str] = None):
    if meal_period:
        items = [i for i in SAMPLE_MENU if i["meal_period"] == meal_period or i["meal_period"] == "all_day"]
    else:
        items = SAMPLE_MENU
    return {"items": items, "count": len(items)}
