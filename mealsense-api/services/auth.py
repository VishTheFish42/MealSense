"""
Gatekeeping for admin-only routes (currently just menu upload). No `admin`
role exists in the system yet — Phase 4 (tasks.md) is what formalizes real
admin accounts. Reusing the existing `kitchen` role here is a deliberate,
narrow scope decision, not an assumption that kitchen staff and admins are
the same thing long-term.

verify_id_token is a parameter (not a hardcoded call to
firebase_admin.auth.verify_id_token) so tests can supply a fake verifier
and exercise our own role-check logic against the Firestore emulator,
without needing a live Auth emulator and real minted tokens — we trust
firebase_admin's own tested code to correctly validate a token signature;
what's actually ours to test is what happens with the uid afterward.
"""
from __future__ import annotations
import os
from typing import Callable

from fastapi import Header, HTTPException

from .firestore_client import get_firestore_client

TokenVerifier = Callable[[str], dict]


def _ensure_firebase_admin_initialized() -> None:
    """firebase_admin.auth.verify_id_token needs a default app to exist first
    — nothing else in this codebase calls initialize_app(), since Firestore
    access deliberately goes through google.cloud.firestore.Client directly
    instead (see firestore_client.py). This is the one place that actually
    needs firebase_admin proper, for real ID token verification.

    Falls back to Application Default Credentials when
    GOOGLE_APPLICATION_CREDENTIALS isn't set — the same fix
    firestore_client.py needed for Cloud Run (tasks.md Phase 7), which
    provides ADC automatically via its metadata server, no key file to
    manage. Before this existed, every /admin/* request would have failed
    on Cloud Run with a misleading 401 "Invalid or expired token" — the
    real problem (this app never initializing at all) was a RuntimeError
    silently swallowed by require_kitchen_role's generic
    `except Exception`, not a real token or auth failure.

    The bare-ADC fallback is gated on K_SERVICE (tasks.md Phase 7.3),
    same as firestore_client.py and for the same reason: without the
    gate, this also succeeds on a developer machine that merely has
    `gcloud auth application-default login` credentials configured for
    unrelated reasons, not just on real Cloud Run. require_kitchen_role
    still calls get_firestore_client() for its role check regardless, so
    that fix already blocks real production data access from local dev —
    this gate closes the same bug class here too, so local dev fails
    the same clean, expected way instead of only being accidentally safe
    downstream."""
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        return

    key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if key_path:
        firebase_admin.initialize_app(credentials.Certificate(key_path))
    elif os.environ.get("K_SERVICE"):
        # No explicit key file, but genuinely running on Cloud Run —
        # initialize_app() with no credential argument resolves
        # Application Default Credentials automatically.
        firebase_admin.initialize_app()
    else:
        # Not Cloud Run and no explicit key file: refuse rather than
        # silently trying bare ADC. If this ever legitimately needs to
        # raise at use time instead (e.g. a future case with no good
        # env-var signal), that's the same "misleading 401" outcome as
        # before Phase 7 existed at all — not a regression.
        raise RuntimeError(
            "Firebase Admin has no credentials: GOOGLE_APPLICATION_CREDENTIALS "
            "is unset and this isn't Cloud Run (K_SERVICE unset). Set "
            "GOOGLE_APPLICATION_CREDENTIALS explicitly to test real admin auth "
            "locally on purpose."
        )


def _default_verifier(token: str) -> dict:
    _ensure_firebase_admin_initialized()
    from firebase_admin import auth as firebase_auth
    return firebase_auth.verify_id_token(token)


def require_kitchen_role(
    authorization: str | None = Header(None),
    verify_id_token: TokenVerifier = _default_verifier,
) -> str:
    """FastAPI dependency: returns the requesting account's uid if it has
    the kitchen role, otherwise raises 401/403. Override this dependency
    in tests via app.dependency_overrides rather than passing verify_id_token
    directly — FastAPI won't inject a non-default-typed callable parameter
    from the request itself, so verify_id_token is really just an internal
    override point for lower-level unit tests calling this function directly.

    authorization defaults to None (not FastAPI's Header(...) required-param
    validation) so a genuinely missing header reaches this code and gets the
    same 401 as a malformed one, instead of a generic 422 from the framework
    before our own logic ever runs."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        decoded = verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    uid = decoded.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Token missing uid")

    db = get_firestore_client()
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists or user_doc.to_dict().get("role") != "kitchen":
        raise HTTPException(status_code=403, detail="Kitchen role required")

    return uid
