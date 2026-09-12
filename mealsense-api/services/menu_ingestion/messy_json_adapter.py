"""
Adapter for a school's own ad hoc daily JSON export: inconsistent key
casing, units embedded in numeric strings ("450 cal", "38g"), meal periods
as free text ("Lunch", "ALL DAY"), and allergens sometimes missing entirely
for a given item rather than an explicit empty list.

This is the shape referenced in design-spec.md §7.0 as the actual product
wedge — a real campus feed that predates any vendor integration and was
never meant to be machine-read by anything else.
"""
from __future__ import annotations
from typing import Any

from .base import IngestionResult, RejectedRecord
from .schema import MenuItemValidationError, build_menu_item, stable_item_id

_MEAL_PERIOD_ALIASES = {
    "breakfast": "breakfast",
    "lunch": "lunch",
    "dinner": "dinner",
    "all day": "all_day",
    "allday": "all_day",
    "all_day": "all_day",
}

# Sentinel strings a human might type to mean "verified, no allergens" —
# distinct from the key being absent, which means "we don't know."
_EXPLICIT_NONE = {"none", "n/a", "na", "-", ""}


def _normalize_meal_period(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    return _MEAL_PERIOD_ALIASES.get(raw.strip().lower(), raw.strip().lower())


def _split_commas(value: Any) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _normalize_allergens(raw: Any) -> list[str] | None:
    """Missing key => None (unknown, must be rejected upstream).
    A string like "none" or "" => explicitly zero allergens.
    Anything else => comma-split list."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return [str(a).strip() for a in raw if str(a).strip()]
    if isinstance(raw, str):
        if raw.strip().lower() in _EXPLICIT_NONE:
            return []
        return _split_commas(raw)
    return None


class MessyJsonMenuAdapter:
    """Normalizes a list of loosely-shaped dicts using common alternate key
    names, so a school's export doesn't need to match any fixed schema."""

    _NAME_KEYS = ("name", "ItemName", "item_name", "itemName", "title")
    _STATION_KEYS = ("station", "Station", "location")
    _MEAL_KEYS = ("meal_period", "Meal", "meal", "MealPeriod")
    _CAL_KEYS = ("calories", "Cals", "cal", "Calories")
    _PROTEIN_KEYS = ("protein_g", "Protein", "protein")
    _CARBS_KEYS = ("carbs_g", "Carbs", "carbs")
    _FAT_KEYS = ("fat_g", "Fat", "fat")
    _FIBER_KEYS = ("fiber_g", "Fiber", "fiber")
    _SODIUM_KEYS = ("sodium_mg", "Sodium", "sodium")
    _SUGAR_KEYS = ("sugar_g", "Sugar", "sugar")
    _ALLERGEN_KEYS = ("allergens", "Allergens", "allergen")
    _TAG_KEYS = ("dietary_tags", "Tags", "tags", "DietaryTags")
    _PRICE_KEYS = ("price", "Price", "cost", "Cost")
    _AVAILABLE_FROM_KEYS = ("available_from", "AvailableFrom", "from", "start_time")
    _AVAILABLE_UNTIL_KEYS = ("available_until", "AvailableUntil", "until", "end_time")
    _INGREDIENT_KEYS = ("ingredients", "Ingredients")
    _DESCRIPTION_KEYS = ("description", "Description", "desc")

    def normalize(self, raw: list[dict]) -> IngestionResult:
        result = IngestionResult()

        for record in raw:
            try:
                name = self._first(record, self._NAME_KEYS)
                station = self._first(record, self._STATION_KEYS)
                item = build_menu_item(
                    id=stable_item_id(str(name or ""), station and str(station)),
                    name=str(name or ""),
                    station=station,
                    meal_period=_normalize_meal_period(self._first(record, self._MEAL_KEYS)),
                    available_from=self._first(record, self._AVAILABLE_FROM_KEYS),
                    available_until=self._first(record, self._AVAILABLE_UNTIL_KEYS),
                    calories=self._first(record, self._CAL_KEYS),
                    protein_g=self._first(record, self._PROTEIN_KEYS),
                    carbs_g=self._first(record, self._CARBS_KEYS),
                    fat_g=self._first(record, self._FAT_KEYS),
                    fiber_g=self._first(record, self._FIBER_KEYS),
                    sodium_mg=self._first(record, self._SODIUM_KEYS),
                    sugar_g=self._first(record, self._SUGAR_KEYS),
                    price=self._first(record, self._PRICE_KEYS),
                    allergens=_normalize_allergens(self._first(record, self._ALLERGEN_KEYS)),
                    dietary_tags=_split_commas(self._first(record, self._TAG_KEYS)),
                    ingredients=_split_commas(self._first(record, self._INGREDIENT_KEYS)),
                    description=self._first(record, self._DESCRIPTION_KEYS),
                )
                result.items.append(item)
            except MenuItemValidationError as e:
                result.rejected.append(RejectedRecord(raw=record, reason=str(e)))

        return result

    @staticmethod
    def _first(record: dict, keys: tuple[str, ...]) -> Any:
        for key in keys:
            if key in record:
                return record[key]
        return None
