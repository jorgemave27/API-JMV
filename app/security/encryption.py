from __future__ import annotations

"""
Encryption utilities for sensitive data.

Task 66:
- Integración con KMSProvider
- Envelope encryption
- Compatibilidad con el TypeDecorator existente
"""

from sqlalchemy.types import TEXT, TypeDecorator

from app.security.kms import decrypt_with_envelope, encrypt_with_envelope


def encrypt(plaintext: str | None) -> str | None:
    """
    Cifra texto usando envelope encryption.
    """
    if plaintext is None:
        return None

    return encrypt_with_envelope(plaintext)


def decrypt(ciphertext: str | None) -> str | None:
    """
    Descifra texto generado por encrypt().
    """
    if ciphertext is None:
        return None

    return decrypt_with_envelope(ciphertext)


class EncryptedString(TypeDecorator):
    """
    TypeDecorator para cifrado transparente.
    """

    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        return encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        return decrypt(value)
