import pytest


def _base_profile(**overrides):
    profile = {
        "age": 21,
        "sex": "male",
        "weightKg": 70.0,
        "heightCm": 170.0,
        "activityLevel": "moderate",
        "healthGoal": "maintain",
        "allergies": [],
        "dietaryIdentity": [],
        "conditions": [],
    }
    profile.update(overrides)
    return profile


@pytest.fixture
def make_profile():
    """Factory for a valid student profile with sane defaults, overridable per test."""
    return _base_profile


@pytest.fixture
def minimal_profile():
    """A single minimal valid profile with no allergies, diet restrictions, or conditions."""
    return _base_profile()


def _menu_item(**overrides):
    item = {
        "id": "item_default",
        "name": "Test Item",
        "meal_period": "lunch",
        "calories": 500.0,
        "protein_g": 20.0,
        "carbs_g": 40.0,
        "fat_g": 15.0,
        "fiber_g": 5.0,
        "sodium_mg": 400.0,
        "sugar_g": 8.0,
        "allergens": [],
        "dietary_tags": [],
    }
    item.update(overrides)
    return item


@pytest.fixture
def make_item():
    """Factory for a valid menu item with sane defaults, overridable per test."""
    return _menu_item


@pytest.fixture
def fixture_menu():
    """A small menu covering the standard cases: an allergen item, a vegan item,
    a high-protein item, and an item outside the current meal period."""
    return [
        _menu_item(
            id="allergen_item",
            name="Peanut Noodles",
            meal_period="lunch",
            allergens=["nuts", "gluten"],
            dietary_tags=["vegetarian"],
        ),
        _menu_item(
            id="vegan_item",
            name="Vegan Buddha Bowl",
            meal_period="lunch",
            allergens=[],
            dietary_tags=["vegan", "vegetarian"],
            fiber_g=10.0,
        ),
        _menu_item(
            id="high_protein_item",
            name="Grilled Chicken",
            meal_period="lunch",
            protein_g=45.0,
            allergens=[],
            dietary_tags=[],
        ),
        _menu_item(
            id="off_period_item",
            name="Dinner Steak",
            meal_period="dinner",
            allergens=[],
            dietary_tags=[],
        ),
    ]
