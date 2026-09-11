"""SMTP mail helper — stdlib smtplib, no deps. — 3dfile.link"""
import smtplib
from email.mime.text import MIMEText
from .config import settings


def send_mail(to: str, subject: str, html_body: str) -> bool:
    """Send HTML email. Returns True on success, False if SMTP not configured."""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        print(f"[MAIL disabled] to={to} subject={subject}")
        return False
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
            s.starttls()
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
        print(f"[MAIL sent] to={to} subject={subject}")
        return True
    except Exception as e:
        print(f"[MAIL failed] to={to}: {e}")
        return False


def send_verification(to: str, token: str):
    url = f"{settings.APP_URL}/api/auth/verify/{token}"
    send_mail(to, "3dfile.link — potwierdź email",
              f"<p>Kliknij link aby potwierdzić email:</p><p><a href='{url}'>{url}</a></p>")


def send_reset(to: str, token: str):
    url = f"{settings.APP_URL}/api/auth/reset?token={token}"
    send_mail(to, "3dfile.link — reset hasła",
              f"<p>Kliknij link aby ustawić nowe hasło (ważny {settings.PASSWORD_RESET_HOURS}h):</p><p><a href='{url}'>{url}</a></p>")
