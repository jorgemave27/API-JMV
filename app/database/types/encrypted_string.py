from __future__ import annotations

"""
Custom SQLAlchemy field type for encrypted strings.

Task 66:
- Usa app.security.encryption
- Compatible con envelope encryption + KMSProvider
- Mantiene compatibilidad transparente para modelos
"""

from sqlalchemy.types import String, TypeDecorator

from app.security.encryption import decrypt, encrypt


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy encrypted string field.

    Cifra automáticamente al guardar y descifra al leer.
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

        return decrypt(value)