"""
Tests services/analytics_aggregation.py against a real local Firestore
emulator, same reasoning as test_menu_store.py. Requires the emulator
running first:
    cd mealsense-app && npx firebase emulators:start --only firestore
Skips cleanly with a clear reason if it isn't reachable.
"""
import socket
import uuid

import pytest

from services.analytics_aggregation import common_dietary_constraints, most_recommended_items

EMULATOR_HOST = "127.0.0.1"
EMULATOR_PORT = 8080


def _emulator_is_running() -> bool:
    try:
        with socket.create_connection((EMULATOR_HOST, EMULATOR_PORT), timeout=0.5):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _emulator_is_running(),
    reason=(
        "Firestore emulator not reachable at 127.0.0.1:8080 — start it with "
        "`cd mealsense-app && npx firebase emulators:start --only firestore` first"
    ),
)


@pytest.fixture(autouse=True)
def emulator_env(monkeypatch):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", f"{EMULATOR_HOST}:{EMULATOR_PORT}")
    from services import firestore_client
    firestore_client.reset_firestore_client()
    yield
    firestore_client.reset_firestore_client()


def _uid() -> str:
    return f"test-{uuid.uuid4().hex}"


# ── most_recommended_items ──────────────────────────────────────────────

def test_most_recommended_items_counts_and_sorts_descending():
    from services.recommendation_history import write_recommendation
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    # A distinct, unique-per-run item id so this test's own count is
    # verifiable exactly, despite recommendation_history being a shared
    # collection other tests also write to in the same emulator run.
    popular_id = f"item-{uuid.uuid4().hex}"
    rare_id = f"item-{uuid.uuid4().hex}"
    student = _uid()

    write_recommendation(student, popular_id, "Popular Dish", 90.0, "lunch")
    write_recommendation(student, popular_id, "Popular Dish", 85.0, "lunch")
    write_recommendation(student, popular_id, "Popular Dish", 88.0, "lunch")
    write_recommendation(student, rare_id, "Rare Dish", 60.0, "lunch")

    results = most_recommended_items(db, limit=50)
    by_id = {r["menu_item_id"]: r for r in results}

    assert by_id[popular_id]["count"] == 3
    assert by_id[popular_id]["name"] == "Popular Dish"
    assert by_id[rare_id]["count"] == 1

    popular_rank = next(i for i, r in enumerate(results) if r["menu_item_id"] == popular_id)
    rare_rank = next(i for i, r in enumerate(results) if r["menu_item_id"] == rare_id)
    assert popular_rank < rare_rank


def test_most_recommended_items_respects_limit():
    from services.recommendation_history import write_recommendation
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    student = _uid()
    for _ in range(5):
        write_recommendation(student, f"item-{uuid.uuid4().hex}", "Unique Dish", 70.0, "lunch")

    results = most_recommended_items(db, limit=2)
    assert len(results) <= 2


def test_most_recommended_items_skips_records_with_no_menu_item_id():
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    db.collection("recommendation_history").add({
        "studentId": _uid(), "score": 80.0, "mealPeriod": "lunch", "feedback": None,
        # no menuItemId at all — a malformed record shouldn't crash the report
    })

    results = most_recommended_items(db, limit=50)  # must not raise
    assert all(r["menu_item_id"] for r in results)


def test_most_recommended_items_falls_back_to_id_when_name_missing():
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    item_id = f"item-{uuid.uuid4().hex}"
    db.collection("recommendation_history").add({
        "studentId": _uid(), "menuItemId": item_id, "score": 80.0,
        "mealPeriod": "lunch", "feedback": None,
        # no menuItemName — simulates a record from before this field existed
    })

    results = most_recommended_items(db, limit=50)
    match = next(r for r in results if r["menu_item_id"] == item_id)
    assert match["name"] == item_id


# ── common_dietary_constraints ──────────────────────────────────────────

def test_common_dietary_constraints_tallies_students_only():
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    unique_allergen = f"allergen-{uuid.uuid4().hex[:8]}"
    student_uid = _uid()
    kitchen_uid = _uid()

    db.collection("users").document(student_uid).set({
        "role": "student", "allergies": [unique_allergen], "dietaryIdentity": ["vegetarian"],
        "conditions": [], "nutritionalFocus": ["high_protein"],
    })
    db.collection("users").document(kitchen_uid).set({
        "role": "kitchen", "allergies": [unique_allergen], "dietaryIdentity": [],
        "conditions": [], "nutritionalFocus": [],
    })

    result = common_dietary_constraints(db)
    allergy_values = {row["value"]: row["count"] for row in result["allergies"]}
    # Only the student's copy should be counted, never the kitchen account's.
    assert allergy_values[unique_allergen] == 1


def test_common_dietary_constraints_excludes_none_sentinel():
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    db.collection("users").document(_uid()).set({
        "role": "student", "allergies": [], "dietaryIdentity": ["none"],
        "conditions": ["none"], "nutritionalFocus": [],
    })

    result = common_dietary_constraints(db)
    assert all(row["value"] != "none" for row in result["dietary_identity"])
    assert all(row["value"] != "none" for row in result["conditions"])


def test_common_dietary_constraints_returns_all_four_categories():
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    result = common_dietary_constraints(db)
    assert set(result.keys()) == {"allergies", "dietary_identity", "conditions", "nutritional_focus"}
