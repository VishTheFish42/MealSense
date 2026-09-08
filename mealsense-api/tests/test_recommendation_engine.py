import itertools

import pytest

from services.recommendation_engine import (
    ACTIVITY_MULTIPLIERS,
    MEAL_FRACTIONS,
    _calorie_target,
    _passes_hard_filters,
    _score_item,
    _weights_for_profile,
    recommend,
)

ALL_CONDITIONS = ["diabetes", "hypertension", "high_cholesterol", "ibs"]


# ── 2.2.1-2.2.3: Allergen hard filter ──────────────────────────────────────

def test_allergen_filter_excludes_flagged_item(make_profile, make_item):
    profile = make_profile(allergies=["nuts"])
    item = make_item(allergens=["nuts"])
    assert _passes_hard_filters(item, profile, "lunch") is False


def test_allergen_filter_case_insensitive(make_profile, make_item):
    profile = make_profile(allergies=["Nuts"])
    item = make_item(allergens=["NUTS"])
    assert _passes_hard_filters(item, profile, "lunch") is False


def test_allergen_filter_multiple_allergies_all_enforced(make_profile, make_item):
    profile = make_profile(allergies=["nuts", "dairy", "shellfish"])
    assert _passes_hard_filters(make_item(allergens=["dairy"]), profile, "lunch") is False
    assert _passes_hard_filters(make_item(allergens=["shellfish"]), profile, "lunch") is False
    assert _passes_hard_filters(make_item(allergens=["gluten"]), profile, "lunch") is True


# ── 2.2.4-2.2.5: Dietary identity filter ───────────────────────────────────

def test_dietary_identity_single_enforced(make_profile, make_item):
    profile = make_profile(dietaryIdentity=["vegetarian"])
    veg_item = make_item(dietary_tags=["vegetarian"])
    non_veg_item = make_item(dietary_tags=[])
    assert _passes_hard_filters(veg_item, profile, "lunch") is True
    assert _passes_hard_filters(non_veg_item, profile, "lunch") is False


def test_dietary_identity_multiple_enforced_as_and_not_or(make_profile, make_item):
    profile = make_profile(dietaryIdentity=["vegan", "halal"])
    both = make_item(dietary_tags=["vegan", "halal"])
    only_vegan = make_item(dietary_tags=["vegan"])
    only_halal = make_item(dietary_tags=["halal"])
    assert _passes_hard_filters(both, profile, "lunch") is True
    assert _passes_hard_filters(only_vegan, profile, "lunch") is False
    assert _passes_hard_filters(only_halal, profile, "lunch") is False


# ── 2.2.6: Meal-period availability filter ─────────────────────────────────

def test_meal_period_filter(make_profile, make_item):
    profile = make_profile()
    lunch_item = make_item(meal_period="lunch")
    dinner_item = make_item(meal_period="dinner")
    all_day_item = make_item(meal_period="all_day")
    assert _passes_hard_filters(lunch_item, profile, "lunch") is True
    assert _passes_hard_filters(dinner_item, profile, "lunch") is False
    assert _passes_hard_filters(all_day_item, profile, "breakfast") is True


# ── 2.2.7: No-safe-items fallback ──────────────────────────────────────────

def test_no_safe_items_fallback(make_profile, make_item):
    profile = make_profile(allergies=["nuts"])
    menu = [make_item(id="x", allergens=["nuts"])]
    result = recommend(menu, profile, "lunch", [])
    assert result["recommendation"] is None
    assert result["reason"] == "no_safe_items"
    assert result["alternatives"] == []


# ── 2.2.8: Macro/calorie alignment is monotonic with deviation ────────────

def test_macro_score_monotonic_with_calorie_deviation(minimal_profile, make_item):
    weights = _weights_for_profile(minimal_profile)
    target = _calorie_target(minimal_profile, "lunch")

    near = make_item(calories=target)
    far = make_item(calories=target * 1.5)
    farther = make_item(calories=target * 2.0)

    score_near, _ = _score_item(near, minimal_profile, weights, target, set())
    score_far, _ = _score_item(far, minimal_profile, weights, target, set())
    score_farther, _ = _score_item(farther, minimal_profile, weights, target, set())

    assert score_near > score_far > score_farther


def test_macro_score_falls_back_when_calorie_target_not_positive(minimal_profile, make_item):
    # Defensive branch: a zero or negative calorie target (extreme/degenerate
    # profile inputs) should neutral-score the macro signal instead of
    # dividing by zero or producing a nonsensical deviation.
    weights = _weights_for_profile(minimal_profile)
    item = make_item(calories=500.0)

    score, _ = _score_item(item, minimal_profile, weights, calorie_target=0, recent_ids=set())
    assert 0.0 <= score <= 100.0


