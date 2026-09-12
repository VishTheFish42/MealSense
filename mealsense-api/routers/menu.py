from datetime import date
from fastapi import APIRouter
from typing import Optional
from services.menu_store import get_menu_for_date

router = APIRouter()


@router.get("/menu")
def get_menu(meal_period: Optional[str] = None, served_on: Optional[str] = None):
    menu = get_menu_for_date(served_on or date.today().isoformat())
    if meal_period:
        items = [i for i in menu if i["meal_period"] == meal_period or i["meal_period"] == "all_day"]
    else:
        items = menu
    return {"items": items, "count": len(items)}
