import pytest

from services.menu_ingestion.schema import (
    MenuItemValidationError, build_menu_item, stable_item_id, _parse_numeric,
)
from services.menu_ingestion.csv_adapter import CsvMenuAdapter
from services.menu_ingestion.messy_json_adapter import MessyJsonMenuAdapter


# ── schema.py: numeric parsing ─────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    (420, 420.0),
    (420.5, 420.5),
    ("420", 420.0),
    ("420.5", 420.5),
    ("420 cal", 420.0),
    ("38g", 38.0),
    ("410mg", 410.0),
    ("  42  ", 42.0),
])
def test_parse_numeric_accepts_common_shapes(raw, expected):
    assert _parse_numeric(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "cal", "n/a", True, False, [1, 2], {"a": 1}])
def test_parse_numeric_rejects_unusable_values(raw):
    assert _parse_numeric(raw) is None


# ── schema.py: build_menu_item ─────────────────────────────────────────────

def _valid_kwargs(**overrides):
    kwargs = dict(
        id="abc123", name="Grilled Chicken", meal_period="lunch",
        calories=450, protein_g=38, carbs_g=20, fat_g=12, fiber_g=3,
        sodium_mg=410, sugar_g=2, price=9.50, allergens=[],
    )
    kwargs.update(overrides)
    return kwargs


def test_build_menu_item_valid():
    item = build_menu_item(**_valid_kwargs(allergens=["dairy"], dietary_tags=["halal"]))
    assert item["name"] == "Grilled Chicken"
    assert item["allergens"] == ["dairy"]
    assert item["dietary_tags"] == ["halal"]
    assert item["calories"] == 450.0
    assert item["price"] == 9.50


def test_build_menu_item_rejects_missing_name():
    with pytest.raises(MenuItemValidationError, match="name"):
        build_menu_item(**_valid_kwargs(name=""))


def test_build_menu_item_rejects_invalid_meal_period():
    with pytest.raises(MenuItemValidationError, match="meal_period"):
        build_menu_item(**_valid_kwargs(meal_period="brunch"))


def test_build_menu_item_rejects_missing_allergen_data():
    """The core safety invariant: allergens=None (source never told us)
    must be rejected, never silently treated as zero allergens."""
    with pytest.raises(MenuItemValidationError, match="allergen"):
        build_menu_item(**_valid_kwargs(allergens=None))


def test_build_menu_item_accepts_explicit_empty_allergens():
    """allergens=[] means verified-safe, not missing — must be accepted."""
    item = build_menu_item(**_valid_kwargs(allergens=[]))
    assert item["allergens"] == []


def test_build_menu_item_rejects_missing_numeric_field():
    with pytest.raises(MenuItemValidationError, match="calories"):
        build_menu_item(**_valid_kwargs(calories=None))


def test_build_menu_item_rejects_unparseable_numeric_field():
    with pytest.raises(MenuItemValidationError, match="protein_g"):
        build_menu_item(**_valid_kwargs(protein_g="unknown"))


def test_build_menu_item_rejects_missing_price():
    """price is required at ingestion, same as the nutrition fields — a
    priceless item must never silently reach the cart, where JS coerces
    `null * quantity` to 0 and the order would place as free."""
    with pytest.raises(MenuItemValidationError, match="price"):
        build_menu_item(**_valid_kwargs(price=None))


def test_build_menu_item_rejects_unparseable_price():
    with pytest.raises(MenuItemValidationError, match="price"):
        build_menu_item(**_valid_kwargs(price="unknown"))


def test_build_menu_item_parses_price_with_currency_symbol():
    item = build_menu_item(**_valid_kwargs(price="$9.50"))
    assert item["price"] == 9.50


def test_build_menu_item_lowercases_allergens_and_tags():
    item = build_menu_item(**_valid_kwargs(allergens=["DAIRY", " Nuts "], dietary_tags=["Halal"]))
    assert item["allergens"] == ["dairy", "nuts"]
    assert item["dietary_tags"] == ["halal"]


# ── schema.py: stable_item_id ──────────────────────────────────────────────

def test_stable_item_id_deterministic():
    assert stable_item_id("Grilled Chicken", "Grill") == stable_item_id("Grilled Chicken", "Grill")


