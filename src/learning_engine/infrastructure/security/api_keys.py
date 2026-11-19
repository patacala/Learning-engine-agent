import hashlib
import secrets


def generate_api_key(slug: str) -> str:
    """Generate a tenant API key for CRM requests."""
    return f"sk-{slug}-{secrets.token_hex(12)}"


def hash_api_key(api_key: str) -> str:
    """One-way hash for storing API keys at rest."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def api_key_prefix(api_key: str) -> str:
    return api_key[:8]
