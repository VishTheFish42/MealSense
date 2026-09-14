"""
Computes the README.md §14 success metrics this project can actually
measure — the ones tasks.md Phase 8 instrumented. Deliberately a script,
not a dashboard (tasks.md 8.3: "even a script that queries Firestore,
doesn't need to be a dashboard"). Run with:

    cd mealsense-api && venv/bin/python -m scripts.metrics_report

Needs real Firestore access — GOOGLE_APPLICATION_CREDENTIALS for a real
project, or FIRESTORE_EMULATOR_HOST for local/demo data (same
configuration as services/firestore_client.py; this script uses it
directly, no separate credential path).

Four of README §14's nine metrics are deliberately out of scope here:
- Allergen-safe recommendation rate: a structural guarantee enforced by
  the hard filter itself (recommendation_engine.py::_passes_hard_filters),
  not something live instrumentation would reveal — proven by that
  module's own test suite, not by querying production data.
- Weekly active users, order status accuracy: not part of Phase 8's
  agreed scope (tasks.md 8.2 names profile completion, time-to-
  recommendation, and order conversion specifically).
- ML thumbs-up rate vs. heuristic baseline: meaningless until Phase 6
  (the bandit) exists at all.
"""
from __future__ import annotations

from google.cloud.firestore_v1.base_query import FieldFilter

from services.firestore_client import get_firestore_client


def profile_completion_rate(db) -> tuple[int, int]:
    """(completed, total) — README §14 target: >70% of new users."""
    docs = [d.to_dict() for d in db.collection("users").stream()]
    completed = sum(1 for d in docs if d.get("onboardingComplete"))
    return completed, len(docs)


def feedback_metrics(db) -> dict:
    """Feedback submission rate (target >30%) and, among those with
    feedback, the thumbs-up rate (README §14's "recommendation relevance,"
    target >75%) — both derived from tasks.md 8.0's recommendation_history,
    no separate instrumentation needed."""
    docs = [d.to_dict() for d in db.collection("recommendation_history").stream()]
    with_feedback = [d for d in docs if d.get("feedback")]
    thumbs_up = sum(1 for d in with_feedback if d["feedback"] == "thumbs_up")
    return {
        "total_recommendations": len(docs),
        "feedback_count": len(with_feedback),
        "thumbs_up_count": thumbs_up,
    }


def time_to_recommendation_ms(db) -> list[float]:
    """README §14 target: <5000ms. Reads tasks.md 8.2's
    analytics_events(type='recommendation_fetch') collection."""
    docs = db.collection("analytics_events").where(
        filter=FieldFilter("type", "==", "recommendation_fetch")
    ).stream()
    return [d.to_dict()["durationMs"] for d in docs if "durationMs" in d.to_dict()]


def order_conversion_rate(db) -> tuple[int, int]:
    """(converted, total_recommendations) — README §14 target: >60%.
    "Converted" means the recommendation's id shows up on a placed order's
    recommendationId field (tasks.md 8.2 — set only when the order was
    placed straight from the top pick, never an alternative). Reads the
    whole orders collection rather than a `!=` Firestore query, since most
    orders simply won't have this field at all (absent, not null) —
    `!=` semantics against a missing field are easy to get subtly wrong,
    and this script isn't meant to scale past a small demo dataset."""
    total_recs = len(list(db.collection("recommendation_history").stream()))
    converted_ids = {
        rec_id
        for d in db.collection("orders").stream()
        if (rec_id := d.to_dict().get("recommendationId"))
    }
    return len(converted_ids), total_recs


def _pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a (no data yet)"
    return f"{numerator}/{denominator} ({100 * numerator / denominator:.1f}%)"


def _percentile(values: list[float], p: float) -> float:
    s = sorted(values)
    idx = min(int(len(s) * p), len(s) - 1)
    return s[idx]


def main() -> None:
    db = get_firestore_client()

    print("=== MealSense Metrics Report (README.md §14) ===\n")

    completed, total_users = profile_completion_rate(db)
    print(f"Profile completion rate      (target >70%):  {_pct(completed, total_users)}")

    feedback = feedback_metrics(db)
    print(f"Feedback submission rate     (target >30%):  "
          f"{_pct(feedback['feedback_count'], feedback['total_recommendations'])}")
    if feedback["feedback_count"] > 0:
        print(f"Recommendation relevance     (target >75%):  "
              f"{_pct(feedback['thumbs_up_count'], feedback['feedback_count'])}")
    else:
        print("Recommendation relevance     (target >75%):  n/a (no feedback yet)")

    durations = time_to_recommendation_ms(db)
    if durations:
        avg = sum(durations) / len(durations)
        p95 = _percentile(durations, 0.95)
        print(f"Time to recommendation       (target <5000ms): avg {avg:.0f}ms, "
              f"p95 {p95:.0f}ms (n={len(durations)})")
    else:
        print("Time to recommendation       (target <5000ms): n/a (no data yet)")

    converted, total_recs = order_conversion_rate(db)
    print(f"Order conversion rate        (target >60%):  {_pct(converted, total_recs)}")


if __name__ == "__main__":
    main()