def test_stable_item_id_case_and_whitespace_insensitive():
    assert stable_item_id("Grilled Chicken", "Grill") == stable_item_id("  grilled chicken  ", "GRILL")


def test_stable_item_id_differs_for_different_items():
    assert stable_item_id("Grilled Chicken", "Grill") != stable_item_id("Grilled Salmon", "Grill")


def test_stable_item_id_differs_by_station():
    assert stable_item_id("Salad", "Salad Bar") != stable_item_id("Salad", "Hot Entrees")


# ── CSV adapter ─────────────────────────────────────────────────────────────

CSV_HEADER = (
    "name,station,meal_period,available_from,available_until,served_on,"
    "calories,protein_g,carbs_g,fat_g,fiber_g,sodium_mg,sugar_g,price,"
    "allergens,dietary_tags,ingredients\n"
)


def test_csv_adapter_normalizes_valid_row():
    csv_text = CSV_HEADER + (
        "Grilled Chicken,Grill,lunch,11:00,15:00,2026-09-08,"
        "450,38,20,12,3,410,2,9.50,"
        "dairy|gluten,halal|gluten-free,chicken|olive oil\n"
    )
    result = CsvMenuAdapter().normalize(csv_text)
    assert result.accepted_count == 1
    assert result.rejected_count == 0
    item = result.items[0]
    assert item["name"] == "Grilled Chicken"
    assert item["allergens"] == ["dairy", "gluten"]
    assert item["dietary_tags"] == ["halal", "gluten-free"]
    assert item["ingredients"] == ["chicken", "olive oil"]
    assert item["calories"] == 450.0
    assert item["price"] == 9.50


def test_csv_adapter_rejects_row_with_missing_price_column():
    csv_text = (
        "name,station,meal_period,calories,protein_g,carbs_g,fat_g,fiber_g,"
        "sodium_mg,sugar_g,allergens\n"
        "Grilled Chicken,Grill,lunch,450,38,20,12,3,410,2,dairy\n"
    )
    result = CsvMenuAdapter().normalize(csv_text)
    assert result.accepted_count == 0
    assert result.rejected_count == 1
    assert "price" in result.rejected[0].reason


def test_csv_adapter_missing_allergen_column_rejects_all_rows():
    csv_text = (
        "name,station,meal_period,calories,protein_g,carbs_g,fat_g,fiber_g,sodium_mg,sugar_g\n"
        "Grilled Chicken,Grill,lunch,450,38,20,12,3,410,2\n"
    )
    result = CsvMenuAdapter().normalize(csv_text)
    assert result.accepted_count == 0
    assert result.rejected_count == 1
    assert "allergen" in result.rejected[0].reason


def test_csv_adapter_blank_allergen_cell_is_explicit_empty():
    csv_text = CSV_HEADER + (
        "Plain Rice,Grill,lunch,11:00,15:00,2026-09-08,"
        "200,4,45,0,1,10,0,3.00,,,\n"
    )
    result = CsvMenuAdapter().normalize(csv_text)
    assert result.accepted_count == 1
    assert result.items[0]["allergens"] == []


def test_csv_adapter_rejects_row_with_bad_numeric_field():
    csv_text = CSV_HEADER + (
        "Mystery Item,Grill,lunch,11:00,15:00,2026-09-08,"
        "not-a-number,38,20,12,3,410,2,5.00,dairy,,\n"
    )
    result = CsvMenuAdapter().normalize(csv_text)
    assert result.accepted_count == 0
    assert result.rejected_count == 1
    assert "calories" in result.rejected[0].reason


def test_csv_adapter_same_dish_gets_same_id_across_ingestions():
    csv_text = CSV_HEADER + (
        "Grilled Chicken,Grill,lunch,11:00,15:00,2026-09-08,450,38,20,12,3,410,2,9.50,dairy,,\n"
    )
    csv_text_next_day = CSV_HEADER + (
        "Grilled Chicken,Grill,lunch,11:00,15:00,2026-09-09,450,38,20,12,3,410,2,9.50,dairy,,\n"
    )
    id_day1 = CsvMenuAdapter().normalize(csv_text).items[0]["id"]
    id_day2 = CsvMenuAdapter().normalize(csv_text_next_day).items[0]["id"]
    assert id_day1 == id_day2


