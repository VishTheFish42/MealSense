"""
Optional Claude-assisted fallback for filling gaps in vendor menu data —
design-spec.md §7.0a. Scoped deliberately narrow (tasks.md 3.6, decided
2026-09-11): wired into services/vendor_ingestion/bon_appetit.py only, not
the CSV/messy-JSON manual upload paths.

Ground rules this module is built around:

- Only ever asked about fields ALREADY missing or unparseable. A field the
  source data already supplies is never re-derived or double-checked here
  — this module makes zero API calls for a fully-complete record.
- Nutrition estimation (calories, protein_g, carbs_g, fat_g, fiber_g,
  sodium_mg, sugar_g) is low-stakes if wrong — design-spec.md §7.0a calls
  this out explicitly: a bad estimate makes a recommendation slightly
  suboptimal, never unsafe. A plausible estimate is used outright; the
  caller is expected to flag the item as containing estimated data.
- Price is deliberately NOT eligible for estimation here, even though it's
  validated through the same numeric-required path as nutrition
  (schema.py). A wrong price is a money-safety issue (a student could be
  over/undercharged), a different risk category than a slightly-off
  calorie count — same reasoning that made price fail-closed at ingestion
  in the first place (tasks.md 3.6a).
- Allergen extraction from ingredient text is safety-relevant and stays
  fail-closed no matter what this module returns. This function only
  *reports* a confidence score — it is the CALLER's job to compare that
  against ALLERGEN_CONFIDENCE_THRESHOLD before trusting the result for
  anything, and to still record a review-queue entry even when confident
  enough to accept the item (the 2026-09-11 decision on this: an
  LLM-accepted item still gets a human double-check, it just isn't
  blocked pending one).
- Never touches the recommendation engine or its scoring/hard-filter
  logic. This module produces candidate *input* to build_menu_item, never
  a decision about what's safe to recommend — the same line
  design-spec.md §7.0a draws for any LLM involvement in ingestion.

Requires ANTHROPIC_API_KEY in the environment. Every public function fails
soft — returns {} / None — on any error. A Claude outage or a missing key
must degrade to "reject the item like before," never crash ingestion for
everyone else's items in the same batch.
"""
from __future__ import annotations
import logging
import os
from dataclasses import dataclass

import anthropic
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# design-spec.md §7.0a: the one number that decides whether an LLM-extracted
# allergen list is trusted enough to accept the item at all. Deliberately
# high — allergen safety has a zero-false-negative target (README.md §14);
# this fallback exists to *reduce* rejected items, never to quietly relax
# that guarantee.
ALLERGEN_CONFIDENCE_THRESHOLD = 0.9

_MODEL = "claude-opus-5"

_NUTRITION_FIELD_UNITS: dict[str, str] = {
    "calories": "kcal", "protein_g": "grams", "carbs_g": "grams",
    "fat_g": "grams", "fiber_g": "grams", "sodium_mg": "milligrams",
    "sugar_g": "grams",
}

# README.md §6.2's allergen vocabulary — the only values the recommendation
# engine's hard filter (recommendation_engine.py::_passes_hard_filters)
# actually knows how to compare against a student's profile.
ALLERGEN_VOCAB = ("nuts", "dairy", "gluten", "eggs", "soy", "shellfish", "fish", "sesame")


class AnthropicNotConfiguredError(Exception):
    """ANTHROPIC_API_KEY isn't set in this environment. Mirrors
    FirestoreNotConfiguredError's role in firestore_client.py: callers with
    a sensible fallback (skip enrichment, reject the item as before) should
    let this propagate up to their own try/except, not treat it as fatal."""


class _NutritionEstimateSchema(BaseModel):
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    sodium_mg: float | None = None
    sugar_g: float | None = None


class _AllergenExtractionSchema(BaseModel):
    allergens: list[str]
    confidence: float


