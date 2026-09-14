"""
Route-level tests for GET /admin/analytics. Auth is bypassed via FastAPI's
dependency_overrides for the response-shape test — require_kitchen_role's
own logic is covered separately in test_auth.py. One test deliberately
does NOT override the dependency, to prove auth is actually wired into
the route, not just implemented and unused (same pattern as
test_admin_menu.py).

Requires the Firestore emulator, same as test_analytics_aggregation.py.
"""
import socket

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


def test_analytics_without_auth_header_returns_401():
    from main import app
    client = TestClient(app)
    resp = client.get("/admin/analytics")
    assert resp.status_code == 401


def test_analytics_returns_expected_shape(authed_client):
    resp = authed_client.get("/admin/analytics", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    body = resp.json()
    assert "most_recommended_items" in body
    assert "dietary_constraints" in body
    assert set(body["dietary_constraints"].keys()) == {
        "allergies", "dietary_identity", "conditions", "nutritional_focus",
    }
