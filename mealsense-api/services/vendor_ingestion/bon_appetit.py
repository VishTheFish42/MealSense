"""
Vendor adapter for Bon Appétit Management Co. campus dining sites
(cafebonappetit.com) — first wired up for Santa Clara University
(campus_config.py's "santa_clara" entry), but written against Bon
Appétit's general site structure so any other Bon Appétit campus is just a
new CampusConfig entry, not a new adapter.

WHY THIS SCRAPES HTML INSTEAD OF CALLING A JSON API: Bon Appétit's
documented public API (legacy.cafebonappetit.com/api/2/menus?cafe=<id>)
now refuses unauthenticated requests ("Cafemanager no longer accepts
unauthenticated requests. Please use the authenticated API.", confirmed
2026-09-11) — that requires vendor-issued credentials we don't have, the
same category of blocker as README §12 open question #1. Each café's own
public page, however, still embeds a real structured data blob
(`Bamco.dayparts` / `Bamco.menu_items`, a WordPress theme's own client-side
state) with everything we need: name, station, per-daypart time windows,
full nutrition, price, ingredient text, and dietary/allergen icons. This is
not a stable public contract Bon Appétit committed to — if they change
their theme, this breaks — but it's real, live, structured data reachable
today with no auth, which the locked-down JSON API is not.

ALLERGEN TRUST POLICY (a real product decision, not an implementation
detail — see requirements.md §3 / tasks.md 3.4 for the fuller writeup):
Bon Appétit's own food-allergy disclosure page for this campus
(scudining.cafebonappetit.com/food-allergens/, confirmed 2026-09-11) states
their online data is not a complete substitute for asking kitchen staff
directly — "the Ingredient Experts in your café are the best source of
information" — and that every location handles all top-9 allergens in
shared prep areas. So an item's dietary/allergen icons are treated as a
reliable POSITIVE signal only: an icon present means that allergen is
genuinely there, but no icons present does NOT mean "verified allergen-free"
— that would be a fail-open assumption this codebase has deliberately
avoided everywhere else (recommendation_engine.py's own hard filter,
menu_ingestion's adapters). An item with zero allergen-relevant icons
therefore gets `allergens=None` (unknown), which build_menu_item already
rejects, and the reject gets queued for a human via menu_review_queue.py
rather than silently dropped.

LLM-ASSISTED GAP FILLING (design-spec.md §7.0a, tasks.md 3.6, decided
2026-09-11 — scoped to this adapter only, not the CSV/messy-JSON manual
upload paths): before giving up on an item missing nutrition data or
structured allergen data, this adapter gives services/menu_ingestion/
llm_enrichment.py one shot at filling exactly the gap, never anything
already present. Nutrition estimates are used outright (low-stakes if
wrong) and the item is flagged with which fields were estimated. Allergen
extraction stays fail-closed: only used if confidence clears
ALLERGEN_CONFIDENCE_THRESHOLD, and even then the item still gets a
review-queue entry — an LLM-accepted item is never treated as equivalent
to a real cor_icon match with zero human visibility.
"""
from __future__ import annotations
import json
import re
from typing import Any, Callable

import httpx

from .campus_config import CampusConfig
from ..menu_ingestion.base import IngestionResult, RejectedRecord, ReviewNote
from ..menu_ingestion.llm_enrichment import (
    ALLERGEN_CONFIDENCE_THRESHOLD,
    estimate_missing_nutrition as _default_estimate_nutrition,
    extract_allergens_from_ingredients as _default_extract_allergens,
)
from ..menu_ingestion.schema import (
    MenuItemValidationError, build_menu_item, stable_item_id, _parse_numeric,
)

_NUTRITION_FIELDS = (
    "calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg", "sugar_g",
)

# Maps our canonical field name to Bon Appétit's own nutrition_details key.
_NUTRITION_KEY_ALIASES: dict[str, str] = {
    "calories": "calories",
    "protein_g": "proteinContent",
    "carbs_g": "carbohydrateContent",
    "fat_g": "fatContent",
    "fiber_g": "fiberContent",
    "sodium_mg": "sodiumContent",
    "sugar_g": "sugarContent",
}

_USER_AGENT = "Mozilla/5.0 (compatible; MealSenseIngestion/1.0)"
_FETCH_TIMEOUT_S = 15.0

