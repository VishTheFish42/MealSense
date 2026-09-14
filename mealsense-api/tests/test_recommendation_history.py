"""
Tests services/recommendation_history.py and the /recommendation +
/recommendation/{id}/feedback routes' Firestore-dependent behavior,
against a real local Firestore emulator — same reasoning as
test_menu_store.py. Requires the emulator running first:
    cd mealsense-app && npx firebase emulators:start --only firestore
Skips cleanly with a clear reason if it isn't reachable.

test_routes.py separately covers /recommendation's shape when Firestore
is NOT configured (the sample-menu fallback environment) — that file
deliberately runs without the emulator, and confirms recommendation_id
is simply absent there rather than the request failing.
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


def _unique_student_id() -> str:
    return f"test-student-{uuid.uuid4().hex}"


# ── write_recommendation / get_recommendation / set_feedback ───────────────

def test_write_then_read_round_trips_a_recommendation():
    from services.recommendation_history import get_recommendation, write_recommendation

    student_id = _unique_student_id()
    rec_id = write_recommendation(student_id, "item-1", "Item 1", 87.4, "lunch")

    record = get_recommendation(rec_id)
    assert record["studentId"] == student_id
    assert record["menuItemId"] == "item-1"
    assert record["score"] == 87.4
    assert record["mealPeriod"] == "lunch"
    assert record["feedback"] is None


def test_get_recommendation_returns_none_for_unknown_id():
    from services.recommendation_history import get_recommendation
    assert get_recommendation("does-not-exist") is None


def test_set_feedback_updates_the_record():
    from services.recommendation_history import get_recommendation, set_feedback, write_recommendation

    rec_id = write_recommendation(_unique_student_id(), "item-1", "Item 1", 87.4, "lunch")
    set_feedback(rec_id, "thumbs_up")

    assert get_recommendation(rec_id)["feedback"] == "thumbs_up"


def test_set_feedback_is_changeable_not_one_shot():
    from services.recommendation_history import get_recommendation, set_feedback, write_recommendation

    rec_id = write_recommendation(_unique_student_id(), "item-1", "Item 1", 87.4, "lunch")
    set_feedback(rec_id, "thumbs_up")
    set_feedback(rec_id, "thumbs_down")

    assert get_recommendation(rec_id)["feedback"] == "thumbs_down"


def test_set_feedback_rejects_invalid_value():
    from services.recommendation_history import set_feedback, write_recommendation

    rec_id = write_recommendation(_unique_student_id(), "item-1", "Item 1", 87.4, "lunch")
    with pytest.raises(ValueError):
        set_feedback(rec_id, "love_it")


def test_set_feedback_raises_not_found_for_unknown_recommendation():
    from google.api_core.exceptions import NotFound
    from services.recommendation_history import set_feedback

    with pytest.raises(NotFound):
        set_feedback("does-not-exist", "thumbs_up")


# ── Route-level: POST /recommendation persists + returns an id ────────────

_MINIMAL_PAYLOAD = {
    "profile": {
        "age": 21, "sex": "male", "weightKg": 70.0, "heightCm": 175.0,
        "activityLevel": "moderate", "healthGoal": "maintain",
        "allergies": [], "dietaryIdentity": [], "conditions": [],
    },
    "meal_period": "lunch",
}


def _fake_recommend_result():
    return {
        "recommendation": {
            "menuItem": {"id": "item-1", "name": "Grilled Chicken Bowl"},
            "score": 87.4,
            "reasoning": {"primary": "Fits your goal.", "signals": []},
        },
        "alternatives": [],
        "meal_period": "lunch",
    }


def test_post_recommendation_with_uid_returns_recommendation_id(monkeypatch):
    """Isolates the route's own history-writing logic from recommend()'s
    real scoring — a live-time-dependent path (3.5's real availability
    filtering) shouldn't make this coverage flaky."""
    import routers.recommendations as recommendations_module
    monkeypatch.setattr(recommendations_module, "recommend", lambda **kw: _fake_recommend_result())

    from main import app
    client = TestClient(app)

    payload = {**_MINIMAL_PAYLOAD, "profile": {**_MINIMAL_PAYLOAD["profile"], "uid": _unique_student_id()}}
    resp = client.post("/recommendation", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert "recommendation_id" in body

    from services.recommendation_history import get_recommendation
    record = get_recommendation(body["recommendation_id"])
    assert record["studentId"] == payload["profile"]["uid"]
    assert record["menuItemId"] == "item-1"
    assert record["score"] == 87.4


def test_post_recommendation_without_uid_omits_recommendation_id(monkeypatch):
    """A profile with no uid (shouldn't happen from the real app, but the
    endpoint has no auth to enforce it) must not crash — just skip
    persisting, since there's nothing to key the history record on."""
    import routers.recommendations as recommendations_module
    monkeypatch.setattr(recommendations_module, "recommend", lambda **kw: _fake_recommend_result())

    from main import app
    client = TestClient(app)

    resp = client.post("/recommendation", json=_MINIMAL_PAYLOAD)
    assert resp.status_code == 200
    assert "recommendation_id" not in resp.json()


def test_post_recommendation_no_safe_items_has_no_recommendation_id(monkeypatch):
    import routers.recommendations as recommendations_module
    monkeypatch.setattr(recommendations_module, "recommend", lambda **kw: {
        "recommendation": None, "alternatives": [], "meal_period": "lunch", "reason": "no_safe_items",
    })

    from main import app
    client = TestClient(app)

    payload = {**_MINIMAL_PAYLOAD, "profile": {**_MINIMAL_PAYLOAD["profile"], "uid": _unique_student_id()}}
    resp = client.post("/recommendation", json=payload)
    assert resp.status_code == 200
    assert "recommendation_id" not in resp.json()


# ── Route-level: POST /recommendation/{id}/feedback ─────────────────────────

def test_feedback_route_updates_the_record():
    from main import app
    from services.recommendation_history import get_recommendation, write_recommendation

    client = TestClient(app)
    rec_id = write_recommendation(_unique_student_id(), "item-1", "Item 1", 87.4, "lunch")

    resp = client.post(f"/recommendation/{rec_id}/feedback", json={"feedback": "thumbs_up"})

    assert resp.status_code == 200
    assert resp.json() == {"recommendation_id": rec_id, "feedback": "thumbs_up"}
    assert get_recommendation(rec_id)["feedback"] == "thumbs_up"


def test_feedback_route_rejects_invalid_value():
    from main import app
    from services.recommendation_history import write_recommendation

    client = TestClient(app)
    rec_id = write_recommendation(_unique_student_id(), "item-1", "Item 1", 87.4, "lunch")

    resp = client.post(f"/recommendation/{rec_id}/feedback", json={"feedback": "love_it"})
    assert resp.status_code == 422


def test_feedback_route_unknown_id_returns_404():
    from main import app
    client = TestClient(app)

    resp = client.post("/recommendation/does-not-exist/feedback", json={"feedback": "thumbs_up"})
    assert resp.status_code == 404
