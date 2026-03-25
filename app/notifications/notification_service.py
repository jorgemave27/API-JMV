"""
NOTIFICATION SERVICE

- NO crea su propia DB (inyección externa)
- Compatible con Celery, FastAPI y tests
"""

import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from app.notifications.providers.email_provider import EmailProvider
from app.notifications.providers.sms_provider import SMSProvider


# ==============================
# JINJA CONFIG
# ==============================
TEMPLATES_PATH = os.path.join(
    os.path.dirname(__file__), "templates"
)

env = Environment(loader=FileSystemLoader(TEMPLATES_PATH))


class NotificationService:
    def __init__(self, db):
        """
        Inicializa providers

        Args:
            db: sesión SQLAlchemy (inyectada)
        """
        self.email_provider = EmailProvider()
        self.sms_provider = SMSProvider()
        self.db = db  # 👈 INYECTADA (CORRECTO)

    # ==============================
    # TEMPLATE
    # ==============================
    def _render_template(self, template_name: str, context: dict) -> str:
        template = env.get_template(template_name)
        return template.render(**context)

    # ==============================
    # EMAIL
    # ==============================
    def send_email(self, to: str, template: str, context: dict):
        html = self._render_template(template, context)

        return self.email_provider.send(
            to_email=to,
            subject=context.get("subject", "Notificación"),
            html_content=html,
        )

    # ==============================
    # SMS
    # ==============================
    def send_sms(self, phone: str, message: str):
        return self.sms_provider.send(phone, message)

    # ==============================
    # MAIN
    # ==============================
    def send(self, destinatario: str, tipo: str, canal: str, context: dict):
        """
        Orquestador principal
        """
        try:
            if canal == "email":
                result = self.send_email(
                    destinatario,
                    f"{tipo}.html",
                    context,
                )

            elif canal == "sms":
                result = self.send_sms(
                    destinatario,
                    context.get("message", "")
                )

            else:
                raise ValueError("Canal no soportado")

            # guardar éxito
            self._save(
                destinatario,
                canal,
                tipo,
                "enviado",
                1,
                None,
            )

            return result

        except Exception as e:
            # guardar error
            self._save(
                destinatario,
                canal,
                tipo,
                "error",
                1,
                str(e),
            )
            raise

    # ==============================
    # DB SAVE
    # ==============================
    def _save(
        self,
        destinatario,
        canal,
        tipo,
        estado,
        intentos,
        error_mensaje,
    ):
        """
        Persiste notificación en DB
        """
        from app.models.notification import NotificacionEnviada

        notif = NotificacionEnviada(
            destinatario=destinatario,
            canal=canal,
            tipo=tipo,
            estado=estado,
            intentos=intentos,
            error_mensaje=error_mensaje,
            enviado_en=datetime.utcnow(),
        )

        self.db.add(notif)
        self.db.commit()