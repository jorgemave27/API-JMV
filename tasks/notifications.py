"""
TASK ASÍNCRONA DE NOTIFICACIONES

- Maneja reintentos
- Backoff exponencial
- Cada worker usa su propia sesión DB (CORRECTO)
"""

from celery import shared_task

from app.database.database import SessionLocal


@shared_task(bind=True, max_retries=3)
def send_notification_task(self, payload: dict):
    """
    Ejecuta envío de notificación de forma asíncrona

    Args:
        payload: {
            destinatario: str,
            tipo: str,
            canal: str,
            context: dict
        }
    """

    # ==============================
    # CREAR SESIÓN DB (POR WORKER)
    # ==============================
    db = SessionLocal()

    try:
        from app.notifications.notification_service import NotificationService

        #--INYECCIÓN CORRECTA
        service = NotificationService(db=db)

        service.send(
            destinatario=payload["destinatario"],
            tipo=payload["tipo"],
            canal=payload["canal"],
            context=payload["context"],
        )

    except Exception as exc:
        # ==============================
        # RETRY CON BACKOFF EXPONENCIAL
        # ==============================
        raise self.retry(
            exc=exc,
            countdown=2 ** self.request.retries  # 2, 4, 8...
        )

    finally:
        # ==============================
        # CERRAR SESIÓN (CRÍTICO)
        # ==============================
        db.close()