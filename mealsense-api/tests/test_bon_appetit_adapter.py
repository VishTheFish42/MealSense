"""
Tests for services/vendor_ingestion/bon_appetit.py. The HTML fixtures below
mirror the real `Bamco.dayparts` / `Bamco.menu_items` shape confirmed
against scudining.cafebonappetit.com (Santa Clara University's live Bon
Appétit site) on 2026-09-11 — same field names, same nesting — just
trimmed to the handful of items each test needs. No test hits the real
network: fetch_campus_menu takes an injectable http_get, the same
dependency-injection pattern services/auth.py uses for verify_id_token.
"""
import json

import pytest

from services.vendor_ingestion.bon_appetit import (
    _extract_allergens,
    _extract_dietary_tags,
    _extract_price,
    _normalize_daypart_label,
    _parse_cafe_html,
    fetch_campus_menu,
)
from services.vendor_ingestion.campus_config import CafeConfig, CampusConfig


def _nutrition(**overrides):
    values = {
        "calories": "450", "proteinContent": "38", "carbohydrateContent": "20",
        "fatContent": "12", "fiberContent": "3", "sodiumContent": "410", "sugarContent": "2",
    }
    values.update(overrides)
    return {k: {"label": k, "value": v, "unit": ""} for k, v in values.items()}


def _item(id_, label, cor_icons=None, price="$9.50", ingredients="", description=""):
    ordered = {
        str(i): {"id": str(i), "label": label_}
        for i, label_ in enumerate(cor_icons or [])
    }
    return {
        "id": id_,
        "label": label,
        "ordered_cor_icon": ordered,
        "nutrition_details": _nutrition(),
        "sizes": [{"size": "1 serving", "portion": "1", "uom": "ea", "price": price}],
        "ingredients": ingredients,
        "description": description,
    }


def _cafe_html(daypart_label, start, end, items_by_id, stations):
    """stations: list of (station_label, [item_ids])."""
    daypart_obj = {
        "starttime": start, "endtime": end, "id": "115", "label": daypart_label,
        "stations": [{"label": label, "items": ids} for label, ids in stations],
    }
    return (
        "<html><body><script>"
        "Bamco.dayparts = Bamco.dayparts || {};"
        f"Bamco.dayparts['115'] = {json.dumps(daypart_obj)};"
        f"Bamco.menu_items = {json.dumps(items_by_id)};"
        "</script></body></html>"
    )


# ── _normalize_daypart_label ────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("Breakfast", "breakfast"),
    ("BRUNCH", "breakfast"),
    ("Lunch", "lunch"),
    ("Dinner", "dinner"),
    ("Late Night", "dinner"),
    ("All Day", "all_day"),
    ("Mission Bakery Cafe", "all_day"),
    ("Summer Schedule", "all_day"),
    (None, "all_day"),
    (3, "all_day"),
])
def test_normalize_daypart_label(raw, expected):
    assert _normalize_daypart_label(raw) == expected


# ── _extract_allergens: the safety-critical piece ──────────────────────────

def test_extract_allergens_maps_known_cor_icons():
    item = _item("1", "Latte", cor_icons=["Milk"])
    assert _extract_allergens(item) == ["dairy"]


def test_extract_allergens_maps_multiple_icons():
    item = _item("1", "Sesame Tofu", cor_icons=["Sesame", "Soy"])
    assert _extract_allergens(item) == ["sesame", "soy"]


def test_extract_allergens_returns_none_when_no_allergen_icon_present():
    """The core safety decision (tasks.md 3.4): zero icons means unknown,
    not verified-safe — must return None, never []."""
    item = _item("1", "Mystery Item", cor_icons=[])
    assert _extract_allergens(item) is None


def test_extract_allergens_ignores_non_allergen_cor_icons():
    """Vegan/Vegetarian icons don't imply anything about the 9 tracked
    allergens — an item with only those icons is still 'unknown'."""
    item = _item("1", "Vegan Salad", cor_icons=["Vegan", "Vegetarian"])
    assert _extract_allergens(item) is None


def test_extract_dietary_tags_maps_known_icons():
    item = _item("1", "Vegan Salad", cor_icons=["Vegan", "Vegetarian"])
    assert _extract_dietary_tags(item) == ["vegan", "vegetarian"]


def test_extract_dietary_tags_empty_when_no_diet_icons():
    item = _item("1", "Latte", cor_icons=["Milk"])
    assert _extract_dietary_tags(item) == []


