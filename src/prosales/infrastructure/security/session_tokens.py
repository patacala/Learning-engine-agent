"""Signed, expiring session tokens for the ProSales UI login cookie.

A minimal HMAC-signed token (payload.signature, both base64url) instead of a
JWT library — the project has no JWT dependency and the payload is a single
expiry timestamp, so stdlib hmac/hashlib (already used in api_keys.py and
dependencies.py) is enough.
"""

import base64
import hashlib
import hmac
import json
import time

DEFAULT_TTL_SECONDS = 12 * 3600


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(body: str, secret: str) -> str:
    return _b64encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())


def create_session_token(secret: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """Issue a token that verify_session_token will accept until it expires."""
    payload = {"exp": int(time.time()) + ttl_seconds}
    body = _b64encode(json.dumps(payload).encode())
    return f"{body}.{_sign(body, secret)}"


def verify_session_token(token: str | None, secret: str) -> bool:
    """True iff ``token`` was signed with ``secret`` and hasn't expired."""
    if not token or not secret:
        return False
    body, _, signature = token.partition(".")
    if not signature:
        return False
    if not hmac.compare_digest(signature, _sign(body, secret)):
        return False
    try:
        payload = json.loads(_b64decode(body))
    except (ValueError, UnicodeDecodeError):
        return False
    return isinstance(payload.get("exp"), int) and payload["exp"] > time.time()