# ── 2.2.9: Protein/fiber scores capped at reference max ───────────────────

def test_protein_and_fiber_scores_capped_at_reference_max(minimal_profile, make_item):
    weights = _weights_for_profile(minimal_profile)
    target = _calorie_target(minimal_profile, "lunch")

    at_cap = make_item(protein_g=50.0, fiber_g=15.0, calories=target)
    above_cap = make_item(protein_g=100.0, fiber_g=30.0, calories=target)

    score_at, _ = _score_item(at_cap, minimal_profile, weights, target, set())
    score_above, _ = _score_item(above_cap, minimal_profile, weights, target, set())

    assert score_at == score_above


# ── 2.2.10: Variety penalty ────────────────────────────────────────────────

def test_variety_penalty_applied_for_recent_items(minimal_profile, make_item):
    weights = _weights_for_profile(minimal_profile)
    target = _calorie_target(minimal_profile, "lunch")
    item = make_item(id="repeat_item", calories=target)

    score_fresh, _ = _score_item(item, minimal_profile, weights, target, set())
    score_recent, _ = _score_item(item, minimal_profile, weights, target, {"repeat_item"})

    assert score_recent < score_fresh
    assert score_fresh - score_recent == pytest.approx(weights["variety"] * 100, abs=0.15)


# ── 2.2.11: Final score bounded to [0, 100] ────────────────────────────────

def test_score_bounded_between_zero_and_hundred(minimal_profile, make_item):
    weights = _weights_for_profile(minimal_profile)
    target = _calorie_target(minimal_profile, "lunch")

    high_everything = make_item(
        calories=target, protein_g=500.0, fiber_g=500.0, sugar_g=0.0, sodium_mg=0.0
    )
    score_high, _ = _score_item(high_everything, minimal_profile, weights, target, set())
    assert 0.0 <= score_high <= 100.0

    worst_case = make_item(
        calories=target * 10, protein_g=0.0, fiber_g=0.0, sugar_g=1000.0, sodium_mg=100000.0
    )
    score_worst, _ = _score_item(worst_case, minimal_profile, weights, target, set())
    assert 0.0 <= score_worst <= 100.0


# ── 2.2.12-2.2.14: Condition-based weight shifts ───────────────────────────

def test_diabetes_shifts_weight_toward_sugar_sodium(make_profile):
    baseline = _weights_for_profile(make_profile(conditions=[]))
    diabetic = _weights_for_profile(make_profile(conditions=["diabetes"]))
    assert diabetic["sugar_sodium"] > baseline["sugar_sodium"]


def test_hypertension_shifts_weight_toward_sugar_sodium(make_profile):
    baseline = _weights_for_profile(make_profile(conditions=[]))
    hypertensive = _weights_for_profile(make_profile(conditions=["hypertension"]))
    assert hypertensive["sugar_sodium"] > baseline["sugar_sodium"]


def test_diabetes_and_hypertension_together_no_double_adjustment(make_profile):
    diabetes_only = _weights_for_profile(make_profile(conditions=["diabetes"]))
    both = _weights_for_profile(make_profile(conditions=["diabetes", "hypertension"]))
    assert both == pytest.approx(diabetes_only)


# ── 2.2.15: Adjusted weights always sum to 1.0 ─────────────────────────────

ALL_CONDITION_COMBOS = [
    list(combo)
    for r in range(len(ALL_CONDITIONS) + 1)
    for combo in itertools.combinations(ALL_CONDITIONS, r)
]


@pytest.mark.parametrize("conditions", ALL_CONDITION_COMBOS)
def test_weights_always_sum_to_one(make_profile, conditions):
    weights = _weights_for_profile(make_profile(conditions=conditions))
    assert sum(weights.values()) == pytest.approx(1.0)


# ── 2.2.16: BMR fixed test vectors ─────────────────────────────────────────

def test_bmr_male_fixed_vector(make_profile):
    profile = make_profile(
        sex="male", age=25, weightKg=80.0, heightCm=180.0,
        activityLevel="sedentary", healthGoal="maintain",
    )
    target = _calorie_target(profile, "all_day")
    bmr = 10 * 80.0 + 6.25 * 180.0 - 5 * 25 + 5
    expected = bmr * ACTIVITY_MULTIPLIERS["sedentary"] * MEAL_FRACTIONS["all_day"]
    assert target == pytest.approx(expected)


