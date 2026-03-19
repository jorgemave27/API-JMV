"""
Cliente para interactuar con HashiCorp Vault.

Responsabilidades:
- Conectarse a Vault
- Leer secretos
- Escribir secretos
- Ser usado por config.py
"""

import os
from typing import Optional

import hvac


class VaultClient:
    """
    Cliente centralizado de Vault.
    """

    def __init__(self) -> None:

        self.vault_addr: Optional[str] = os.getenv("VAULT_ADDR")
        self.vault_token: Optional[str] = os.getenv("VAULT_TOKEN")

        self.client: Optional[hvac.Client] = None

        if self.vault_addr:
            self.client = hvac.Client(
                url=self.vault_addr,
                token=self.vault_token,
                timeout=2,
            )

    def enabled(self) -> bool:
        """
        Indica si Vault está activo.
        """
        return self.client is not None

    def read_secret(self, path: str) -> dict:
        """
        Lee secretos desde KV store.

        Ejemplo path:
        secret/mi-api
        """

        if not self.client:
            raise RuntimeError("Vault no habilitado")

        response = self.client.secrets.kv.v2.read_secret_version(path=path.replace("secret/", ""))

        return response["data"]["data"]

    def write_secret(self, path: str, data: dict) -> None:
        """
        Guarda secretos en Vault.
        """

        if not self.client:
            raise RuntimeError("Vault no habilitado")

        self.client.secrets.kv.v2.create_or_update_secret(
            path=path.replace("secret/", ""),
            secret=data,
        )


vault_client = VaultClient()