# ── Messy JSON adapter ───────────────────────────────────────────────────────

def test_messy_json_adapter_normalizes_alternate_keys_and_units():
    raw = [{
        "ItemName": "Grilled Chicken",
        "Station": "Grill",
        "Meal": "Lunch",
        "Cals": "450 cal",
        "Protein": "38g",
        "Carbs": "20g",
        "Fat": "12g",
        "Fiber": "3g",
        "Sodium": "410mg",
        "Sugar": "2g",
        "Price": "$9.50",
        "Allergens": "Dairy, Gluten",
        "Tags": "Halal, Gluten-Free",
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    assert result.accepted_count == 1
    item = result.items[0]
    assert item["name"] == "Grilled Chicken"
    assert item["meal_period"] == "lunch"
    assert item["calories"] == 450.0
    assert item["protein_g"] == 38.0
    assert item["sodium_mg"] == 410.0
    assert item["price"] == 9.50
    assert item["allergens"] == ["dairy", "gluten"]
    assert item["dietary_tags"] == ["halal", "gluten-free"]


def test_messy_json_adapter_passes_through_availability_window():
    raw = [{
        "ItemName": "Grilled Chicken", "Meal": "lunch",
        "Cals": 450, "Protein": 38, "Carbs": 20, "Fat": 12, "Fiber": 3,
        "Sodium": 410, "Sugar": 2, "Price": 9.50, "Allergens": "dairy",
        "AvailableFrom": "11:00", "AvailableUntil": "15:00",
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    assert result.accepted_count == 1
    item = result.items[0]
    assert item["available_from"] == "11:00"
    assert item["available_until"] == "15:00"


def test_messy_json_adapter_availability_window_defaults_to_none_when_absent():
    raw = [{
        "ItemName": "Grilled Chicken", "Meal": "lunch",
        "Cals": 450, "Protein": 38, "Carbs": 20, "Fat": 12, "Fiber": 3,
        "Sodium": 410, "Sugar": 2, "Price": 9.50, "Allergens": "dairy",
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    item = result.items[0]
    assert item["available_from"] is None
    assert item["available_until"] is None


def test_messy_json_adapter_passes_through_ingredients_and_description():
    raw = [{
        "ItemName": "Grilled Chicken", "Meal": "lunch",
        "Cals": 450, "Protein": 38, "Carbs": 20, "Fat": 12, "Fiber": 3,
        "Sodium": 410, "Sugar": 2, "Price": 9.50, "Allergens": "dairy",
        "Ingredients": "chicken, olive oil, garlic",
        "Description": "Herb-marinated grilled chicken.",
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    item = result.items[0]
    assert item["ingredients"] == ["chicken", "olive oil", "garlic"]
    assert item["description"] == "Herb-marinated grilled chicken."


@pytest.mark.parametrize("raw_period,expected", [
    ("Lunch", "lunch"),
    ("BREAKFAST", "breakfast"),
    ("All Day", "all_day"),
    ("ALLDAY", "all_day"),
])
def test_messy_json_adapter_normalizes_meal_period_aliases(raw_period, expected):
    raw = [{
        "ItemName": "Item", "Meal": raw_period,
        "Cals": 100, "Protein": 1, "Carbs": 1, "Fat": 1, "Fiber": 1,
        "Sodium": 1, "Sugar": 1, "Price": 5, "Allergens": "none",
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    assert result.accepted_count == 1
    assert result.items[0]["meal_period"] == expected


def test_messy_json_adapter_rejects_missing_allergen_key():
    raw = [{
        "ItemName": "Mystery Dish", "Meal": "lunch",
        "Cals": 100, "Protein": 1, "Carbs": 1, "Fat": 1, "Fiber": 1,
        "Sodium": 1, "Sugar": 1,
        # no "Allergens" key at all
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    assert result.accepted_count == 0
    assert result.rejected_count == 1
    assert "allergen" in result.rejected[0].reason


@pytest.mark.parametrize("none_spelling", ["none", "None", "N/A", "-", ""])
def test_messy_json_adapter_treats_none_spellings_as_explicit_empty(none_spelling):
    raw = [{
        "ItemName": "Plain Rice", "Meal": "lunch",
        "Cals": 100, "Protein": 1, "Carbs": 1, "Fat": 1, "Fiber": 1,
        "Sodium": 1, "Sugar": 1, "Price": 5, "Allergens": none_spelling,
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    assert result.accepted_count == 1
    assert result.items[0]["allergens"] == []


def test_messy_json_adapter_partial_batch_failure_does_not_drop_valid_items():
    raw = [
        {
            "ItemName": "Good Item", "Meal": "lunch",
            "Cals": 100, "Protein": 1, "Carbs": 1, "Fat": 1, "Fiber": 1,
            "Sodium": 1, "Sugar": 1, "Price": 5, "Allergens": "none",
        },
        {
            "ItemName": "Bad Item", "Meal": "lunch",
            "Cals": 100, "Protein": 1, "Carbs": 1, "Fat": 1, "Fiber": 1,
            "Sodium": 1, "Sugar": 1,
            # missing Allergens entirely
        },
    ]
    result = MessyJsonMenuAdapter().normalize(raw)
    assert result.accepted_count == 1
    assert result.rejected_count == 1
    assert result.items[0]["name"] == "Good Item"


def test_messy_json_adapter_rejects_non_string_meal_period():
    raw = [{
        "ItemName": "Item", "Meal": 3,
        "Cals": 100, "Protein": 1, "Carbs": 1, "Fat": 1, "Fiber": 1,
        "Sodium": 1, "Sugar": 1, "Allergens": "none",
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    assert result.accepted_count == 0
    assert "meal_period" in result.rejected[0].reason


def test_messy_json_adapter_accepts_allergens_already_as_a_list():
    raw = [{
        "ItemName": "Item", "Meal": "lunch",
        "Cals": 100, "Protein": 1, "Carbs": 1, "Fat": 1, "Fiber": 1,
        "Sodium": 1, "Sugar": 1, "Price": 5, "Allergens": ["Dairy", " nuts "],
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    assert result.accepted_count == 1
    assert result.items[0]["allergens"] == ["dairy", "nuts"]


def test_messy_json_adapter_rejects_missing_price():
    raw = [{
        "ItemName": "Item", "Meal": "lunch",
        "Cals": 100, "Protein": 1, "Carbs": 1, "Fat": 1, "Fiber": 1,
        "Sodium": 1, "Sugar": 1, "Allergens": "none",
        # no "Price"/"price"/"cost" key at all
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    assert result.accepted_count == 0
    assert "price" in result.rejected[0].reason


def test_messy_json_adapter_accepts_cost_key_alias():
    raw = [{
        "ItemName": "Item", "Meal": "lunch",
        "Cals": 100, "Protein": 1, "Carbs": 1, "Fat": 1, "Fiber": 1,
        "Sodium": 1, "Sugar": 1, "Allergens": "none", "cost": "7.25",
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    assert result.accepted_count == 1
    assert result.items[0]["price"] == 7.25


def test_messy_json_adapter_rejects_unrecognized_allergen_value_type():
    raw = [{
        "ItemName": "Item", "Meal": "lunch",
        "Cals": 100, "Protein": 1, "Carbs": 1, "Fat": 1, "Fiber": 1,
        "Sodium": 1, "Sugar": 1, "Allergens": 42,
    }]
    result = MessyJsonMenuAdapter().normalize(raw)
    assert result.accepted_count == 0
    assert "allergen" in result.rejected[0].reason


def test_same_dish_gets_same_id_across_different_adapters():
    """The whole point of the canonical schema: two campuses' completely
    different feed shapes for 'the same kind of dish' converge on a
    comparable identity once normalized."""
    csv_text = CSV_HEADER + (
        "Grilled Chicken,Grill,lunch,11:00,15:00,2026-09-08,450,38,20,12,3,410,2,9.50,dairy,,\n"
    )
    csv_id = CsvMenuAdapter().normalize(csv_text).items[0]["id"]

    json_raw = [{
        "ItemName": "Grilled Chicken", "Station": "Grill", "Meal": "lunch",
        "Cals": 450, "Protein": 38, "Carbs": 20, "Fat": 12, "Fiber": 3,
        "Sodium": 410, "Sugar": 2, "Price": 9.50, "Allergens": "dairy",
    }]
    json_id = MessyJsonMenuAdapter().normalize(json_raw).items[0]["id"]

    assert csv_id == json_id