# Bon Appétit's "Circle of Responsibility" icon labels that map onto our
# allergen vocabulary (README.md §6.2). Any icon not in either map here
# (e.g. "Farm to Fork", "Low Carbon Footprint", "Seafood Watch") is
# informational and simply ignored — it isn't a safety signal for us.
_COR_ICON_ALLERGENS: dict[str, str] = {
    "milk": "dairy",
    "wheat/gluten": "gluten",
    "egg": "eggs",
    "soy": "soy",
    "tree nut": "nuts",
    "peanut": "nuts",
    "sesame": "sesame",
    "fish": "fish",
    "shellfish": "shellfish",
}

_COR_ICON_DIET_TAGS: dict[str, str] = {
    "vegan": "vegan",
    "vegetarian": "vegetarian",
    "halal": "halal",
    "kosher": "kosher",
}

# Bon Appétit dayparts are frequently café-specific labels ("Mission Bakery
# Cafe", "Summer Schedule") rather than clean breakfast/lunch/dinner names
# — unlike our other adapters' meal_period field, which always arrives
# already meaningful. Anything unrecognized defaults to all_day, which is
# the safe choice for an all-day counter (never wrongly excluded by the
# meal-period bucket filter) rather than guessing a specific period.
_DAYPART_ALIASES: dict[str, str] = {
    "breakfast": "breakfast",
    "brunch": "breakfast",
    "lunch": "lunch",
    "dinner": "dinner",
    "late night": "dinner",
    "all day": "all_day",
}


def _normalize_daypart_label(label: Any) -> str:
    if not isinstance(label, str):
        return "all_day"
    return _DAYPART_ALIASES.get(label.strip().lower(), "all_day")


def _extract_json_var(html: str, var_name: str) -> dict | None:
    """Pulls `<var_name> = {...};` out of an inline <script> block. The
    non-greedy match up to the literal `};` terminator (not just the next
    `}`) is what makes this safe against nested braces in the JSON body —
    JS source doesn't emit a raw `}` immediately followed by `);` inside an
    object literal's own content."""
    m = re.search(rf"{re.escape(var_name)}\s*=\s*(\{{.*?\}});", html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _extract_dayparts(html: str) -> dict[str, dict]:
    dayparts: dict[str, dict] = {}
    for m in re.finditer(r"Bamco\.dayparts\['(\d+)'\]\s*=\s*(\{.*?\});", html, re.S):
        try:
            dayparts[m.group(1)] = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
    return dayparts


def _cor_icon_labels(item: dict) -> list[str]:
    ordered = item.get("ordered_cor_icon") or {}
    return [v.get("label", "") for v in ordered.values() if isinstance(v, dict)]


def _extract_allergens(item: dict) -> list[str] | None:
    """See the module docstring's ALLERGEN TRUST POLICY section. Returns
    None (unknown, rejected upstream) when no allergen-relevant icon is
    present — never an empty list, since that would assert "verified safe"
    on data Bon Appétit itself doesn't claim is exhaustive."""
    found = {
        _COR_ICON_ALLERGENS[label.lower()]
        for label in _cor_icon_labels(item)
        if label.lower() in _COR_ICON_ALLERGENS
    }
    return sorted(found) if found else None


def _extract_dietary_tags(item: dict) -> list[str]:
    return sorted({
        _COR_ICON_DIET_TAGS[label.lower()]
        for label in _cor_icon_labels(item)
        if label.lower() in _COR_ICON_DIET_TAGS
    })


def _nutrition_value(item: dict, key: str) -> Any:
    details = item.get("nutrition_details") or {}
    entry = details.get(key) or {}
    return entry.get("value")


def _extract_price(item: dict) -> Any:
    """Prefers the first listed size's price — most items here are
    single-size, and multi-size items (e.g. drinks in 12/16/20 oz) don't
    have an equivalent in our OrderItem model (flat price, no size
    variants) regardless of which size we picked, so this is a known,
    documented simplification, not a silent one."""
    sizes = item.get("sizes") or []
    if sizes:
        return sizes[0].get("price")
    raw = item.get("price")
    if isinstance(raw, str):
        m = re.search(r"\$[\d.]+", raw)
        if m:
            return m.group(0)
    return None


def _parse_cafe_html(
    html: str,
    cafe_name: str,
    estimate_nutrition: Callable[[str, str, list[str]], dict[str, float]] = _default_estimate_nutrition,
    extract_allergens_llm: Callable[[str, str], Any] = _default_extract_allergens,
) -> IngestionResult:
    result = IngestionResult()

    menu_items = _extract_json_var(html, "Bamco.menu_items")
    if not menu_items:
        # No items right now (e.g. this café is closed for the summer) —
        # not an error, just nothing to ingest from this location today.
        return result

    for daypart in _extract_dayparts(html).values():
        meal_period = _normalize_daypart_label(daypart.get("label"))
        available_from = daypart.get("starttime")
        available_until = daypart.get("endtime")

        for station in daypart.get("stations", []):
            station_name = station.get("label") or cafe_name
            for item_id in station.get("items", []):
                item = menu_items.get(item_id)
                if item is None:
                    continue

                name = item.get("label", "")
                ingredients_text = item.get("ingredients") or ""
                nutrition = {f: _nutrition_value(item, _NUTRITION_KEY_ALIASES[f]) for f in _NUTRITION_FIELDS}
                allergens = _extract_allergens(item)

                estimated_fields: list[str] = []
                missing_nutrition = [f for f in _NUTRITION_FIELDS if _parse_numeric(nutrition[f]) is None]
                if missing_nutrition:
                    estimates = estimate_nutrition(name, ingredients_text, missing_nutrition)
                    for field, value in estimates.items():
                        nutrition[field] = value
                        estimated_fields.append(field)

                allergen_note: dict | None = None
                if allergens is None and ingredients_text:
                    extraction = extract_allergens_llm(name, ingredients_text)
                    if extraction is not None and extraction.confidence >= ALLERGEN_CONFIDENCE_THRESHOLD:
                        allergens = extraction.allergens
                        allergen_note = {"allergens": extraction.allergens, "confidence": extraction.confidence}

                raw_record = {
                    "cafe": cafe_name,
                    "station": station_name,
                    "daypart": daypart.get("label"),
                    "item": item,
                }
                try:
                    normalized = build_menu_item(
                        id=stable_item_id(name, station_name),
                        name=name,
                        station=station_name,
                        meal_period=meal_period,
                        available_from=available_from,
                        available_until=available_until,
                        calories=nutrition["calories"],
                        protein_g=nutrition["protein_g"],
                        carbs_g=nutrition["carbs_g"],
                        fat_g=nutrition["fat_g"],
                        fiber_g=nutrition["fiber_g"],
                        sodium_mg=nutrition["sodium_mg"],
                        sugar_g=nutrition["sugar_g"],
                        price=_extract_price(item),
                        allergens=allergens,
                        dietary_tags=_extract_dietary_tags(item),
                        ingredients=[ingredients_text] if ingredients_text else [],
                        description=item.get("description") or None,
                    )
                    if estimated_fields:
                        normalized["estimated_fields"] = estimated_fields
                    result.items.append(normalized)
                    if allergen_note is not None:
                        result.review_notes.append(ReviewNote(
                            item_id=normalized["id"],
                            reason="AI-extracted allergens, please verify",
                            detail={**allergen_note, "name": name, "ingredients": ingredients_text},
                        ))
                except MenuItemValidationError as e:
                    result.rejected.append(RejectedRecord(raw=raw_record, reason=str(e)))

    return result


def _default_fetch(url: str) -> str:
    resp = httpx.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_FETCH_TIMEOUT_S)
    resp.raise_for_status()
    return resp.text