# ── _extract_price ──────────────────────────────────────────────────────────

def test_extract_price_uses_first_size():
    item = _item("1", "Coffee", price="$3.55")
    assert _extract_price(item) == "$3.55"


def test_extract_price_falls_back_to_raw_price_string_regex():
    item = _item("1", "Coffee")
    item["sizes"] = []
    item["price"] = "12 fl oz - $3.55  16 fl oz - $3.75"
    assert _extract_price(item) == "$3.55"


def test_extract_price_none_when_unavailable():
    item = _item("1", "Mystery")
    item["sizes"] = []
    item["price"] = None
    assert _extract_price(item) is None


# ── _parse_cafe_html: end-to-end normalization ──────────────────────────────

def test_parse_cafe_html_accepts_item_with_allergen_icon():
    items = {"1001": _item("1001", "Grilled Chicken Bowl", cor_icons=["Milk"], price="$9.50",
                            ingredients="chicken, cream sauce")}
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("Hot Entrees", ["1001"])])

    result = _parse_cafe_html(html, "Benson Marketplace")

    assert result.accepted_count == 1
    assert result.rejected_count == 0
    item = result.items[0]
    assert item["name"] == "Grilled Chicken Bowl"
    assert item["station"] == "Hot Entrees"
    assert item["meal_period"] == "lunch"
    assert item["available_from"] == "11:00"
    assert item["available_until"] == "15:00"
    assert item["calories"] == 450.0
    assert item["protein_g"] == 38.0
    assert item["allergens"] == ["dairy"]
    assert item["price"] == 9.50
    assert item["ingredients"] == ["chicken, cream sauce"]


def test_parse_cafe_html_rejects_item_with_no_allergen_icon():
    items = {"1002": _item("1002", "Mystery Item", cor_icons=[])}
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("Hot Entrees", ["1002"])])

    result = _parse_cafe_html(html, "Benson Marketplace")

    assert result.accepted_count == 0
    assert result.rejected_count == 1
    rejected = result.rejected[0]
    assert "allergen" in rejected.reason
    assert rejected.raw["item"]["label"] == "Mystery Item"
    assert rejected.raw["station"] == "Hot Entrees"


def test_parse_cafe_html_accepted_and_rejected_items_coexist():
    items = {
        "1001": _item("1001", "Grilled Chicken Bowl", cor_icons=["Milk"]),
        "1002": _item("1002", "Mystery Item", cor_icons=[]),
    }
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("Hot Entrees", ["1001", "1002"])])

    result = _parse_cafe_html(html, "Benson Marketplace")

    assert result.accepted_count == 1
    assert result.rejected_count == 1


def test_parse_cafe_html_maps_dietary_tags_on_accepted_item():
    items = {"1003": _item("1003", "Sesame Tofu Bowl", cor_icons=["Sesame", "Vegan"])}
    html = _cafe_html("Dinner", "17:00", "21:00", items, [("Global Kitchen", ["1003"])])

    result = _parse_cafe_html(html, "Benson Marketplace")

    assert result.accepted_count == 1
    item = result.items[0]
    assert item["allergens"] == ["sesame"]
    assert item["dietary_tags"] == ["vegan"]


def test_parse_cafe_html_no_items_key_returns_empty_result():
    html = "<html><body><script>Bamco.dayparts = {};</script></body></html>"
    result = _parse_cafe_html(html, "Closed Cafe")
    assert result.accepted_count == 0
    assert result.rejected_count == 0


def test_parse_cafe_html_station_falls_back_to_cafe_name_when_unlabeled():
    items = {"1001": _item("1001", "Grilled Chicken", cor_icons=["Milk"])}
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("", ["1001"])])
    result = _parse_cafe_html(html, "Fresh Bytes")
    assert result.items[0]["station"] == "Fresh Bytes"


def test_parse_cafe_html_skips_item_id_missing_from_menu_items():
    """A station can reference an item id that isn't in the menu_items dict
    at all (e.g. an item removed mid-day) — should be silently skipped,
    not a crash, and shouldn't affect other items in the same station."""
    items = {"1001": _item("1001", "Grilled Chicken", cor_icons=["Milk"])}
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("Hot Entrees", ["1001", "9999"])])
    result = _parse_cafe_html(html, "Benson Marketplace")
    assert result.accepted_count == 1
    assert result.items[0]["name"] == "Grilled Chicken"


