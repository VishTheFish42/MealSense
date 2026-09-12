"""
Tests menu_review_queue.py against a real local Firestore emulator, same
reasoning as test_menu_store.py. Requires the emulator running first:
    cd mealsense-app && npx firebase emulators:start --only firestore
Skips cleanly with a clear reason if it isn't reachable.
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


def _unique_campus_id() -> str:
    return f"test-campus-{uuid.uuid4().hex}"


def test_write_review_items_returns_zero_for_empty_list():
    from services.menu_review_queue import write_review_items
    assert write_review_items(_unique_campus_id(), "2026-09-11", []) == 0


def test_write_then_read_round_trips_rejected_items():
    from services.menu_review_queue import write_review_items, get_review_queue

    campus_id = _unique_campus_id()
    rejected = [
        {"raw": {"item": {"label": "Mystery Item"}}, "reason": "missing allergen data"},
        {"raw": {"item": {"label": "Another Item"}}, "reason": "missing allergen data"},
    ]
    written = write_review_items(campus_id, "2026-09-11", rejected)
    assert written == 2

    queue = get_review_queue(campus_id=campus_id)
    assert len(queue) == 2
    reasons = {entry["reason"] for entry in queue}
    assert reasons == {"missing allergen data"}
    assert all(entry["resolved"] is False for entry in queue)
    assert all(entry["campusId"] == campus_id for entry in queue)


def test_get_review_queue_defaults_to_unresolved_only():
    from services.menu_review_queue import write_review_items, get_review_queue, resolve_review_item

    campus_id = _unique_campus_id()
    write_review_items(campus_id, "2026-09-11", [
        {"raw": {"item": {"label": "Item A"}}, "reason": "missing allergen data"},
        {"raw": {"item": {"label": "Item B"}}, "reason": "missing allergen data"},
    ])
    all_entries = get_review_queue(campus_id=campus_id, resolved=None)
    assert len(all_entries) == 2

    resolve_review_item(all_entries[0]["id"], allergens=["dairy"])

    unresolved = get_review_queue(campus_id=campus_id)
    assert len(unresolved) == 1
    assert unresolved[0]["id"] == all_entries[1]["id"]


def test_resolve_review_item_stores_confirmed_allergens():
    from services.menu_review_queue import write_review_items, get_review_queue, resolve_review_item

    campus_id = _unique_campus_id()
    write_review_items(campus_id, "2026-09-11", [
        {"raw": {"item": {"label": "Item A"}}, "reason": "missing allergen data"},
    ])
    entry = get_review_queue(campus_id=campus_id)[0]

    resolve_review_item(entry["id"], allergens=["gluten", "soy"])

    resolved_entries = get_review_queue(campus_id=campus_id, resolved=True)
    assert len(resolved_entries) == 1
    assert resolved_entries[0]["confirmedAllergens"] == ["gluten", "soy"]
