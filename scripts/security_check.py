import os


def check_env():
    """
    Verifica que la API esté en modo producción.
    """

    env = os.getenv("APP_ENV")

    if env != "production":
        print("WARNING: APP_ENV no está en production")
    else:
        print("OK: production mode")


def check_encryption():
    """
    Verifica que exista una clave de encriptación.
    """

    if os.getenv("ENCRYPTION_KEY"):
        print("OK: encryption key configurada")
    else:
        print("ERROR: falta ENCRYPTION_KEY")


if __name__ == "__main__":
    print("Running security audit...\n")

    check_env()

    check_encryption()

    print("\nAudit completed")
