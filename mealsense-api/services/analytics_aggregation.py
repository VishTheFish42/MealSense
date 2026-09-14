"""
Aggregate anonymized stats for the admin dashboard — README §9.5, the
GET /v1/admin/analytics endpoint design-spec.md §4.4 already sketched but
never built, tasks.md 4.4.

Computed live, by scanning recommendation_history and users on each
request — deliberately naive for now, matching tasks.md 4.4's own
framing ("don't do this as a naive per-request scan once order volume is
nonzero" — it isn't yet, for this pilot). If real usage ever makes this
slow, the fix is a scheduled nightly rollup writing to a small
pre-aggregated doc, not optimizing this scan in place; there's no
scheduler infrastructure in this project yet (tasks.md Phase 7) to build
that against.

Anonymized: no student uid, name, or email appears anywhere in either
function's output — only counts.
"""
from __future__ import annotations
from collections import Counter

# A student who picks "None" for allergies/conditions/etc. gets this
# written as a sentinel before EditPreferencesScreen.tsx/OnboardingScreen.tsx
# filter it back out on save — it should never actually reach Firestore,
# but excluding it here too is a cheap, harmless safety net against ever
# surfacing a meaningless "none: 12" row to dining staff.
_NONE_SENTINEL = "none"


def most_recommended_items(db, limit: int = 10) -> list[dict]:
    """[{menu_item_id, name, count}, ...], most-recommended first.
    `name` is whatever was denormalized onto the record at write time
    (services/recommendation_history.py::write_recommendation) — history
    spans many days, each with its own menus/{date}/items subcollection,
    so there's no single "today's menu" to resolve an older id against."""
    docs = [d.to_dict() for d in db.collection("recommendation_history").stream()]

    counts: Counter = Counter()
    names: dict[str, str] = {}
    for d in docs:
        item_id = d.get("menuItemId")
        if not item_id:
            continue
        counts[item_id] += 1
        if item_id not in names and d.get("menuItemName"):
            names[item_id] = d["menuItemName"]

    return [
        {"menu_item_id": item_id, "name": names.get(item_id, item_id), "count": count}
        for item_id, count in counts.most_common(limit)
    ]


def common_dietary_constraints(db) -> dict[str, list[dict]]:
    """{"allergies": [{value, count}, ...], "dietary_identity": [...],
    "conditions": [...], "nutritional_focus": [...]} — each list sorted
    most-common first. Students only (a kitchen account's own dietary
    fields, if any, aren't campus dietary data)."""
    docs = [
        d.to_dict()
        for d in db.collection("users").stream()
        if d.to_dict().get("role") == "student"
    ]

    def _tally(field: str) -> list[dict]:
        counter: Counter = Counter()
        for doc in docs:
            for value in doc.get(field) or []:
                if value and value.strip().lower() != _NONE_SENTINEL:
                    counter[value] += 1
        return [{"value": value, "count": count} for value, count in counter.most_common()]

    return {
        "allergies": _tally("allergies"),
        "dietary_identity": _tally("dietaryIdentity"),
        "conditions": _tally("conditions"),
        "nutritional_focus": _tally("nutritionalFocus"),
    }
