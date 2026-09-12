"""
Tests for services/menu_ingestion/llm_enrichment.py. Every test injects a
fake client instead of calling the real Anthropic API — same
dependency-injection pattern as services/auth.py's verify_id_token and
services/vendor_ingestion/bon_appetit.py's http_get.
"""
from types import SimpleNamespace

import pytest

from services.menu_ingestion.llm_enrichment import (
    ALLERGEN_CONFIDENCE_THRESHOLD,
    AnthropicNotConfiguredError,
    estimate_missing_nutrition,
    extract_allergens_from_ingredients,
)


class _FakeMessages:
    def __init__(self, parsed_output=None, raises=False):
        self._parsed_output = parsed_output
        self._raises = raises
        self.last_kwargs = None

    def parse(self, **kwargs):
        self.last_kwargs = kwargs
        if self._raises:
            raise RuntimeError("simulated API failure")
        return SimpleNamespace(parsed_output=self._parsed_output)


class _FakeClient:
    def __init__(self, parsed_output=None, raises=False):
        self.messages = _FakeMessages(parsed_output, raises)


# ── estimate_missing_nutrition ──────────────────────────────────────────────

def test_estimate_missing_nutrition_short_circuits_on_empty_list():
    """No API call at all when nothing is missing — the core cost/scope
    constraint (tasks.md 3.6): never re-derive data that's already there."""
    client = _FakeClient(parsed_output=SimpleNamespace(calories=999.0))
    result = estimate_missing_nutrition("Grilled Chicken", "chicken, rice", [], client=client)
    assert result == {}
    assert client.messages.last_kwargs is None


def test_estimate_missing_nutrition_fills_only_requested_fields():
    parsed = SimpleNamespace(
        calories=450.0, protein_g=None, carbs_g=20.0, fat_g=None,
        fiber_g=3.0, sodium_mg=None, sugar_g=None,
    )
    client = _FakeClient(parsed_output=parsed)

    result = estimate_missing_nutrition(
        "Grilled Chicken Bowl", "chicken, rice, broccoli",
        ["calories", "fiber_g"], client=client,
    )

    assert result == {"calories": 450.0, "fiber_g": 3.0}


def test_estimate_missing_nutrition_omits_fields_claude_could_not_estimate():
    parsed = SimpleNamespace(calories=None, protein_g=None, carbs_g=None,
                              fat_g=None, fiber_g=None, sodium_mg=None, sugar_g=None)
    client = _FakeClient(parsed_output=parsed)

    result = estimate_missing_nutrition("Mystery Dish", "", ["calories"], client=client)

    assert result == {}


def test_estimate_missing_nutrition_returns_empty_on_client_exception():
    client = _FakeClient(raises=True)
    result = estimate_missing_nutrition("Grilled Chicken", "chicken", ["calories"], client=client)
    assert result == {}


def test_estimate_missing_nutrition_returns_empty_when_not_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from services.menu_ingestion import llm_enrichment
    llm_enrichment.reset_client()

    result = estimate_missing_nutrition("Grilled Chicken", "chicken", ["calories"])  # no client injected
    assert result == {}


# ── extract_allergens_from_ingredients ──────────────────────────────────────

def test_extract_allergens_returns_none_for_empty_ingredients():
    client = _FakeClient(parsed_output=SimpleNamespace(allergens=["dairy"], confidence=0.99))
    assert extract_allergens_from_ingredients("Mystery Dish", "", client=client) is None
    assert extract_allergens_from_ingredients("Mystery Dish", "   ", client=client) is None
    assert extract_allergens_from_ingredients("Mystery Dish", None, client=client) is None


def test_extract_allergens_lowercases_and_filters_unknown_values():
    parsed = SimpleNamespace(allergens=["Dairy", "GLUTEN", "unicorn_dust"], confidence=0.95)
    client = _FakeClient(parsed_output=parsed)

    result = extract_allergens_from_ingredients("Grilled Cheese", "bread, cheese, butter", client=client)

    assert result.allergens == ["dairy", "gluten"]
    assert result.confidence == 0.95


def test_extract_allergens_passes_through_low_confidence_unfiltered():
    """This function reports confidence, it does not enforce a threshold —
    that's the caller's job (bon_appetit.py). A low-confidence result
    still comes back, just with its real number attached."""
    parsed = SimpleNamespace(allergens=["soy"], confidence=0.4)
    client = _FakeClient(parsed_output=parsed)

    result = extract_allergens_from_ingredients("Mystery Dish", "soy-based sauce", client=client)

    assert result.confidence == 0.4
    assert result.confidence < ALLERGEN_CONFIDENCE_THRESHOLD
    assert result.allergens == ["soy"]


def test_extract_allergens_returns_none_on_client_exception():
    client = _FakeClient(raises=True)
    result = extract_allergens_from_ingredients("Grilled Cheese", "bread, cheese", client=client)
    assert result is None


def test_extract_allergens_returns_none_when_not_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from services.menu_ingestion import llm_enrichment
    llm_enrichment.reset_client()

    result = extract_allergens_from_ingredients("Grilled Cheese", "bread, cheese")  # no client injected
    assert result is None


def test_get_client_raises_when_not_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from services.menu_ingestion import llm_enrichment
    llm_enrichment.reset_client()

    with pytest.raises(AnthropicNotConfiguredError):
        llm_enrichment._get_client()
