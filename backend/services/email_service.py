"""Small SMTP adapter used for account notifications."""
import asyncio
import logging
import smtplib
from email.message import EmailMessage

from backend.config import settings

logger = logging.getLogger(__name__)


def _send_registration_email_sync(email: str, full_name: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        logger.info("Registration email skipped: SMTP is not configured.")
        return
    message = EmailMessage()
    message["Subject"] = "Chào mừng bạn đến với Job4U"
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = email
    message.set_content(
        f"Xin chào {full_name},\n\n"
        "Tài khoản Job4U của bạn đã được tạo thành công. "
        "Email này là tài khoản dùng để đăng nhập về sau.\n\n"
        "Trân trọng,\nĐội ngũ Job4U"
    )
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)


async def send_registration_email(email: str, full_name: str) -> bool:
    try:
        await asyncio.to_thread(_send_registration_email_sync, email, full_name)
        return bool(settings.SMTP_HOST and settings.SMTP_FROM_EMAIL)
    except Exception:
        logger.exception("Could not send registration email to %s", email)
        return False


def _send_application_feedback_email_sync(email: str, full_name: str, company_name: str, job_title: str, feedback: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        logger.info("Application feedback email skipped: SMTP is not configured.")
        return
    message = EmailMessage()
    message["Subject"] = f"Phản hồi hồ sơ ứng tuyển: {job_title}"
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = email
    message.set_content(
        f"Xin chào {full_name},\n\n"
        f"{company_name} đã gửi phản hồi về hồ sơ ứng tuyển vị trí “{job_title}”.\n\n"
        f"Nội dung phản hồi:\n{feedback}\n\n"
        "Bạn cũng có thể xem lại phản hồi trong tài khoản Job4U.\n\n"
        "Trân trọng,\nĐội ngũ Job4U"
    )
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)


async def send_application_feedback_email(email: str, full_name: str, company_name: str, job_title: str, feedback: str) -> bool:
    try:
        await asyncio.to_thread(_send_application_feedback_email_sync, email, full_name, company_name, job_title, feedback)
        return bool(settings.SMTP_HOST and settings.SMTP_FROM_EMAIL)
    except Exception:
        logger.exception("Could not send application feedback email to %s", email)
        return False
