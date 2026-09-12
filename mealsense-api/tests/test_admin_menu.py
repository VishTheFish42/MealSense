"""
Route-level tests for POST /admin/menu/upload. Auth is bypassed via FastAPI's
dependency_overrides for the tests that exercise upload/reject behavior —
require_kitchen_role's own logic is covered separately in test_auth.py.
One test deliberately does NOT override the dependency, to prove auth is
actually wired into the route, not just implemented and unused.

Requires the Firestore emulator, same as test_menu_store.py — write_menu_items
hits real Firestore.
"""
import socket
import uuid

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture
def authed_client():
    from main import app
    from services.auth import require_kitchen_role

    app.dependency_overrides[require_kitchen_role] = lambda: "fake-kitchen-uid"
    yield TestClient(app)
    app.dependency_overrides.pop(require_kitchen_role, None)


CSV_HEADER = (
    "name,station,meal_period,available_from,available_until,served_on,"
    "calories,protein_g,carbs_g,fat_g,fiber_g,sodium_mg,sugar_g,price,"
    "allergens,dietary_tags,ingredients\n"
)


def _unique_served_on() -> str:
    """A unique per-test document id under menus/ — the emulator persists
    state across the whole pytest run, so a shared literal date would let
    this file's writes collide with test_menu_store.py's (they did, before
    this fix: both hardcoded "2026-09-08" and one test's leftover rows
    broke the other's exact-count assertion)."""
    return f"test-{uuid.uuid4().hex}"


def test_upload_without_auth_header_returns_401():
    """No dependency override here — proves auth is actually enforced,
    not just implemented and never wired into the route."""
    from main import app
    client = TestClient(app)
    resp = client.post(f"/admin/menu/upload?format=csv&served_on={_unique_served_on()}", content="")
    assert resp.status_code == 401


def test_upload_valid_csv_accepts_and_persists(authed_client):
    served_on = _unique_served_on()
    csv_text = CSV_HEADER + (
        f"Grilled Chicken,Grill,lunch,11:00,15:00,{served_on},"
        "450,38,20,12,3,410,2,9.50,dairy,,\n"
    )
    resp = authed_client.post(
        f"/admin/menu/upload?format=csv&served_on={served_on}",
        content=csv_text,
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] == 1
    assert body["rejected"] == []

    from services.menu_store import get_menu_for_date
    menu = get_menu_for_date(served_on)
    assert any(item["name"] == "Grilled Chicken" for item in menu)


def test_upload_csv_reports_rejected_rows_with_reason(authed_client):
    csv_text = (
        "name,station,meal_period,calories,protein_g,carbs_g,fat_g,fiber_g,sodium_mg,sugar_g\n"
        "Mystery Item,Grill,lunch,450,38,20,12,3,410,2\n"  # no allergens column at all
    )
    resp = authed_client.post(
        f"/admin/menu/upload?format=csv&served_on={_unique_served_on()}",
        content=csv_text,
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] == 0
    assert len(body["rejected"]) == 1
    assert "allergen" in body["rejected"][0]["reason"]


def test_upload_messy_json_accepts_and_persists(authed_client):
    served_on = _unique_served_on()
    raw = [{
        "ItemName": "Grilled Salmon", "Meal": "Lunch",
        "Cals": "450 cal", "Protein": "38g", "Carbs": "20g", "Fat": "12g",
        "Fiber": "3g", "Sodium": "410mg", "Sugar": "2g", "Price": "9.50", "Allergens": "fish",
    }]
    resp = authed_client.post(
        f"/admin/menu/upload?format=messy_json&served_on={served_on}",
        json=raw,
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] == 1

    from services.menu_store import get_menu_for_date
    menu = get_menu_for_date(served_on)
    assert any(item["name"] == "Grilled Salmon" for item in menu)


def test_upload_unknown_format_returns_400(authed_client):
    resp = authed_client.post(
        "/admin/menu/upload?format=xml",
        content="<menu></menu>",
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 400


# ── POST /admin/menu/sync-vendor ────────────────────────────────────────────

def test_sync_vendor_unknown_campus_returns_400(authed_client):
    resp = authed_client.post(
        "/admin/menu/sync-vendor?campus=nonexistent_school",
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 400


def test_sync_vendor_unregistered_vendor_returns_500(authed_client, monkeypatch):
    from services.vendor_ingestion.campus_config import CampusConfig
    import routers.admin_menu as admin_menu_module

    fake_config = CampusConfig(
        campus_id="unsupported_school", display_name="Unsupported School",
        vendor="some_unregistered_vendor", base_url="https://example.com", cafes=(),
    )
    monkeypatch.setattr(admin_menu_module, "get_campus_config", lambda campus: fake_config)

    resp = authed_client.post(
        "/admin/menu/sync-vendor?campus=unsupported_school",
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 500


def test_sync_vendor_without_auth_header_returns_401():
    from main import app
    client = TestClient(app)
    resp = client.post(f"/admin/menu/sync-vendor?campus=santa_clara&served_on={_unique_served_on()}")
    assert resp.status_code == 401


def test_sync_vendor_persists_accepted_items_and_queues_allergen_rejections(authed_client, monkeypatch):
    from services.menu_ingestion.base import IngestionResult, RejectedRecord
    import routers.admin_menu as admin_menu_module

    served_on = _unique_served_on()
    accepted_item = {
        "id": "synced-item-1", "name": "Synced Grilled Chicken", "station": "Hot Entrees",
        "meal_period": "lunch", "available_from": "11:00", "available_until": "15:00",
        "calories": 450.0, "protein_g": 38.0, "carbs_g": 20.0, "fat_g": 12.0,
        "fiber_g": 3.0, "sodium_mg": 410.0, "sugar_g": 2.0, "price": 9.5,
        "allergens": ["dairy"], "dietary_tags": [], "ingredients": [], "description": "",
    }
    fake_result = IngestionResult(
        items=[accepted_item],
        rejected=[RejectedRecord(raw={"item": {"label": "Mystery Item"}}, reason="missing allergen data")],
    )

    monkeypatch.setitem(admin_menu_module._VENDOR_FETCHERS, "bon_appetit", lambda campus: fake_result)

    resp = authed_client.post(
        f"/admin/menu/sync-vendor?campus=santa_clara&served_on={served_on}",
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] == 1
    assert len(body["rejected"]) == 1
    assert body["queued_for_review"] == 1

    from services.menu_store import get_menu_for_date
    menu = get_menu_for_date(served_on)
    assert any(item["name"] == "Synced Grilled Chicken" for item in menu)

    from services.menu_review_queue import get_review_queue
    queue = get_review_queue(campus_id="santa_clara")
    assert any(e["raw"]["item"]["label"] == "Mystery Item" for e in queue)
