"""
Canonical MenuItem schema that every ingestion adapter must normalize into.

This matches the flat shape actually consumed by services/recommendation_engine.py
and data/sample_menu.py (not the nested `nutrition: {...}` shape sketched in
README.md §7.1 — the flat shape is what the real engine reads, and diverging
from it would mean every adapter output silently fails to score).
"""
from __future__ import annotations
import hashlib
from typing import Any

VALID_MEAL_PERIODS = {"breakfast", "lunch", "dinner", "all_day"}

REQUIRED_NUMERIC_FIELDS = (
    "calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg", "sugar_g",
)


class MenuItemValidationError(Exception):
    """Raised when a raw record cannot be normalized into a safe MenuItem."""


def stable_item_id(name: str, station: str | None) -> str:
    """Deterministic per-dish id, not date-dependent, so the same dish served
    on different days keeps the same id — required for the recommendation
    engine's variety-penalty tracking (§5.2) to work across days."""
    key = f"{name.strip().lower()}|{(station or '').strip().lower()}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def build_menu_item(
    *,
    id: str,
    name: str,
    meal_period: str,
    calories: Any,
    protein_g: Any,
    carbs_g: Any,
    fat_g: Any,
    fiber_g: Any,
    sodium_mg: Any,
    sugar_g: Any,
    allergens: list[str] | None,
    price: Any,
    dietary_tags: list[str] | None = None,
    ingredients: list[str] | None = None,
    station: str | None = None,
    available_from: str | None = None,
    available_until: str | None = None,
    description: str | None = None,
) -> dict:
    """
    Validate and normalize a single menu item into the canonical shape.

    Raises MenuItemValidationError if the record is unsafe to serve, most
    importantly when allergen data is missing entirely (`allergens is None`).
    An explicitly empty list means "verified, this item has no allergens" and
    is fine; `None` means the source never told us, which is not the same
    thing and must not be silently treated as safe.
    """
    if not name or not name.strip():
        raise MenuItemValidationError("missing name")

    if meal_period not in VALID_MEAL_PERIODS:
        raise MenuItemValidationError(f"invalid meal_period: {meal_period!r}")

    if allergens is None:
        raise MenuItemValidationError("missing allergen data")

    numeric_values = {
        "calories": calories, "protein_g": protein_g, "carbs_g": carbs_g,
        "fat_g": fat_g, "fiber_g": fiber_g, "sodium_mg": sodium_mg, "sugar_g": sugar_g,
        "price": price,
    }
    parsed: dict[str, float] = {}
    for field_name, raw_value in numeric_values.items():
        parsed_value = _parse_numeric(raw_value)
        if parsed_value is None:
            raise MenuItemValidationError(f"missing or unparseable {field_name}: {raw_value!r}")
        parsed[field_name] = parsed_value

    return {
        "id": id,
        "name": name.strip(),
        "station": station or "",
        "meal_period": meal_period,
        "available_from": available_from,
        "available_until": available_until,
        "calories": parsed["calories"],
        "protein_g": parsed["protein_g"],
        "carbs_g": parsed["carbs_g"],
        "fat_g": parsed["fat_g"],
        "fiber_g": parsed["fiber_g"],
        "sodium_mg": parsed["sodium_mg"],
        "sugar_g": parsed["sugar_g"],
        "allergens": [a.strip().lower() for a in allergens],
        "dietary_tags": [t.strip().lower() for t in (dietary_tags or [])],
        "ingredients": list(ingredients or []),
        "price": parsed["price"],
        "description": description or "",
    }


def _parse_numeric(value: Any) -> float | None:
    """Best-effort numeric parse for values that may arrive as '420', '420 cal',
    '420.0mg', or already-numeric. Returns None if nothing usable is present —
    the caller treats that as a validation failure, never a silent 0."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        digits = ""
        seen_dot = False
        for ch in stripped:
            if ch.isdigit():
                digits += ch
            elif ch == "." and not seen_dot:
                digits += ch
                seen_dot = True
            elif digits:
                break
        if not digits or digits == ".":
            return None
        try:
            return float(digits)
        except ValueError:
            return None
    return None
