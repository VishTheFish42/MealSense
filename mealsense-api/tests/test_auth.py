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


def test_default_verifier_without_credentials_raises_runtime_error(monkeypatch):
    """The real verify_id_token path (not the injected fake used everywhere
    above) needs firebase_admin initialized with a real service account —
    found via a live manual test hitting this exact gap: nothing in the
    codebase ever called firebase_admin.initialize_app() before this fix."""
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    from services.auth import _default_verifier
    with pytest.raises(RuntimeError, match="GOOGLE_APPLICATION_CREDENTIALS"):
        _default_verifier("some-token")