def test_extract_json_var_returns_none_for_malformed_json():
    from services.vendor_ingestion.bon_appetit import _extract_json_var
    html = "<script>Bamco.menu_items = {not valid json};</script>"
    assert _extract_json_var(html, "Bamco.menu_items") is None


def test_extract_json_var_returns_none_when_absent():
    from services.vendor_ingestion.bon_appetit import _extract_json_var
    assert _extract_json_var("<html></html>", "Bamco.menu_items") is None


# ── fetch_campus_menu: aggregation across cafés, injected fetcher ─────────

def _campus_with_two_cafes(html_by_url: dict[str, str]) -> CampusConfig:
    return CampusConfig(
        campus_id="test_campus",
        display_name="Test Campus",
        vendor="bon_appetit",
        base_url="https://test.cafebonappetit.com",
        cafes=(CafeConfig(slug="cafe-a", name="Cafe A"), CafeConfig(slug="cafe-b", name="Cafe B")),
    )


def test_fetch_campus_menu_aggregates_across_cafes():
    html_a = _cafe_html("Lunch", "11:00", "15:00",
                         {"1": _item("1", "Item A", cor_icons=["Milk"])},
                         [("Station A", ["1"])])
    html_b = _cafe_html("Dinner", "17:00", "21:00",
                         {"2": _item("2", "Item B", cor_icons=["Soy"])},
                         [("Station B", ["2"])])
    urls = {
        "https://test.cafebonappetit.com/cafe/cafe-a/": html_a,
        "https://test.cafebonappetit.com/cafe/cafe-b/": html_b,
    }
    campus = _campus_with_two_cafes(urls)

    result = fetch_campus_menu(campus, http_get=lambda url: urls[url])

    assert result.accepted_count == 2
    names = {i["name"] for i in result.items}
    assert names == {"Item A", "Item B"}


# ── LLM enrichment wiring (tasks.md 3.6, decided 2026-09-11) ───────────────
# Fake estimate/extract callables stand in for services/menu_ingestion/
# llm_enrichment.py — no network, no API key, full control over what
# "Claude" returns.

def _item_missing_calories_and_fiber(id_, label, cor_icons, ingredients):
    item = _item(id_, label, cor_icons=cor_icons, ingredients=ingredients)
    item["nutrition_details"]["calories"]["value"] = None
    item["nutrition_details"]["fiberContent"]["value"] = None
    return item


def test_parse_cafe_html_fills_missing_nutrition_via_injected_estimator():
    items = {"1": _item_missing_calories_and_fiber(
        "1", "Grilled Chicken", cor_icons=["Milk"], ingredients="chicken, cream",
    )}
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("Hot Entrees", ["1"])])

    def fake_estimate(name, ingredients, missing_fields):
        assert set(missing_fields) == {"calories", "fiber_g"}
        return {"calories": 480.0, "fiber_g": 2.0}

    result = _parse_cafe_html(html, "Benson Marketplace", estimate_nutrition=fake_estimate)

    assert result.accepted_count == 1
    item = result.items[0]
    assert item["calories"] == 480.0
    assert item["fiber_g"] == 2.0
    assert set(item["estimated_fields"]) == {"calories", "fiber_g"}


def test_parse_cafe_html_estimator_never_called_when_nutrition_complete():
    """The core scope constraint: zero API calls for a fully-complete
    record."""
    items = {"1": _item("1", "Grilled Chicken", cor_icons=["Milk"])}
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("Hot Entrees", ["1"])])

    def fake_estimate(name, ingredients, missing_fields):
        raise AssertionError("should never be called when nothing is missing")

    result = _parse_cafe_html(html, "Benson Marketplace", estimate_nutrition=fake_estimate)
    assert result.accepted_count == 1
    assert "estimated_fields" not in result.items[0]


def test_parse_cafe_html_still_rejects_when_estimator_leaves_a_gap():
    items = {"1": _item_missing_calories_and_fiber(
        "1", "Mystery Dish", cor_icons=["Milk"], ingredients="",
    )}
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("Hot Entrees", ["1"])])

    def fake_estimate(name, ingredients, missing_fields):
        return {"calories": 480.0}  # doesn't fill fiber_g

    result = _parse_cafe_html(html, "Benson Marketplace", estimate_nutrition=fake_estimate)

    assert result.accepted_count == 0
    assert result.rejected_count == 1
    assert "fiber_g" in result.rejected[0].reason


