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
    matching dishes instead of duplicating them."""
    if not items:
        return
    db = get_firestore_client()
    collection = _items_collection(served_on)
    batch = db.batch()
    for item in items:
        batch.set(collection.document(item["id"]), item)
    batch.commit()
