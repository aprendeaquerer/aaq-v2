"""Email service - verification codes and PDF report delivery."""

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Optional

from app.config import settings


async def send_verification_email(to_email: str, code: str, language: str = "es") -> bool:
    """Send a verification code email."""
    subjects = {
        "es": "Tu codigo de verificacion - Aprende a Querer",
        "en": "Your verification code - Learn to Love",
        "ru": "Ваш код подтверждения - Learn to Love",
    }
    bodies = {
        "es": f"Tu codigo de verificacion es: {code}\n\nEste codigo expira en 15 minutos.",
        "en": f"Your verification code is: {code}\n\nThis code expires in 15 minutes.",
        "ru": f"Ваш код подтверждения: {code}\n\nЭтот код истекает через 15 минут.",
    }

    subject = subjects.get(language, subjects["es"])
    body = bodies.get(language, bodies["es"])

    return await _send_email(to_email, subject, body)


async def send_pdf_report(to_email: str, pdf_bytes: bytes, language: str = "es") -> bool:
    """Send the attachment style PDF report via email."""
    subjects = {
        "es": "Tu reporte de estilo de apego - Aprende a Querer",
        "en": "Your attachment style report - Learn to Love",
        "ru": "Ваш отчет о стиле привязанности",
    }

    msg = MIMEMultipart()
    msg["From"] = f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subjects.get(language, subjects["es"])

    body = MIMEText("Adjunto encontraras tu reporte personalizado de estilo de apego.", "plain")
    msg.attach(body)

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename="reporte_apego.pdf")
    msg.attach(attachment)

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_SERVER,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=True,
        )
        return True
    except Exception:
        return False


async def _send_email(to_email: str, subject: str, body: str) -> bool:
    """Send a plain text email."""
    if not settings.SMTP_USERNAME:
        return False

    msg = MIMEText(body)
    msg["From"] = f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_SERVER,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=True,
        )
        return True
    except Exception:
        return False