def test_bmr_female_fixed_vector(make_profile):
    profile = make_profile(
        sex="female", age=30, weightKg=60.0, heightCm=165.0,
        activityLevel="sedentary", healthGoal="maintain",
    )
    target = _calorie_target(profile, "all_day")
    bmr = 10 * 60.0 + 6.25 * 165.0 - 5 * 30 - 161
    expected = bmr * ACTIVITY_MULTIPLIERS["sedentary"] * MEAL_FRACTIONS["all_day"]
    assert target == pytest.approx(expected)


# ── 2.2.17: All four activity multipliers applied ──────────────────────────

@pytest.mark.parametrize("activity", ["sedentary", "light", "moderate", "very_active"])
def test_all_activity_multipliers_applied(make_profile, activity):
    profile = make_profile(activityLevel=activity, healthGoal="maintain")
    target = _calorie_target(profile, "all_day")
    bmr = (
        10 * profile["weightKg"]
        + 6.25 * profile["heightCm"]
        - 5 * profile["age"]
        + 5
    )
    expected = bmr * ACTIVITY_MULTIPLIERS[activity] * MEAL_FRACTIONS["all_day"]
    assert target == pytest.approx(expected)


# ── 2.2.18: Goal adjustments applied correctly ─────────────────────────────

def test_goal_adjustments_applied(make_profile):
    base = make_profile(healthGoal="maintain")
    lose = make_profile(healthGoal="lose_weight")
    gain = make_profile(healthGoal="gain_muscle")

    t_base = _calorie_target(base, "all_day")
    t_lose = _calorie_target(lose, "all_day")
    t_gain = _calorie_target(gain, "all_day")

    assert t_lose == pytest.approx(t_base * 0.85)
    assert t_gain == pytest.approx(t_base * 1.10)


# ── 2.2.19: Meal-period apportionment matches spec ─────────────────────────

def test_meal_period_apportionment_matches_spec(make_profile):
    profile = make_profile()
    breakfast = _calorie_target(profile, "breakfast")
    lunch = _calorie_target(profile, "lunch")
    dinner = _calorie_target(profile, "dinner")

    tdee = breakfast / MEAL_FRACTIONS["breakfast"]
    assert lunch == pytest.approx(tdee * MEAL_FRACTIONS["lunch"])
    assert dinner == pytest.approx(tdee * MEAL_FRACTIONS["dinner"])
    assert MEAL_FRACTIONS["breakfast"] == pytest.approx(0.25)
    assert MEAL_FRACTIONS["lunch"] == pytest.approx(0.35)
    assert MEAL_FRACTIONS["dinner"] == pytest.approx(0.35)


# ── 2.2.20: Top recommendation is always the highest-scoring candidate ────

def test_top_recommendation_is_highest_scoring(minimal_profile, make_item):
    items = [
        make_item(id="low", protein_g=5.0),
        make_item(id="high", protein_g=45.0),
        make_item(id="mid", protein_g=20.0),
    ]
    result = recommend(items, minimal_profile, "lunch", [])
    assert result["recommendation"]["menuItem"]["id"] == "high"

    scores = [result["recommendation"]["score"]] + [a["score"] for a in result["alternatives"]]
    assert scores == sorted(scores, reverse=True)


# ── 2.2.21: Alternatives capped at 3, sorted descending ────────────────────

def test_alternatives_capped_at_three_and_sorted(minimal_profile, make_item):
    items = [make_item(id=f"item{i}", protein_g=float(i)) for i in range(10)]
    result = recommend(items, minimal_profile, "lunch", [])

    assert len(result["alternatives"]) == 3
    scores = [a["score"] for a in result["alternatives"]]
    assert scores == sorted(scores, reverse=True)


# ── 2.2.22: Reasoning signals capped at 4 ──────────────────────────────────

def test_reasoning_signals_capped_at_four(make_profile, make_item):
    profile = make_profile(conditions=["high_cholesterol"])
    # Deliberately qualifies for 5 named signals: high_protein, high_fiber,
    # low_sugar, low_sodium, and low_fat (via the high_cholesterol condition).
    item = make_item(protein_g=40.0, fiber_g=10.0, sugar_g=2.0, sodium_mg=200.0, fat_g=5.0)

    result = recommend([item], profile, "lunch", [])
    signals = result["recommendation"]["reasoning"]["signals"]

    assert len(signals) <= 4
    assert signals == ["high_protein", "high_fiber", "low_sugar", "low_sodium"]
    assert "low_fat" not in signals
