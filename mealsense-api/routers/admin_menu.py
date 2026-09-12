from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from services.auth import require_kitchen_role
from services.menu_ingestion.csv_adapter import CsvMenuAdapter
from services.menu_ingestion.messy_json_adapter import MessyJsonMenuAdapter
from services.menu_store import write_menu_items
from services.menu_review_queue import write_review_items
from services.vendor_ingestion.campus_config import get_campus_config
from services.vendor_ingestion.bon_appetit import fetch_campus_menu

router = APIRouter()

_ADAPTERS = {
    "csv": CsvMenuAdapter(),
    "messy_json": MessyJsonMenuAdapter(),
}

# Registered by vendor key (CampusConfig.vendor), not by campus — adding a
# new campus on an already-supported vendor needs no change here at all,
# only a new entry in vendor_ingestion/campus_config.py.
_VENDOR_FETCHERS = {
    "bon_appetit": fetch_campus_menu,
}


@router.post("/admin/menu/upload")
async def upload_menu(
    request: Request,
    format: str = Query(..., description="csv or messy_json"),
    served_on: str | None = Query(None, description="YYYY-MM-DD, defaults to today"),
    uid: str = Depends(require_kitchen_role),
):
    adapter = _ADAPTERS.get(format)
    if adapter is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format: {format!r}. Must be one of {sorted(_ADAPTERS)}",
        )

    if format == "csv":
        raw = (await request.body()).decode("utf-8")
    else:
        raw = await request.json()

    result = adapter.normalize(raw)
    write_menu_items(served_on or date.today().isoformat(), result.items)

    return {
        "accepted": result.accepted_count,
        "rejected": [{"raw": r.raw, "reason": r.reason} for r in result.rejected],
    }


@router.post("/admin/menu/sync-vendor")
async def sync_vendor_menu(
    campus: str = Query(..., description="Campus id, e.g. santa_clara — see vendor_ingestion/campus_config.py"),
    served_on: str | None = Query(None, description="YYYY-MM-DD, defaults to today"),
    uid: str = Depends(require_kitchen_role),
):
    """Pulls today's live menu directly from a campus's dining vendor
    (README §7.2 priority #1) instead of a manual CSV/JSON upload. One
    endpoint for every campus+vendor combination in campus_config.py — see
    that module's docstring for what "onboard a new school" means here."""
    try:
        campus_config = get_campus_config(campus)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    fetcher = _VENDOR_FETCHERS.get(campus_config.vendor)
    if fetcher is None:
        raise HTTPException(
            status_code=500,
            detail=f"No adapter registered for vendor {campus_config.vendor!r}",
        )

    result = fetcher(campus_config)
    served_on = served_on or date.today().isoformat()
    write_menu_items(served_on, result.items)

    # Only allergen-related rejections are the review queue's concern
    # (design-spec.md §7.0a case 3) — a fetch failure or a bad meal_period
    # value isn't something a human confirming allergens can act on.
    allergen_rejections = [
        {"raw": r.raw, "reason": r.reason}
        for r in result.rejected
        if "allergen" in r.reason.lower()
    ]
    # Items ALREADY accepted still get queued here too when an LLM (not a
    # human, not a vendor-supplied cor_icon) is why they were accepted at
    # all — tasks.md 3.6's decision: an AI-confident item still gets a
    # human double-check, it just isn't blocked pending one.
    review_note_entries = [
        {"raw": {"item_id": n.item_id, **(n.detail or {})}, "reason": n.reason}
        for n in result.review_notes
    ]
    queued = write_review_items(
        campus_config.campus_id, served_on, allergen_rejections + review_note_entries
    )

    return {
        "accepted": result.accepted_count,
        "rejected": [{"raw": r.raw, "reason": r.reason} for r in result.rejected],
        "queued_for_review": queued,
    }