@dataclass
class AllergenExtractionResult:
    allergens: list[str]  # already lowercased and restricted to ALLERGEN_VOCAB
    confidence: float


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise AnthropicNotConfiguredError(
                "ANTHROPIC_API_KEY is not set — required for LLM-assisted "
                "menu data enrichment (design-spec.md §7.0a)."
            )
        _client = anthropic.Anthropic()
    return _client


def reset_client() -> None:
    """Test-only: force the next _get_client() call to reconnect."""
    global _client
    _client = None


def estimate_missing_nutrition(
    name: str,
    ingredients: str,
    missing_fields: list[str],
    client: anthropic.Anthropic | None = None,
) -> dict[str, float]:
    """Returns {field: estimated_value} for exactly the subset of
    missing_fields Claude could produce a number for. A field it couldn't
    estimate is simply absent from the result — the caller's normal
    validation still rejects the item over that field, exactly as it
    would have with no enrichment attempted at all.

    `client` is an injectable anthropic.Anthropic-like object (only
    `.messages.parse(...)` needs to exist) — tests supply a fake instead of
    hitting the real API, the same dependency-injection pattern
    services/auth.py uses for verify_id_token and
    services/vendor_ingestion/bon_appetit.py uses for http_get.
    """
    if not missing_fields:
        return {}

    try:
        active_client = client or _get_client()
        wanted = ", ".join(f"{f} ({_NUTRITION_FIELD_UNITS.get(f, '')})" for f in missing_fields)
        response = active_client.messages.parse(
            model=_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": (
                    "A campus dining menu item is missing some nutrition data. "
                    "Using typical, commonly known nutrition facts for a dish "
                    f"like this, estimate ONLY these fields: {wanted}.\n\n"
                    f"Dish name: {name}\n"
                    f"Ingredients (if known): {ingredients or 'not provided'}\n\n"
                    "If you cannot make a reasonable estimate for a field, "
                    "leave it null rather than guessing wildly."
                ),
            }],
            output_format=_NutritionEstimateSchema,
        )
    except Exception:
        # Fail soft by design (see module docstring) — a Claude outage,
        # rate limit, or malformed response degrades to "no estimate,"
        # never an ingestion crash.
        logger.warning("estimate_missing_nutrition failed for %r", name, exc_info=True)
        return {}

    estimate = response.parsed_output
    return {
        field: getattr(estimate, field)
        for field in missing_fields
        if getattr(estimate, field, None) is not None
    }


def extract_allergens_from_ingredients(
    name: str,
    ingredients: str,
    client: anthropic.Anthropic | None = None,
) -> AllergenExtractionResult | None:
    """Returns None when there's no ingredient text to reason from, or on
    any API/parsing failure. Callers MUST compare .confidence against
    ALLERGEN_CONFIDENCE_THRESHOLD themselves before trusting .allergens for
    anything — this function reports a confidence score, it does not
    enforce one."""
    if not ingredients or not ingredients.strip():
        return None

    try:
        active_client = client or _get_client()
        response = active_client.messages.parse(
            model=_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": (
                    "A campus dining item's structured allergen data is "
                    "missing, but its ingredient text is available. Identify "
                    "which of these allergens the ingredients suggest are "
                    f"present: {', '.join(ALLERGEN_VOCAB)}. This feeds a "
                    "food-safety system with a zero-tolerance policy for "
                    "missed allergens — err toward a LOWER confidence score "
                    "rather than overstating certainty.\n\n"
                    f"Dish name: {name}\n"
                    f"Ingredients: {ingredients}\n\n"
                    "confidence should reflect how certain you are that this "
                    "list is COMPLETE and correct for the allergens above, "
                    "not just that the ones you listed are present."
                ),
            }],
            output_format=_AllergenExtractionSchema,
        )
    except Exception:
        logger.warning("extract_allergens_from_ingredients failed for %r", name, exc_info=True)
        return None

    parsed = response.parsed_output
    allergens = sorted({a.lower() for a in parsed.allergens if a.lower() in ALLERGEN_VOCAB})
    return AllergenExtractionResult(allergens=allergens, confidence=parsed.confidence)
