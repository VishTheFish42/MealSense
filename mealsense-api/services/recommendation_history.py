"""
Persists a record of each top recommendation actually served to a
student, so thumbs-up/down feedback (README §9.2, design-spec.md §3.3 /
§14.2 Step 4) has something to attach to. /recommendation was previously
fully stateless (design-spec.md §2.3's deliberate "no cache invalidation"
design) — this is the first write it ever makes, and it's additive:
scoring, hard filtering, and menu reads are all unchanged.

Scoped to the top recommendation only, never the alternatives — the
bandit's reward signal (design-spec.md §14.2 Step 4) rewards "the
recommended item," singular, and only has a causal story for the one
item actually served; there's no clean interpretation for feedback on an
item the scoring function didn't choose to serve.
"""
from __future__ import annotations
from datetime import datetime, timezone

from .firestore_client import get_firestore_client

_COLLECTION = "recommendation_history"
VALID_FEEDBACK = {"thumbs_up", "thumbs_down"}


def write_recommendation(
    student_id: str, menu_item_id: str, menu_item_name: str, score: float, meal_period: str
) -> str:
    """Writes one history record for a served top recommendation. Returns
    the new document's id — the client references this id when later
    submitting feedback via set_feedback.

    menu_item_name is denormalized (stored here, not just looked up via
    menu_item_id) for tasks.md 4.4's aggregate reporting: recommendation
    history spans many days, each with its own menus/{date}/items
    subcollection, so there's no single "today's menu" to resolve a
    historical id against. Storing the name at write time is the simplest
    correct fix — the alternative (join against every day's menu at
    report time) is real complexity this reporting feature doesn't need."""
    db = get_firestore_client()
    doc_ref = db.collection(_COLLECTION).document()
    doc_ref.set({
        "studentId": student_id,
        "menuItemId": menu_item_id,
        "menuItemName": menu_item_name,
        "score": score,
        "mealPeriod": meal_period,
        "recommendedAt": datetime.now(timezone.utc).isoformat(),
        "feedback": None,
    })
    return doc_ref.id


def set_feedback(recommendation_id: str, feedback: str) -> None:
    """Raises ValueError for an invalid feedback value, and
    google.api_core.exceptions.NotFound for a recommendation_id that
    doesn't exist — same fail-loud stance as
    menu_store.py::set_item_availability. Changeable, not one-shot: a
    second call with a different value simply overwrites the first."""
    if feedback not in VALID_FEEDBACK:
        raise ValueError(f"feedback must be one of {sorted(VALID_FEEDBACK)}, got {feedback!r}")
    db = get_firestore_client()
    db.collection(_COLLECTION).document(recommendation_id).update({"feedback": feedback})


def get_recommendation(recommendation_id: str) -> dict | None:
    """Test/verification helper — also the read path a future
    recommendation-history view (README §9.4, still unbuilt) would need.
    Returns None rather than raising for an unknown id, since "does this
    exist" is a legitimate question here, not necessarily an error."""
    db = get_firestore_client()
    doc = db.collection(_COLLECTION).document(recommendation_id).get()
    if not doc.exists:
        return None
    return {"id": doc.id, **doc.to_dict()}
