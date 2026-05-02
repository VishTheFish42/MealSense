"""
Recommendation engine implementing the scoring algorithm from design-spec.md §5.
"""
from __future__ import annotations
from typing import Any

# ── Weight definitions ────────────────────────────────────────────────────────

BASE_WEIGHTS: dict[str, float] = {
    "macro": 0.35,
    "protein": 0.20,
    "fiber": 0.15,
    "sugar_sodium": 0.15,
    "variety": 0.15,
}

ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "very_active": 1.725,
}

MEAL_FRACTIONS: dict[str, float] = {
    "breakfast": 0.25,
    "lunch": 0.35,
    "dinner": 0.35,
    "all_day": 0.33,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _weights_for_profile(profile: dict) -> dict[str, float]:
    """Return scoring weights adjusted for the student's health conditions."""
    w = BASE_WEIGHTS.copy()
    conditions: list[str] = profile.get("conditions", [])

    if "diabetes" in conditions:
        w["macro"] = 0.30
        w["sugar_sodium"] = 0.25
        w["protein"] = 0.20
        w["fiber"] = 0.10
        w["variety"] = 0.15

    if "hypertension" in conditions and "diabetes" not in conditions:
        w["macro"] = 0.30
        w["sugar_sodium"] = 0.25
        w["protein"] = 0.20
        w["fiber"] = 0.10
        w["variety"] = 0.15

    if "high_cholesterol" in conditions:
        w["fiber"] = 0.20
        # Redistribute to keep sum at 1
        w["macro"] = max(0.25, w["macro"] - 0.05)

    if "ibs" in conditions:
        w["fiber"] = max(w["fiber"] - 0.05, 0.05)

    # Normalise to sum 1
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def _calorie_target(profile: dict, meal_period: str) -> float:
    """Mifflin-St Jeor BMR × activity multiplier × meal fraction."""
    age = profile.get("age") or 21
    weight_kg = profile.get("weightKg") or 70.0
    height_cm = profile.get("heightCm") or 170.0
    sex = (profile.get("sex") or "male").lower()
    activity = profile.get("activityLevel") or "moderate"
    goal = profile.get("healthGoal") or "maintain"

    if sex == "female":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5

    tdee = bmr * ACTIVITY_MULTIPLIERS.get(activity, 1.55)

    if goal == "lose_weight":
        tdee *= 0.85
    elif goal == "gain_muscle":
        tdee *= 1.10

    return tdee * MEAL_FRACTIONS.get(meal_period, 0.33)


def _score_item(
    item: dict,
    profile: dict,
    weights: dict[str, float],
    calorie_target: float,
    recent_ids: set[str],
) -> tuple[float, list[str]]:
    """Return (score 0-100, list of top signal names)."""
    signals: list[str] = []

    # 1. Macro alignment (calorie proximity)
    if calorie_target > 0:
        deviation = abs(item["calories"] - calorie_target) / calorie_target
        macro_score = max(0.0, 1.0 - deviation)
    else:
        macro_score = 0.5

    # 2. Protein (50 g reference max)
    protein_score = min(item["protein_g"] / 50.0, 1.0)
    if item["protein_g"] >= 30:
        signals.append("high_protein")

    # 3. Fiber (15 g reference max)
    fiber_score = min(item["fiber_g"] / 15.0, 1.0)
    if item["fiber_g"] >= 6:
        signals.append("high_fiber")

    # 4. Low sugar + low sodium combined
    sugar_score = 1.0 - min(item["sugar_g"] / 30.0, 1.0)
    sodium_score = 1.0 - min(item["sodium_mg"] / 1500.0, 1.0)
    sugar_sodium_score = (sugar_score + sodium_score) / 2.0
    if item["sugar_g"] <= 6:
        signals.append("low_sugar")
    if item["sodium_mg"] <= 500:
        signals.append("low_sodium")

    # 5. Variety penalty
    variety_score = 0.0 if item["id"] in recent_ids else 1.0

    # Low-fat bonus for high_cholesterol / ibs
    conditions = profile.get("conditions", [])
    fat_bonus = 0.0
    if ("high_cholesterol" in conditions or "ibs" in conditions) and item["fat_g"] <= 12:
        fat_bonus = 0.05
        signals.append("low_fat")

    raw = (
        weights["macro"] * macro_score
        + weights["protein"] * protein_score
        + weights["fiber"] * fiber_score
        + weights["sugar_sodium"] * sugar_sodium_score
        + weights["variety"] * variety_score
        + fat_bonus
    )

    return round(min(raw * 100, 100), 1), signals


def _primary_reason(item: dict, profile: dict, signals: list[str]) -> str:
    """Generate a one-sentence human-readable recommendation reason."""
    goal = profile.get("healthGoal", "wellness")
    goal_phrases: dict[str, str] = {
        "lose_weight": "supports your weight-loss goal with a lower calorie count",
        "maintain": "fits your maintenance calorie target well",
        "gain_muscle": "is high in protein to support muscle growth",
        "energy": "provides steady energy with balanced macros",
        "wellness": "offers a balanced nutritional profile",
    }
    base = goal_phrases.get(goal, "is a good match for your profile")
    if "high_protein" in signals:
        return f"{item['name']} {base} and delivers {item['protein_g']:.0f} g of protein."
    if "high_fiber" in signals:
        return f"{item['name']} {base} and is rich in fiber ({item['fiber_g']:.0f} g)."
    return f"{item['name']} {base}."


# ── Hard filters ──────────────────────────────────────────────────────────────

def _passes_hard_filters(item: dict, profile: dict, meal_period: str) -> bool:
    allergens = set(a.lower() for a in profile.get("allergies", []))
    item_allergens = set(a.lower() for a in item.get("allergens", []))
    if allergens & item_allergens:
        return False

    diet = set(d.lower() for d in profile.get("dietaryIdentity", []))
    item_tags = set(t.lower() for t in item.get("dietary_tags", []))
    for d in diet:
        if d not in item_tags:
            return False

    item_period = item.get("meal_period", "all_day")
    if item_period != "all_day" and item_period != meal_period:
        return False

    return True


# ── Public API ────────────────────────────────────────────────────────────────

def recommend(
    menu: list[dict],
    profile: dict,
    meal_period: str,
    recent_ids: list[str],
) -> dict:
    """
    Run the full recommendation pipeline.
    Returns a dict matching the RecommendationResponse shape expected by the app.
    """
    recent_set = set(recent_ids)
    weights = _weights_for_profile(profile)
    calorie_target = _calorie_target(profile, meal_period)

    candidates = [i for i in menu if _passes_hard_filters(i, profile, meal_period)]

    if not candidates:
        return {
            "recommendation": None,
            "alternatives": [],
            "meal_period": meal_period,
            "reason": "no_safe_items",
        }

    scored = []
    for item in candidates:
        score, signals = _score_item(item, profile, weights, calorie_target, recent_set)
        scored.append((item, score, signals))

    scored.sort(key=lambda x: x[1], reverse=True)

    def build_result(item: dict, score: float, signals: list[str]) -> dict:
        return {
            "menuItem": item,
            "score": score,
            "reasoning": {
                "primary": _primary_reason(item, profile, signals),
                "signals": signals[:4],
            },
        }

    top_item, top_score, top_signals = scored[0]
    alternatives = [build_result(i, s, sig) for i, s, sig in scored[1:4]]

    return {
        "recommendation": build_result(top_item, top_score, top_signals),
        "alternatives": alternatives,
        "meal_period": meal_period,
    }
