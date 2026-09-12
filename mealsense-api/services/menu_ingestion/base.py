"""
Shared interface every campus-specific ingestion adapter implements.

Onboarding a new school means writing one adapter's `normalize()` method
against whatever shape its feed actually arrives in (a vendor API response,
a CSV, or an ad hoc JSON export) — never touching the recommendation engine
or anything downstream of this layer.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class RejectedRecord:
    """One raw record that could not be safely normalized, and why."""
    raw: Any
    reason: str


@dataclass
class ReviewNote:
    """An item that WAS accepted into `items`, but still needs a human to
    double-check something about it — e.g. an LLM-extracted allergen list
    that cleared the confidence bar but wasn't verified by a person
    (services/menu_ingestion/llm_enrichment.py, tasks.md 3.6). Distinct
    from RejectedRecord: this item is already live, not excluded."""
    item_id: str
    reason: str
    detail: Any = None


@dataclass
class IngestionResult:
    """Output of running a raw feed through an adapter."""
    items: list[dict] = field(default_factory=list)
    rejected: list[RejectedRecord] = field(default_factory=list)
    review_notes: list[ReviewNote] = field(default_factory=list)

    @property
    def accepted_count(self) -> int:
        return len(self.items)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)


class MenuAdapter(Protocol):
    """Any campus-specific adapter implements this. `raw` is whatever shape
    that campus's feed actually is — this class doesn't constrain it."""

    def normalize(self, raw: Any) -> IngestionResult:
        ...
