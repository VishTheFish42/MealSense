"""
Firestore access for the FastAPI backend. This is the first time this
backend has talked to Firestore at all — previously only the mobile app
(via the JS SDK) did.

Uses google.cloud.firestore.Client directly rather than
firebase_admin.firestore.client(), since the latter's credential loading
goes through google.auth.default() even when FIRESTORE_EMULATOR_HOST is
set, which fails with no GCP environment configured. Anonymous credentials
against the emulator; in real (non-emulator) environments, an explicit
service account key file if GOOGLE_APPLICATION_CREDENTIALS points at one,
otherwise Application Default Credentials.

The ADC path (added for tasks.md Phase 7's Cloud Run deployment) matters
because Cloud Run — and every other GCP compute product — provides
credentials automatically via its metadata server, with no key file to
download or manage at all. Before this existed, get_firestore_client()
always required an explicit key file outside the emulator, which would
have made the app silently lose all Firestore access the moment it ran
on Cloud Run — this is the fix for that, not just an alternative path.

The bare-ADC branch is gated on K_SERVICE (tasks.md Phase 7.3), a env
var Cloud Run — and only Cloud Run — automatically injects into every
container instance (see
https://cloud.google.com/run/docs/container-contract#env-vars). Without
this gate, `google.auth.default()` also happily succeeds on any
developer machine that has ever run `gcloud auth application-default
login` for unrelated reasons (e.g. deploying) — confirmed hands-on
while building this: local `uvicorn main:app --reload` with no emulator
running silently connected to and read real *production* Firestore,
using the developer's own gcloud credentials, with zero warning. The
gate makes that the same clean, catchable FirestoreNotConfiguredError
it always was pre-Phase-7 on any machine that isn't actually Cloud Run,
regardless of what credentials happen to be sitting in that machine's
gcloud config.
"""
from __future__ import annotations
import os

import google.auth
from google.auth.credentials import AnonymousCredentials
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import firestore
from google.oauth2 import service_account

class FirestoreNotConfiguredError(Exception):
    """None of FIRESTORE_EMULATOR_HOST, GOOGLE_APPLICATION_CREDENTIALS, or
    Application Default Credentials is available. Callers that have a
    sensible offline fallback (menu_store's static sample menu) should
    catch this specifically, not Firestore errors in general — a real
    connection or permissions failure should still surface, not be
    silently swallowed into "just serve stale sample data.\""""


_client: firestore.Client | None = None

# Set once ADC lookup has failed, so a "not configured" local dev/test
# environment pays the slow cost of google.auth.default() timing out
# against GCP's metadata server exactly once per process, not once per
# call. Without this, a suite that exercises the not-configured fallback
# across dozens of calls (every test that hits it before a
# reset_firestore_client()) goes from ~2s to ~25s — the timeout itself is
# a few seconds, and it was being paid over and over.
_adc_unavailable: bool = False

_NOT_CONFIGURED_MESSAGE = (
    "No Firestore credentials available: FIRESTORE_EMULATOR_HOST and "
    "GOOGLE_APPLICATION_CREDENTIALS are both unset, and bare Application "
    "Default Credentials are only trusted when actually running on Cloud "
    "Run (K_SERVICE set). Start the Firestore emulator for ordinary local "
    "dev, or set GOOGLE_APPLICATION_CREDENTIALS explicitly to point "
    "local dev at real Firestore on purpose."
)


def get_firestore_client() -> firestore.Client:
    global _client, _adc_unavailable
    if _client is not None:
        return _client

    project_id = os.environ.get("FIREBASE_PROJECT_ID", "mealsense-cb5ab")

    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        _client = firestore.Client(project=project_id, credentials=AnonymousCredentials())
    elif os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        creds = service_account.Credentials.from_service_account_file(
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        )
        _client = firestore.Client(project=project_id, credentials=creds)
    elif os.environ.get("K_SERVICE"):
        # Application Default Credentials: what Cloud Run provides
        # automatically, no key file needed. Gated on K_SERVICE (a
        # Cloud-Run-injected env var, never present on a developer
        # machine) so this branch is only ever reached when actually
        # running on Cloud Run — see the module docstring for why:
        # bare google.auth.default() also succeeds on any machine with
        # real gcloud ADC credentials configured for unrelated reasons,
        # which would otherwise silently point local dev at production.
        if _adc_unavailable:
            raise FirestoreNotConfiguredError(_NOT_CONFIGURED_MESSAGE)
        try:
            creds, _ = google.auth.default()
        except DefaultCredentialsError:
            _adc_unavailable = True
            raise FirestoreNotConfiguredError(_NOT_CONFIGURED_MESSAGE)
        _client = firestore.Client(project=project_id, credentials=creds)
    else:
        raise FirestoreNotConfiguredError(_NOT_CONFIGURED_MESSAGE)

    return _client


def reset_firestore_client() -> None:
    """Test-only: force the next get_firestore_client() call to reconnect,
    e.g. after changing FIRESTORE_EMULATOR_HOST between test runs.

    Deliberately does NOT clear _adc_unavailable: whether Application
    Default Credentials work at all is a fact about the machine/network
    (can it reach GCP's metadata server, is there a gcloud ADC file on
    disk), not something that changes per-test the way the emulator env
    var does. Every emulator-gated test file's fixture calls this on
    teardown — if it also cleared _adc_unavailable, every one of those
    resets would re-arm the next non-emulator test to pay the slow ADC
    probe again. Measured on a machine with no ADC configured at all:
    ~25s before this caching existed (every not-configured call retried
    the probe), ~12s once _adc_unavailable is cached but still cleared on
    reset, ~12s even after excluding it from reset too — because
    google.auth.default()'s own metadata-server timeout is itself ~6-12s
    on a single call here, and that one-time cost is unavoidable the
    first time it's genuinely needed. The fix here caps it at paying that
    once per process instead of dozens of times; it doesn't make the
    underlying probe itself fast. A real GCP environment (Cloud Run) or a
    local `gcloud auth application-default login` both make this whole
    branch resolve near-instantly instead of timing out at all."""
    global _client
    _client = None
