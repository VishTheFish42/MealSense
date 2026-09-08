from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


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
