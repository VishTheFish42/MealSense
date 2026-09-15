"""
Tests require_kitchen_role's own role-check logic against a real Firestore
emulator. Token *verification* itself is not re-tested here — we trust
firebase_admin's own tested code for that, and inject a fake verifier so
these tests don't need a live Auth emulator and real minted tokens.
"""
import socket

import pytest
from fastapi import HTTPException

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


def _seed_user(uid: str, role: str):
    from services.firestore_client import get_firestore_client
    get_firestore_client().collection("users").document(uid).set({"role": role})


def test_missing_authorization_header_raises_401():
    from services.auth import require_kitchen_role
    with pytest.raises(HTTPException) as exc_info:
        require_kitchen_role(authorization=None)
    assert exc_info.value.status_code == 401


def test_empty_authorization_header_raises_401():
    from services.auth import require_kitchen_role
    with pytest.raises(HTTPException) as exc_info:
        require_kitchen_role(authorization="")
    assert exc_info.value.status_code == 401


def test_malformed_authorization_header_raises_401():
    from services.auth import require_kitchen_role
    with pytest.raises(HTTPException) as exc_info:
        require_kitchen_role(authorization="not-a-bearer-token")
    assert exc_info.value.status_code == 401


def test_verifier_exception_raises_401():
    from services.auth import require_kitchen_role

    def failing_verifier(token):
        raise ValueError("bad token")

    with pytest.raises(HTTPException) as exc_info:
        require_kitchen_role(authorization="Bearer whatever", verify_id_token=failing_verifier)
    assert exc_info.value.status_code == 401


def test_decoded_token_missing_uid_raises_401():
    from services.auth import require_kitchen_role
    with pytest.raises(HTTPException) as exc_info:
        require_kitchen_role(authorization="Bearer whatever", verify_id_token=lambda token: {})
    assert exc_info.value.status_code == 401


def test_uid_with_student_role_raises_403():
    from services.auth import require_kitchen_role
    _seed_user("student-uid", "student")

    with pytest.raises(HTTPException) as exc_info:
        require_kitchen_role(
            authorization="Bearer whatever",
            verify_id_token=lambda token: {"uid": "student-uid"},
        )
    assert exc_info.value.status_code == 403


def test_nonexistent_uid_raises_403():
    from services.auth import require_kitchen_role
    with pytest.raises(HTTPException) as exc_info:
        require_kitchen_role(
            authorization="Bearer whatever",
            verify_id_token=lambda token: {"uid": "no-such-user"},
        )
    assert exc_info.value.status_code == 403


def test_uid_with_kitchen_role_succeeds():
    from services.auth import require_kitchen_role
    _seed_user("kitchen-uid", "kitchen")

    uid = require_kitchen_role(
        authorization="Bearer whatever",
        verify_id_token=lambda token: {"uid": "kitchen-uid"},
    )
    assert uid == "kitchen-uid"


def _reset_firebase_admin_apps():
    """firebase_admin caches its initialized app(s) at module scope —
    _ensure_firebase_admin_initialized() no-ops if one already exists, so
    tests exercising the two different initialization branches below need
    a clean slate between them, not just between test files."""
    import firebase_admin
    for name in list(firebase_admin._apps):
        firebase_admin.delete_app(firebase_admin._apps[name])


def test_ensure_firebase_admin_initialized_uses_explicit_key_file_when_set(monkeypatch):
    from unittest.mock import MagicMock, patch

    _reset_firebase_admin_apps()
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/fake/path/key.json")
    monkeypatch.delenv("K_SERVICE", raising=False)
    from services.auth import _ensure_firebase_admin_initialized

    fake_creds = MagicMock()
    try:
        with patch("firebase_admin.credentials.Certificate", return_value=fake_creds) as mock_cert:
            with patch("firebase_admin.initialize_app") as mock_init:
                _ensure_firebase_admin_initialized()
        mock_cert.assert_called_once_with("/fake/path/key.json")
        mock_init.assert_called_once_with(fake_creds)
    finally:
        _reset_firebase_admin_apps()


def test_ensure_firebase_admin_initialized_falls_back_to_adc_on_cloud_run(monkeypatch):
    """The actual fix (tasks.md Phase 7): without an explicit key file,
    but genuinely running on Cloud Run (K_SERVICE set), this must still
    initialize successfully via Application Default Credentials — what
    Cloud Run provides automatically — rather than raising RuntimeError,
    which is what made every /admin/* request fail with a misleading 401
    "Invalid or expired token" before this existed (the real error was
    swallowed by require_kitchen_role's generic `except Exception`, never
    surfaced as what it actually was)."""
    from unittest.mock import patch

    _reset_firebase_admin_apps()
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("K_SERVICE", "mealsense-api")
    from services.auth import _ensure_firebase_admin_initialized

    try:
        with patch("firebase_admin.initialize_app") as mock_init:
            _ensure_firebase_admin_initialized()
        mock_init.assert_called_once_with()  # no credential arg — ADC fallback
    finally:
        _reset_firebase_admin_apps()


def test_ensure_firebase_admin_initialized_refuses_bare_adc_off_cloud_run(monkeypatch):
    """tasks.md Phase 7.3: the bare-ADC fallback must be refused outright
    off Cloud Run, even if this machine happens to have real gcloud ADC
    credentials configured for unrelated reasons (e.g. deploying) — same
    fix, same reasoning as firestore_client.py's K_SERVICE gate
    (test_firestore_client.py). Without this, local dev could initialize
    Firebase Admin against real production identity, not just a
    misleading-but-harmless failure."""
    from unittest.mock import patch

    _reset_firebase_admin_apps()
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    from services.auth import _ensure_firebase_admin_initialized

    try:
        with patch("firebase_admin.initialize_app") as mock_init:
            with pytest.raises(RuntimeError):
                _ensure_firebase_admin_initialized()
        mock_init.assert_not_called()
    finally:
        _reset_firebase_admin_apps()
