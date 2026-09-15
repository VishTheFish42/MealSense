"""
Tests services/firestore_client.py's credential-resolution logic directly,
mocking google.auth.default() rather than relying on the real (slow —
several seconds on a machine with no ADC configured) network timeout.
This is deliberately separate from the other Firestore-backed test files:
those all set FIRESTORE_EMULATOR_HOST and never touch this module's ADC
branch at all.

Every test resets module state via reset_firestore_client() so mocked
clients/credentials never leak into other test files that run in the
same pytest process afterward.
"""
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import DefaultCredentialsError

from services import firestore_client
from services.firestore_client import FirestoreNotConfiguredError, get_firestore_client


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    firestore_client.reset_firestore_client()
    firestore_client._adc_unavailable = False
    yield
    firestore_client.reset_firestore_client()
    firestore_client._adc_unavailable = False


def test_raises_not_configured_when_adc_unavailable():
    with patch("google.auth.default", side_effect=DefaultCredentialsError("no creds")):
        with pytest.raises(FirestoreNotConfiguredError):
            get_firestore_client()


def test_adc_failure_is_cached_not_retried_every_call():
    """The actual bug this was written to catch: without caching, every
    call in a not-configured environment re-pays google.auth.default()'s
    own multi-second metadata-server timeout."""
    with patch("google.auth.default", side_effect=DefaultCredentialsError("no creds")) as mock_default:
        with pytest.raises(FirestoreNotConfiguredError):
            get_firestore_client()
        with pytest.raises(FirestoreNotConfiguredError):
            get_firestore_client()
        with pytest.raises(FirestoreNotConfiguredError):
            get_firestore_client()

    assert mock_default.call_count == 1


def test_reset_firestore_client_does_not_re_arm_the_adc_probe():
    """reset_firestore_client() clears the cached client (so a real config
    change, e.g. setting FIRESTORE_EMULATOR_HOST, takes effect) but must
    NOT clear the cached ADC-unavailable result — that's an environment
    fact, not per-test state, and re-probing on every reset is exactly
    the slowdown this caching exists to prevent."""
    with patch("google.auth.default", side_effect=DefaultCredentialsError("no creds")) as mock_default:
        with pytest.raises(FirestoreNotConfiguredError):
            get_firestore_client()

        firestore_client.reset_firestore_client()

        with pytest.raises(FirestoreNotConfiguredError):
            get_firestore_client()

    assert mock_default.call_count == 1


def test_uses_adc_when_available():
    fake_creds = MagicMock()
    fake_client = MagicMock()

    with patch("google.auth.default", return_value=(fake_creds, "some-project")):
        with patch("services.firestore_client.firestore.Client", return_value=fake_client) as mock_ctor:
            client = get_firestore_client()

    assert client is fake_client
    _, kwargs = mock_ctor.call_args
    assert kwargs["credentials"] is fake_creds


def test_explicit_credentials_file_takes_priority_over_adc(monkeypatch, tmp_path):
    key_file = tmp_path / "fake-key.json"
    key_file.write_text("{}")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key_file))

    fake_creds = MagicMock()
    fake_client = MagicMock()

    with patch("google.auth.default") as mock_adc:
        with patch(
            "services.firestore_client.service_account.Credentials.from_service_account_file",
            return_value=fake_creds,
        ):
            with patch("services.firestore_client.firestore.Client", return_value=fake_client):
                client = get_firestore_client()

    assert client is fake_client
    mock_adc.assert_not_called()  # explicit key file must win, never fall through to ADC
