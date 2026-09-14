"""
Firestore-backed menu storage. Layout: menus/{servedOn}/items/{itemId},
one subcollection per calendar day, so "today's menu" is a single
collection read. `servedOn` is supplied by the caller (the upload
endpoint) at write time — it is not parsed per-item by the
menu_ingestion adapters, which stay date-agnostic.
"""
from __future__ import annotations

from data.sample_menu import SAMPLE_MENU
from .firestore_client import FirestoreNotConfiguredError, get_firestore_client


def _items_collection(served_on: str):
    db = get_firestore_client()
    return db.collection("menus").document(served_on).collection("items")


def get_menu_for_date(served_on: str) -> list[dict]:
    """Returns the normalized menu for the given date (YYYY-MM-DD).
    Falls back to the static sample menu if nothing has been uploaded for
    that date yet, or if Firestore isn't configured in this environment at
    all — the app should never show an empty menu just because no admin
    has uploaded today's feed. A genuine Firestore connection/permissions
    error is not caught here and will propagate, not be masked."""
    try:
        docs = list(_items_collection(served_on).stream())
    except FirestoreNotConfiguredError:
        return SAMPLE_MENU
    if not docs:
        return SAMPLE_MENU
    return [d.to_dict() for d in docs]


def write_menu_items(served_on: str, items: list[dict]) -> None:
    """Batch-writes normalized menu items for a given date. Each item's
    own `id` (from menu_ingestion.schema.stable_item_id) is used as the
    Firestore document ID, so re-uploading the same day's menu overwrites
    matching dishes instead of duplicating them.

    Uses a merge write, not a full overwrite: ingestion (build_menu_item)
    never sets a `sold_out` field at all — that's only ever set by
    set_item_availability below — so a merge write means re-syncing a
    vendor feed or re-uploading a CSV mid-day updates every field the
    source actually supplies (fresh nutrition, price, etc.) without
    silently resetting a dish staff already marked sold out back to
    available."""
    if not items:
        return
    db = get_firestore_client()
    collection = _items_collection(served_on)
    batch = db.batch()
    for item in items:
        batch.set(collection.document(item["id"]), item, merge=True)
    batch.commit()


def set_item_availability(served_on: str, item_id: str, sold_out: bool) -> None:
    """Toggles an item's sold-out status without re-ingesting the whole
    record — README §9.5 / design-spec.md §7.3's "mark items sold out in
    real time." Uses `update`, not `set`, so this raises
    google.api_core.exceptions.NotFound for an item that was never
    actually ingested for this date, rather than silently creating a bare
    {"sold_out": ...} stub document."""
    db = get_firestore_client()
    _items_collection(served_on).document(item_id).update({"sold_out": sold_out})
