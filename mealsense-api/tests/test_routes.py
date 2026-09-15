import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import DefaultCredentialsError

from main import app

client = TestClient(app)


@pytest.fixture
def firestore_not_configured(monkeypatch):
    """Forces the FirestoreNotConfiguredError fallback deterministically.
    This file's whole premise is "Firestore isn't configured" — that used
    to be an ambient fact about any machine with no emulator, key file, or
    Application Default Credentials set up. It stopped being ambiently
    true the moment local ADC was set up for Cloud Run deployment
    (tasks.md Phase 7): a developer running this suite locally now
    genuinely has working Firestore credentials, so relying on environment
    absence silently broke the tests below. Mocking the credential
    boundary instead keeps this deterministic regardless of what any given
    machine — this one or a future one — actually has configured."""
    from services import firestore_client
    firestore_client.reset_firestore_client()
    monkeypatch.setattr(
        "google.auth.default",
        lambda *a, **kw: (_ for _ in ()).throw(DefaultCredentialsError("no creds (test)")),
    )
    yield
    firestore_client.reset_firestore_client()


# ── 2.3.1: GET /menu with no params ────────────────────────────────────────

def test_get_menu_no_params_returns_all_items_and_count():
    resp = client.get("/menu")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == len(body["items"])
    assert body["count"] > 0


# ── 2.3.2: GET /menu?meal_period=X filters correctly, including all_day ───

def test_get_menu_filtered_by_meal_period_includes_all_day():
    resp = client.get("/menu", params={"meal_period": "breakfast"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == len(body["items"])
    assert body["count"] > 0
    assert all(item["meal_period"] in ("breakfast", "all_day") for item in body["items"])


# ── 2.3.3: POST /recommendation with a minimal valid profile ──────────────

def test_post_recommendation_minimal_valid_profile_returns_expected_shape():
    payload = {
        "profile": {
            "age": 21,
            "sex": "male",
            "weightKg": 70.0,
            "heightCm": 175.0,
            "activityLevel": "moderate",
            "healthGoal": "maintain",
            "allergies": [],
            "dietaryIdentity": [],
            "conditions": [],
        },
        "meal_period": "lunch",
    }
    resp = client.post("/recommendation", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "recommendation" in body
    assert "alternatives" in body
    assert body["meal_period"] == "lunch"


# ── 2.3.4: POST /recommendation with malformed/missing fields ─────────────

def test_post_recommendation_missing_meal_period_returns_422():
    # `meal_period` is a required field on RecommendationRequest; omitting it
    # should fail FastAPI/Pydantic request validation before it ever reaches
    # the recommendation engine.
    resp = client.post("/recommendation", json={"profile": {}})
    assert resp.status_code == 422


def test_post_recommendation_missing_profile_returns_422():
    resp = client.post("/recommendation", json={"meal_period": "lunch"})
    assert resp.status_code == 422


def test_post_recommendation_with_uid_still_succeeds_without_firestore_configured(firestore_not_configured):
    """This file deliberately covers /recommendation's shape when
    Firestore is NOT configured (test_recommendation_history.py covers
    the emulator-backed history write itself). A profile with a uid must
    still hit the write_recommendation attempt and gracefully skip it on
    FirestoreNotConfiguredError — the recommendation response itself
    must not fail just because history/feedback isn't available here."""
    payload = {
        "profile": {
            "uid": "some-student-uid",
            "age": 21,
            "sex": "male",
            "weightKg": 70.0,
            "heightCm": 175.0,
            "activityLevel": "moderate",
            "healthGoal": "maintain",
            "allergies": [],
            "dietaryIdentity": [],
            "conditions": [],
        },
        "meal_period": "lunch",
    }
    resp = client.post("/recommendation", json=payload)
    assert resp.status_code == 200
    assert "recommendation_id" not in resp.json()


def test_post_recommendation_catches_firestore_not_configured_when_writing_history(
    monkeypatch, firestore_not_configured
):
    """Directly forces entry into the write_recommendation try/except
    (routers/recommendations.py) regardless of what real time it is —
    the test above can't guarantee reaching this branch on its own, since
    whether recommend() returns a real recommendation depends on the
    live wall clock (3.5's real availability filtering)."""
    import routers.recommendations as recommendations_module

    monkeypatch.setattr(recommendations_module, "recommend", lambda **kw: {
        "recommendation": {
            "menuItem": {"id": "item-1", "name": "Grilled Chicken Bowl"},
            "score": 87.4,
            "reasoning": {"primary": "Fits your goal.", "signals": []},
        },
        "alternatives": [],
        "meal_period": "lunch",
    })

    payload = {
        "profile": {"uid": "some-student-uid"},
        "meal_period": "lunch",
    }
    resp = client.post("/recommendation", json=payload)

    assert resp.status_code == 200
    assert "recommendation_id" not in resp.json()