def test_parse_cafe_html_accepts_via_confident_allergen_extraction_and_queues_review():
    from services.menu_ingestion.llm_enrichment import AllergenExtractionResult

    items = {"1": _item("1", "Mystery Sesame Dish", cor_icons=[], ingredients="sesame paste, honey")}
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("Hot Entrees", ["1"])])

    def fake_extract(name, ingredients):
        return AllergenExtractionResult(allergens=["sesame"], confidence=0.95)

    result = _parse_cafe_html(html, "Benson Marketplace", extract_allergens_llm=fake_extract)

    assert result.accepted_count == 1
    assert result.rejected_count == 0
    item = result.items[0]
    assert item["allergens"] == ["sesame"]

    assert len(result.review_notes) == 1
    note = result.review_notes[0]
    assert note.item_id == item["id"]
    assert "verify" in note.reason.lower()
    assert note.detail["allergens"] == ["sesame"]
    assert note.detail["confidence"] == 0.95


def test_parse_cafe_html_rejects_low_confidence_allergen_extraction():
    from services.menu_ingestion.llm_enrichment import AllergenExtractionResult

    items = {"1": _item("1", "Mystery Dish", cor_icons=[], ingredients="mystery sauce")}
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("Hot Entrees", ["1"])])

    def fake_extract(name, ingredients):
        return AllergenExtractionResult(allergens=["soy"], confidence=0.5)  # below threshold

    result = _parse_cafe_html(html, "Benson Marketplace", extract_allergens_llm=fake_extract)

    assert result.accepted_count == 0
    assert result.rejected_count == 1
    assert result.review_notes == []


def test_parse_cafe_html_extractor_never_called_without_ingredient_text():
    items = {"1": _item("1", "Mystery Dish", cor_icons=[], ingredients="")}
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("Hot Entrees", ["1"])])

    def fake_extract(name, ingredients):
        raise AssertionError("should never be called with no ingredient text")

    result = _parse_cafe_html(html, "Benson Marketplace", extract_allergens_llm=fake_extract)
    assert result.accepted_count == 0
    assert result.rejected_count == 1


def test_parse_cafe_html_extractor_never_called_when_allergens_already_known():
    items = {"1": _item("1", "Grilled Chicken", cor_icons=["Milk"], ingredients="chicken, cream")}
    html = _cafe_html("Lunch", "11:00", "15:00", items, [("Hot Entrees", ["1"])])

    def fake_extract(name, ingredients):
        raise AssertionError("should never be called when a cor_icon already answered this")

    result = _parse_cafe_html(html, "Benson Marketplace", extract_allergens_llm=fake_extract)
    assert result.accepted_count == 1
    assert result.items[0]["allergens"] == ["dairy"]


def test_fetch_campus_menu_aggregates_review_notes_across_cafes():
    from services.menu_ingestion.llm_enrichment import AllergenExtractionResult

    html_a = _cafe_html("Lunch", "11:00", "15:00",
                         {"1": _item("1", "Sesame Item", cor_icons=[], ingredients="sesame paste")},
                         [("Station A", ["1"])])
    urls = {"https://test.cafebonappetit.com/cafe/cafe-a/": html_a,
            "https://test.cafebonappetit.com/cafe/cafe-b/": "<html></html>"}
    campus = _campus_with_two_cafes(urls)

    def fake_extract(name, ingredients):
        return AllergenExtractionResult(allergens=["sesame"], confidence=0.99)

    result = fetch_campus_menu(campus, http_get=lambda url: urls[url], extract_allergens_llm=fake_extract)

    assert result.accepted_count == 1
    assert len(result.review_notes) == 1


def test_fetch_campus_menu_records_fetch_failure_without_blowing_up_other_cafes():
    html_b = _cafe_html("Lunch", "11:00", "15:00",
                         {"2": _item("2", "Item B", cor_icons=["Soy"])},
                         [("Station B", ["2"])])

    def flaky_fetch(url: str) -> str:
        if "cafe-a" in url:
            raise TimeoutError("simulated network failure")
        return html_b

    campus = _campus_with_two_cafes({})
    result = fetch_campus_menu(campus, http_get=flaky_fetch)

    assert result.accepted_count == 1
    assert result.items[0]["name"] == "Item B"
    assert result.rejected_count == 1
    assert "fetch failed" in result.rejected[0].reason
