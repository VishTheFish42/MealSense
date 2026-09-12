"""
Firestore access for the FastAPI backend. This is the first time this
backend has talked to Firestore at all — previously only the mobile app
(via the JS SDK) did.

Uses google.cloud.firestore.Client directly rather than
firebase_admin.firestore.client(), since the latter's credential loading
goes through google.auth.default() even when FIRESTORE_EMULATOR_HOST is
set, which fails with no GCP environment configured. Anonymous credentials
against the emulator, a real service account file in production.
"""
from __future__ import annotations
import os
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore
from google.oauth2 import service_account

class FirestoreNotConfiguredError(Exception):
    """Neither FIRESTORE_EMULATOR_HOST nor GOOGLE_APPLICATION_CREDENTIALS is
    set. Callers that have a sensible offline fallback (menu_store's static
    sample menu) should catch this specifically, not Firestore errors in
    general — a real connection or permissions failure should still surface,
    not be silently swallowed into "just serve stale sample data.\""""


_client: firestore.Client | None = None


def get_firestore_client() -> firestore.Client:
    global _client
    if _client is not None:
        return _client

    project_id = os.environ.get("FIREBASE_PROJECT_ID", "mealsense-cb5ab")

    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        _client = firestore.Client(project=project_id, credentials=AnonymousCredentials())
    else:
        key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not key_path:
            raise FirestoreNotConfiguredError(
                "GOOGLE_APPLICATION_CREDENTIALS is not set. Either point it at a "
                "Firebase service account key file, or set FIRESTORE_EMULATOR_HOST "
                "to run against the local emulator instead."
            )
        creds = service_account.Credentials.from_service_account_file(key_path)
        _client = firestore.Client(project=project_id, credentials=creds)

    return _client


def reset_firestore_client() -> None:
    """Test-only: force the next get_firestore_client() call to reconnect,
    e.g. after changing FIRESTORE_EMULATOR_HOST between test runs."""
    global _client
    _client = None
