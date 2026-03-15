"""
Custom SQLAlchemy field type for encrypted strings.

Automatically encrypts before saving
Automatically decrypts after reading
"""

from __future__ import annotations

from sqlalchemy.types import TypeDecorator, String

from app.security.encryption import encrypt, decrypt


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy encrypted string field.

    Transparent encryption layer.
    """

    impl = String

    cache_ok = True

    def process_bind_param(self, value, dialect):
        """
        Called when saving to DB.
        """

        if value is None:
            return None

        return encrypt(value)

    def process_result_value(self, value, dialect):
        """
        Called when loading from DB.
        """

        if value is None:
            return None

        try:
            return decrypt(value)
        except Exception:
            return value