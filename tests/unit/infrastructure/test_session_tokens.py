"""Signed session tokens: round-trip, expiry, tampering, and wrong-secret
rejection — this is what guards the UI's login cookie."""

from learning_engine.infrastructure.security.session_tokens import (
    create_session_token,
    verify_session_token,
)


def test_valid_token_verifies():
    token = create_session_token("s3cret", ttl_seconds=3600)
    assert verify_session_token(token, "s3cret") is True


def test_expired_token_rejected():
    token = create_session_token("s3cret", ttl_seconds=-1)
    assert verify_session_token(token, "s3cret") is False


def test_wrong_secret_rejected():
    token = create_session_token("s3cret", ttl_seconds=3600)
    assert verify_session_token(token, "other-secret") is False


def test_tampered_payload_rejected():
    token = create_session_token("s3cret", ttl_seconds=3600)
    body, _, signature = token.partition(".")
    # Flip the signature so it no longer matches a re-signed (even identical) body.
    tampered = f"{body}x.{signature}"
    assert verify_session_token(tampered, "s3cret") is False


def test_malformed_token_rejected():
    assert verify_session_token("not-a-real-token", "s3cret") is False
    assert verify_session_token("", "s3cret") is False
    assert verify_session_token(None, "s3cret") is False


def test_empty_secret_rejected():
    token = create_session_token("", ttl_seconds=3600)
    assert verify_session_token(token, "") is False


def test_default_ttl_is_valid():
    token = create_session_token("s3cret")
    assert verify_session_token(token, "s3cret") is True
