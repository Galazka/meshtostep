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

def send_share_link(to: str, token: str, sender_email: str = "", job_title: str = "", job_uuid: str = ""):
    url = f"{settings.APP_URL}/s/{token}"
    preview_url = f"{settings.APP_URL}/api/preview/{job_uuid or token}"
    title = job_title or "Model 3D"
    send_mail(to, f"{sender_email or 'Ktoś'} udostępnił Ci model: {title}",
              f"""<div style="font-family:system-ui,sans-serif;max-width:500px;margin:0 auto;padding:24px">
<h2 style="color:#1a56db">🔗 Udostępniono Ci model 3D</h2>
<p><strong>{title}</strong></p>
<p><img src="{preview_url}" style="width:100%;border-radius:8px;border:1px solid #e2e8f0" alt="Podgląd"></p>
<p><a href="{url}" style="display:inline-block;padding:12px 24px;background:#1a56db;color:#fff;border-radius:8px;font-weight:600;text-decoration:none">Zobacz model 3D</a></p>
<p style="color:#94a3b8;font-size:12px">Powered by <a href="{settings.APP_URL}">3dfile.link</a></p>
</div>""")

