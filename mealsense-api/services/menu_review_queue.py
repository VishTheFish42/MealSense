"""
Admin review queue for menu items that could not be safely auto-accepted.
Today this specifically means items rejected for missing/unverified
allergen data — design-spec.md §7.0a's case 3 ("no ingredient text to
reason from at all... written to an admin review queue"), and the vendor
allergen-trust policy decided for the Bon Appétit adapter (tasks.md 3.4):
an item with no allergen-relevant icon is `allergens=None`, gets rejected
by build_menu_item, and lands here instead of being silently dropped.

There's no admin UI reading this yet (tasks.md Phase 4 — the Admin
Dashboard is still unbuilt). This is the backend plumbing that UI will
eventually read from; get_review_queue() exists now so the queue is
actually readable and testable, not just a write-only sink.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from google.cloud.firestore_v1.base_query import FieldFilter

from .firestore_client import get_firestore_client

_COLLECTION = "menu_review_queue"


def write_review_items(campus_id: str, served_on: str, rejected: list[dict]) -> int:
    """`rejected` is a list of {"raw": ..., "reason": ...} dicts (the same
    shape RejectedRecord serializes to elsewhere in this codebase). Returns
    the number of documents written. No-ops (returns 0) if Firestore isn't
    configured in this environment — mirrors menu_store.py's own
    offline-fallback stance: a missing review queue is a soft failure here,
    not a reason to break ingestion for anyone not running against real
    Firestore. A genuine connection/permissions error still propagates."""
    if not rejected:
        return 0

    db = get_firestore_client()
    collection = db.collection(_COLLECTION)
    batch = db.batch()
    now = datetime.now(timezone.utc).isoformat()
    for entry in rejected:
        doc_id = uuid.uuid4().hex
        batch.set(collection.document(doc_id), {
            "campusId": campus_id,
            "servedOn": served_on,
            "raw": entry["raw"],
            "reason": entry["reason"],
            "resolved": False,
            "createdAt": now,
        })
    batch.commit()
    return len(rejected)


def get_review_queue(campus_id: str | None = None, resolved: bool = False) -> list[dict]:
    """Lists queue entries, filtered by campus (optional) and resolution
    status (defaults to unresolved-only — what an admin view would want
    first). Pass resolved=None for both."""
    db = get_firestore_client()
    query = db.collection(_COLLECTION)
    if campus_id is not None:
        query = query.where(filter=FieldFilter("campusId", "==", campus_id))
    if resolved is not None:
        query = query.where(filter=FieldFilter("resolved", "==", resolved))
    return [{"id": d.id, **d.to_dict()} for d in query.stream()]


def resolve_review_item(doc_id: str, allergens: list[str]) -> None:
    """Marks a queue entry resolved after a human has confirmed the item's
    real allergen list. Doesn't write the confirmed item back into the
    live menu itself — that's a deliberate scope cut: re-ingestion is a
    product decision (which served_on date(s) does the confirmation apply
    to?) belonging to the Phase 4 admin dashboard, not this plumbing."""
    db = get_firestore_client()
    db.collection(_COLLECTION).document(doc_id).update({
        "resolved": True,
        "confirmedAllergens": allergens,
    })
