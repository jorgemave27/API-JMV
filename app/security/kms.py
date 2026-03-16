from __future__ import annotations

import base64
import json
import os
from abc import ABC, abstractmethod

from cryptography.fernet import Fernet

try:
    import boto3
except Exception:
    boto3 = None


class KMSProvider(ABC):
    @abstractmethod
    def generate_data_key(self) -> dict[str, bytes]:
        pass

    @abstractmethod
    def decrypt_data_key(self, encrypted_key: bytes) -> bytes:
        pass


class LocalKMSProvider(KMSProvider):
    """
    Provider local para desarrollo.
    Protege la DEK con una master key local.
    """

    def __init__(self) -> None:
        key = os.getenv("LOCAL_KMS_MASTER_KEY")

        if not key:
            raise RuntimeError("LOCAL_KMS_MASTER_KEY no configurada")

        if isinstance(key, str):
            key = key.encode()

        self.master = Fernet(key)

    def generate_data_key(self) -> dict[str, bytes]:
        plaintext_data_key = Fernet.generate_key()
        encrypted_data_key = self.master.encrypt(plaintext_data_key)

        return {
            "plaintext": plaintext_data_key,
            "ciphertext": encrypted_data_key,
        }

    def decrypt_data_key(self, encrypted_key: bytes) -> bytes:
        return self.master.decrypt(encrypted_key)


class AWSKMSProvider(KMSProvider):
    """
    Provider real con AWS KMS.
    Usa GenerateDataKey y Decrypt.
    """

    def __init__(self) -> None:
        if boto3 is None:
            raise RuntimeError("boto3 no está instalado")

        key_id = os.getenv("AWS_KMS_KEY_ID")
        region = os.getenv("AWS_REGION")

        if not key_id:
            raise RuntimeError("AWS_KMS_KEY_ID no configurado")

        kwargs = {}
        if region:
            kwargs["region_name"] = region

        self.client = boto3.client("kms", **kwargs)
        self.key_id = key_id

    def generate_data_key(self) -> dict[str, bytes]:
        response = self.client.generate_data_key(
            KeyId=self.key_id,
            KeySpec="AES_256",
        )

        return {
            "plaintext": response["Plaintext"],
            "ciphertext": response["CiphertextBlob"],
        }

    def decrypt_data_key(self, encrypted_key: bytes) -> bytes:
        response = self.client.decrypt(
            CiphertextBlob=encrypted_key,
        )
        return response["Plaintext"]


def get_kms_provider() -> KMSProvider:
    provider = os.getenv("KMS_PROVIDER", "local").strip().lower()

    if provider == "aws":
        return AWSKMSProvider()

    return LocalKMSProvider()


def _build_fernet_key_from_data_key(data_key: bytes) -> bytes:
    """
    Convierte la data key raw en key compatible con Fernet.
    """
    if len(data_key) < 32:
        raise RuntimeError("Data key inválida")

    return base64.urlsafe_b64encode(data_key[:32])


def encrypt_with_envelope(plaintext: str) -> str:
    """
    Envelope encryption:
    - KMS protege la DEK
    - La DEK cifra el dato
    """
    provider = get_kms_provider()

    generated = provider.generate_data_key()
    plaintext_data_key = generated["plaintext"]
    encrypted_data_key = generated["ciphertext"]

    fernet_key = _build_fernet_key_from_data_key(plaintext_data_key)
    cipher = Fernet(fernet_key)

    encrypted_payload = cipher.encrypt(plaintext.encode()).decode()

    payload = {
        "v": 1,
        "alg": "envelope-fernet",
        "dek": base64.b64encode(encrypted_data_key).decode(),
        "ct": encrypted_payload,
    }

    return base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()


def decrypt_with_envelope(ciphertext: str) -> str:
    """
    Descifra payload envelope.
    """
    provider = get_kms_provider()

    decoded = json.loads(base64.b64decode(ciphertext).decode())

    encrypted_data_key = base64.b64decode(decoded["dek"])
    encrypted_payload = decoded["ct"]

    plaintext_data_key = provider.decrypt_data_key(encrypted_data_key)
    fernet_key = _build_fernet_key_from_data_key(plaintext_data_key)

    cipher = Fernet(fernet_key)
    plaintext = cipher.decrypt(encrypted_payload.encode()).decode()

    return plaintext