def fetch_campus_menu(
    campus: CampusConfig,
    http_get: Callable[[str], str] | None = None,
    estimate_nutrition: Callable[[str, str, list[str]], dict[str, float]] = _default_estimate_nutrition,
    extract_allergens_llm: Callable[[str, str], Any] = _default_extract_allergens,
) -> IngestionResult:
    """Fetches and normalizes today's live menu for every café configured
    for this campus. `http_get` is an injectable `url -> html` fetcher —
    tests supply a fixture-backed fake instead of hitting the real network,
    the same dependency-injection pattern services/auth.py uses for
    verify_id_token. `estimate_nutrition`/`extract_allergens_llm` default to
    the real Claude-backed functions in llm_enrichment.py (themselves a
    safe no-op with no ANTHROPIC_API_KEY configured) — tests override them
    the same way, to control exactly what "Claude" returns without any
    network or credentials."""
    fetch = http_get or _default_fetch
    result = IngestionResult()

    for cafe in campus.cafes:
        url = f"{campus.base_url}/cafe/{cafe.slug}/"
        try:
            html = fetch(url)
        except Exception as e:
            result.rejected.append(RejectedRecord(
                raw={"cafe": cafe.slug, "url": url},
                reason=f"fetch failed: {e}",
            ))
            continue

        cafe_result = _parse_cafe_html(html, cafe.name, estimate_nutrition, extract_allergens_llm)
        result.items.extend(cafe_result.items)
        result.rejected.extend(cafe_result.rejected)
        result.review_notes.extend(cafe_result.review_notes)

    return result
