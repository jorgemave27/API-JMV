"""
Encryption utilities for sensitive data.

AES-256-GCM encryption used for field level encryption in database.
Compatible with Vault / ENV configuration used in API-JMV.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def _load_key() -> bytes:
    """
    Load encryption key.

    Priority:
    1. Vault secret (if loaded into settings)
    2. ENV variable ENCRYPTION_KEY

    Must be base64 encoded 32 bytes.
    """

    key = None

    # Si Vault cargó la key dentro de settings
    if hasattr(settings, "ENCRYPTION_KEY"):
        key = settings.ENCRYPTION_KEY

    # fallback ENV
    if not key:
        key = os.getenv("ENCRYPTION_KEY")

    if not key:
        raise RuntimeError("ENCRYPTION_KEY not configured")

    key_bytes = base64.b64decode(key)

    if len(key_bytes) != 32:
        raise RuntimeError("ENCRYPTION_KEY must be 32 bytes")

    return key_bytes


def encrypt(plaintext: str) -> str:
    """
    Encrypt plaintext using AES-256-GCM.
    """

    if plaintext is None:
        return None

    key = _load_key()

    aesgcm = AESGCM(key)

    nonce = os.urandom(12)

    ciphertext = aesgcm.encrypt(
        nonce,
        plaintext.encode(),
        None
    )

    encrypted = nonce + ciphertext

    return base64.b64encode(encrypted).decode()


def decrypt(ciphertext: str) -> str:
    """
    Decrypt ciphertext produced by encrypt().
    """

    if ciphertext is None:
        return None

    key = _load_key()

    aesgcm = AESGCM(key)

    raw = base64.b64decode(ciphertext)

    nonce = raw[:12]
    data = raw[12:]

    decrypted = aesgcm.decrypt(
        nonce,
        data,
        None
    )

    return decrypted.decode()