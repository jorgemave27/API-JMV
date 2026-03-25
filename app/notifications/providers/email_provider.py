"""
EMAIL PROVIDER (SENDGRID)

- Soporta modo DEV (simulado)
- Soporta modo PROD (SendGrid real)
"""

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.core.config import settings


class EmailProvider:
    def __init__(self):
        """
        Inicializa cliente SendGrid solo si hay API key real
        """
        if settings.SENDGRID_API_KEY != "dummy":
            self.client = SendGridAPIClient(settings.SENDGRID_API_KEY)
        else:
            self.client = None  # 👈 modo simulado

    def send(self, to_email: str, subject: str, html_content: str) -> int:
        """
        Envía email o lo simula en desarrollo

        Args:
            to_email: destinatario
            subject: asunto
            html_content: contenido HTML

        Returns:
            status_code (200 en modo simulado)
        """

        # =====================================================
        # 🔥 MODO DEV (SIN SENDGRID REAL)
        # =====================================================
        if settings.SENDGRID_API_KEY == "dummy":
            print(
                f"[EMAIL SIMULADO] → to={to_email} | subject={subject}"
            )
            return 200

        # =====================================================
        # 🚀 MODO REAL (SENDGRID)
        # =====================================================
        message = Mail(
            from_email=settings.EMAIL_FROM,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )

        response = self.client.send(message)

        return response.status_code