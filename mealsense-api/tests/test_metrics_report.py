"""
Tests scripts/metrics_report.py against a real local Firestore emulator,
same reasoning as test_menu_store.py. Requires the emulator running first:
    cd mealsense-app && npx firebase emulators:start --only firestore
Skips cleanly with a clear reason if it isn't reachable.
"""
import socket
import uuid

import pytest

from scripts.metrics_report import (
    _pct,
    _percentile,
    feedback_metrics,
    order_conversion_rate,
    profile_completion_rate,
    time_to_recommendation_ms,
)

EMULATOR_HOST = "127.0.0.1"
EMULATOR_PORT = 8080


def _emulator_is_running() -> bool:
    try:
        with socket.create_connection((EMULATOR_HOST, EMULATOR_PORT), timeout=0.5):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _emulator_is_running(),
    reason=(
        "Firestore emulator not reachable at 127.0.0.1:8080 — start it with "
        "`cd mealsense-app && npx firebase emulators:start --only firestore` first"
    ),
)


@pytest.fixture(autouse=True)
def emulator_env(monkeypatch):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", f"{EMULATOR_HOST}:{EMULATOR_PORT}")
    from services import firestore_client
    firestore_client.reset_firestore_client()
    yield
    firestore_client.reset_firestore_client()


def _uid() -> str:
    return f"test-{uuid.uuid4().hex}"


# ── _pct / _percentile: pure logic ──────────────────────────────────────────

def test_pct_formats_ratio():
    assert _pct(3, 4) == "3/4 (75.0%)"


def test_pct_handles_zero_denominator():
    assert _pct(0, 0) == "n/a (no data yet)"


def test_percentile_p95_of_sorted_values():
    values = list(range(1, 101))  # 1..100
    assert _percentile(values, 0.95) == 96  # index 95 (0-based) of sorted list


# ── profile_completion_rate ──────────────────────────────────────────────

def test_profile_completion_rate():
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    completed_uid, incomplete_uid = _uid(), _uid()
    db.collection("users").document(completed_uid).set({"onboardingComplete": True})
    db.collection("users").document(incomplete_uid).set({"onboardingComplete": False})

    completed, total = profile_completion_rate(db)
    assert completed >= 1
    assert total >= completed


# ── feedback_metrics ─────────────────────────────────────────────────────

def test_feedback_metrics_counts_correctly():
    from services.recommendation_history import set_feedback, write_recommendation
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    student = _uid()
    rec_up = write_recommendation(student, "item-1", 90.0, "lunch")
    rec_down = write_recommendation(student, "item-2", 60.0, "lunch")
    write_recommendation(student, "item-3", 50.0, "lunch")  # no feedback
    set_feedback(rec_up, "thumbs_up")
    set_feedback(rec_down, "thumbs_down")

    metrics = feedback_metrics(db)
    assert metrics["total_recommendations"] >= 3
    assert metrics["feedback_count"] >= 2
    assert metrics["thumbs_up_count"] >= 1


# ── time_to_recommendation_ms ────────────────────────────────────────────

def test_time_to_recommendation_ms_only_counts_matching_type():
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    student = _uid()
    db.collection("analytics_events").add({
        "type": "recommendation_fetch", "studentId": student, "durationMs": 1234,
    })
    db.collection("analytics_events").add({
        "type": "some_other_event", "studentId": student, "durationMs": 9999,
    })

    durations = time_to_recommendation_ms(db)
    assert 1234 in durations
    assert 9999 not in durations


# ── order_conversion_rate ────────────────────────────────────────────────

def test_order_conversion_rate_counts_orders_with_matching_recommendation_id():
    from services.recommendation_history import write_recommendation
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    student = _uid()
    rec_id = write_recommendation(student, "item-1", 90.0, "lunch")
    write_recommendation(student, "item-2", 80.0, "lunch")  # never ordered

    db.collection("orders").add({
        "studentId": student, "items": [], "totalPrice": 9.0,
        "status": "placed", "recommendationId": rec_id,
    })
    db.collection("orders").add({
        "studentId": student, "items": [], "totalPrice": 5.0,
        "status": "placed",  # no recommendationId — ordered an alternative
    })

    converted, total_recs = order_conversion_rate(db)
    assert converted >= 1
    assert total_recs >= 2


# ── main(): full orchestration smoke test ───────────────────────────────

def test_main_prints_a_report_without_crashing(capsys):
    """Seeds a bit of everything so main() exercises every branch (the
    'has data' path for every metric, not just the 'n/a' fallbacks)."""
    from scripts.metrics_report import main
    from services.recommendation_history import set_feedback, write_recommendation
    from services.firestore_client import get_firestore_client
    db = get_firestore_client()

    student = _uid()
    db.collection("users").document(student).set({"onboardingComplete": True})
    rec_id = write_recommendation(student, "item-1", 90.0, "lunch")
    set_feedback(rec_id, "thumbs_up")
    db.collection("analytics_events").add({
        "type": "recommendation_fetch", "studentId": student, "durationMs": 1500,
    })
    db.collection("orders").add({
        "studentId": student, "items": [], "totalPrice": 9.0,
        "status": "placed", "recommendationId": rec_id,
    })

    main()

    output = capsys.readouterr().out
    assert "MealSense Metrics Report" in output
    assert "Profile completion rate" in output
    assert "Order conversion rate" in output
