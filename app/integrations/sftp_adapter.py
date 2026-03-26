from __future__ import annotations

"""
SFTP ADAPTER

Este módulo encapsula la conexión y operaciones básicas sobre un servidor SFTP.
Se utiliza para integrar sistemas legacy que intercambian archivos vía SFTP.

Responsabilidades:
- Conectarse al servidor
- Listar archivos
- Descargar / subir archivos
- Eliminar / mover archivos
"""

import paramiko


class SFTPAdapter:
    def __init__(self, host: str, port: int, username: str, password: str):
        """
        Inicializa el adaptador SFTP con credenciales.

        Args:
            host: IP o dominio del servidor SFTP
            port: Puerto (normalmente 22)
            username: Usuario SFTP
            password: Password SFTP
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password

        self.transport = None
        self.sftp = None

    def connect(self):
        """
        Establece conexión con el servidor SFTP.
        """
        self.transport = paramiko.Transport((self.host, self.port))
        self.transport.connect(
            username=self.username,
            password=self.password
        )

        self.sftp = paramiko.SFTPClient.from_transport(self.transport)

    def close(self):
        """
        Cierra la conexión SFTP.
        """
        if self.sftp:
            self.sftp.close()

        if self.transport:
            self.transport.close()

    def list_files(self, remote_path: str):
        """
        Lista archivos en un directorio remoto.

        Args:
            remote_path: Ruta en el servidor SFTP

        Returns:
            Lista de nombres de archivo
        """
        return self.sftp.listdir(remote_path)

    def download_file(self, remote_path: str, local_path: str):
        """
        Descarga archivo del SFTP al filesystem local.

        Args:
            remote_path: Ruta remota
            local_path: Ruta local destino
        """
        self.sftp.get(remote_path, local_path)

    def upload_file(self, local_path: str, remote_path: str):
        """
        Sube archivo local al SFTP.

        Args:
            local_path: Ruta local
            remote_path: Ruta destino en SFTP
        """
        self.sftp.put(local_path, remote_path)

    def delete_file(self, remote_path: str):
        """
        Elimina archivo del SFTP.
        """
        self.sftp.remove(remote_path)

    def move_file(self, old_path: str, new_path: str):
        """
        Mueve/renombra archivo dentro del SFTP.

        Args:
            old_path: Ruta actual
            new_path: Nueva ruta
        """
        self.sftp.rename(old_path, new_path)