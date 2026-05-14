"""Symmetric encryption for user API keys.

Uses Fernet (AES-128-CBC + HMAC) with a key derived from the application
``SECRET_KEY`` via SHA-256.  Keys are stored as URL-safe base64 strings in the
database and decrypted on-demand when an agent needs to make an LLM call.
"""

from __future__ import annotations

import base64
from hashlib import sha256

from cryptography.fernet import Fernet

from aloha.config import settings

# Module-level singleton; safe because the app runs in a single process with an
# async event loop — no concurrent threads mutate this reference.  The Fernet
# instance is derived from the immutable SECRET_KEY and is reused for all
# encrypt/decrypt calls.
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Return a lazily-initialised Fernet instance."""
    global _fernet
    if _fernet is None:
        key = base64.urlsafe_b64encode(sha256(settings.secret_key.encode()).digest())
        _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt *plaintext* and return a URL-safe base64 ciphertext string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a ciphertext string produced by :func:`encrypt`."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
