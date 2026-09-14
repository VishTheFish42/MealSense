"""
Tests menu_store.py against a real local Firestore emulator, not a mock —
same reasoning as mealsense-app/tests/firestore.rules.test.js: our own
read/write logic is worth testing against actual Firestore semantics
(subcollection queries, batch writes), not a hand-rolled stand-in for them.

Requires the emulator running first:
    cd mealsense-app && npx firebase emulators:start --only firestore
(defaults to 127.0.0.1:8080, matching firebase.json). Skips cleanly with
a clear reason if it isn't reachable, rather than a raw connection error.
"""
import socket
import uuid

import pytest

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


def _unique_served_on() -> str:
    """A unique per-test document id under menus/ — the emulator persists
    state across the whole pytest run, so a shared literal date would let
    one test's writes leak into another's assertions."""
    return f"test-{uuid.uuid4().hex}"


def test_get_menu_for_date_falls_back_to_sample_menu_when_empty():
    from services.menu_store import get_menu_for_date
    from data.sample_menu import SAMPLE_MENU

    menu = get_menu_for_date(_unique_served_on())  # nothing has ever written to this one
    assert menu == SAMPLE_MENU


def test_write_then_read_round_trips_items():
    from services.menu_store import get_menu_for_date, write_menu_items

    served_on = _unique_served_on()
    items = [
        {"id": "item-a", "name": "Test Dish A", "meal_period": "lunch", "allergens": []},
        {"id": "item-b", "name": "Test Dish B", "meal_period": "lunch", "allergens": ["dairy"]},
    ]
    write_menu_items(served_on, items)

    menu = get_menu_for_date(served_on)
    assert len(menu) == 2
    names = {item["name"] for item in menu}
    assert names == {"Test Dish A", "Test Dish B"}


def test_re_uploading_same_day_overwrites_matching_ids_not_duplicates():
    from services.menu_store import get_menu_for_date, write_menu_items

    served_on = _unique_served_on()
    write_menu_items(served_on, [{"id": "dish-1", "name": "Original Name", "allergens": []}])
    write_menu_items(served_on, [{"id": "dish-1", "name": "Updated Name", "allergens": []}])

    menu = get_menu_for_date(served_on)
    assert len(menu) == 1
    assert menu[0]["name"] == "Updated Name"


def test_write_menu_items_handles_empty_list_without_error():
    from services.menu_store import write_menu_items
    write_menu_items(_unique_served_on(), [])  # should not raise


# ── set_item_availability (README §9.5, design-spec.md §7.3) ───────────────

def test_set_item_availability_marks_item_sold_out():
    from services.menu_store import get_menu_for_date, set_item_availability, write_menu_items

    served_on = _unique_served_on()
    write_menu_items(served_on, [{"id": "dish-1", "name": "Soup", "allergens": []}])

    set_item_availability(served_on, "dish-1", True)

    menu = get_menu_for_date(served_on)
    assert menu[0]["sold_out"] is True


def test_set_item_availability_can_toggle_back_to_available():
    from services.menu_store import get_menu_for_date, set_item_availability, write_menu_items

    served_on = _unique_served_on()
    write_menu_items(served_on, [{"id": "dish-1", "name": "Soup", "allergens": []}])
    set_item_availability(served_on, "dish-1", True)

    set_item_availability(served_on, "dish-1", False)

    menu = get_menu_for_date(served_on)
    assert menu[0]["sold_out"] is False


def test_set_item_availability_raises_not_found_for_unknown_item():
    from google.api_core.exceptions import NotFound
    from services.menu_store import set_item_availability

    with pytest.raises(NotFound):
        set_item_availability(_unique_served_on(), "does-not-exist", True)


def test_re_uploading_preserves_sold_out_status_via_merge():
    """The core behavioral fix this feature needed: re-syncing a vendor
    feed or re-uploading a CSV mid-day must not silently un-mark a dish
    staff already flagged sold out, since ingestion itself never sets or
    clears this field."""
    from services.menu_store import get_menu_for_date, set_item_availability, write_menu_items

    served_on = _unique_served_on()
    write_menu_items(served_on, [{"id": "dish-1", "name": "Original Name", "allergens": []}])
    set_item_availability(served_on, "dish-1", True)

    write_menu_items(served_on, [{"id": "dish-1", "name": "Updated Name", "allergens": []}])

    menu = get_menu_for_date(served_on)
    assert menu[0]["name"] == "Updated Name"
    assert menu[0]["sold_out"] is True
