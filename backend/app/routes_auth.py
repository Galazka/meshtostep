"""Auth routes: register, login, me, password reset, email verification."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from . import models
from .auth import hash_password, verify_password, create_token, get_current_user, require_user
from .config import settings
from .database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── Rate limiter (in-memory, per IP) ────────────────────────────────
_login_hits: dict[str, list[float]] = defaultdict(list)


def _rate_limit(ip: str):
    now = datetime.utcnow().timestamp()
    window = 60
    _login_hits[ip] = [t for t in _login_hits[ip] if now - t < window]
    if len(_login_hits[ip]) >= settings.RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "Za duzo prob. Poczekaj minute.")
    _login_hits[ip].append(now)


def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Password policy ──────────────────────────────────────────────────
_MIN_PWD = 8
_MAX_PWD = 128


def _validate_password(pw: str):
    errors = []
    if len(pw) < _MIN_PWD:
        errors.append(f"min {_MIN_PWD} znakow")
    if len(pw) > _MAX_PWD:
        errors.append(f"max {_MAX_PWD} znakow")
    if not re.search(r"[A-Z]", pw):
        errors.append("duza litera")
    if not re.search(r"[a-z]", pw):
        errors.append("mala litera")
    if not re.search(r"\d", pw):
        errors.append("cyfra")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", pw):
        errors.append("specjalny znak (!@#...)")
    if errors:
        raise HTTPException(422, "Haslo za slabe: " + ", ".join(errors))


# ── Requests ─────────────────────────────────────────────────────────
class RegisterReq(BaseModel):
    email: EmailStr
    password: str
    password_confirm: str
    terms_accepted: bool  # wymagane: regulamin
    privacy_accepted: bool  # wymagane: polityka prywatnosci
    marketing_consent: bool = False  # opcjonalne

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        _validate_password(v)
        return v


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class ResetReq(BaseModel):
    email: EmailStr


class ResetConfirmReq(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        _validate_password(v)
        return v


# ── Routes ───────────────────────────────────────────────────────────
@router.post("/register")
def register(body: RegisterReq, request: Request, db: Session = Depends(get_db)):
    _rate_limit(_get_ip(request))

    # Walidacja RODO
    if not body.terms_accepted:
        raise HTTPException(422, "Musisz zaakceptowac regulamin")
    if not body.privacy_accepted:
        raise HTTPException(422, "Musisz zaakceptowac polityke prywatnosci")
    if body.password != body.password_confirm:
        raise HTTPException(422, "Hasla sie nie zgadzaja")

    email_lower = body.email.lower().strip()
    if db.query(models.User).filter(models.User.email == email_lower).first():
        raise HTTPException(409, "Email juz zarejestrowany")

    now = datetime.utcnow()
    token = secrets.token_urlsafe(48)
    user = models.User(
        email=email_lower,
        password_hash=hash_password(body.password),
        credits=settings.FREE_CREDITS,
        verification_token=token,
        email_verified=not settings.EMAIL_VERIFICATION_REQUIRED,
        terms_accepted_at=now,
        privacy_accepted_at=now,
        marketing_consent=body.marketing_consent,
        registered_ip=_get_ip(request),
        register_user_agent=(request.headers.get("user-agent") or "")[:512],
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # TODO: send verification email via SMTP if settings.EMAIL_VERIFICATION_REQUIRED
    jwt_token = create_token(user.id, user.email)
    return {
        "token": jwt_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "credits": user.credits,
            "email_verified": user.email_verified,
        },
        "message": (
            "Konto utworzone"
            if not settings.EMAIL_VERIFICATION_REQUIRED
            else "Sprawdz email, kliknij link weryfikacyjny"
        ),
    }


@router.post("/login")
def login(body: LoginReq, request: Request, db: Session = Depends(get_db)):
    _rate_limit(_get_ip(request))

    email_lower = body.email.lower().strip()
    user = db.query(models.User).filter(models.User.email == email_lower).first()

    if not user:
        raise HTTPException(401, "Bledny email lub haslo")

    # Account lock check
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = (user.locked_until - datetime.utcnow()).seconds
        raise HTTPException(
            423, f"Konto zablokowane na {remaining // 60 + 1} min"
        )

    if not verify_password(body.password, user.password_hash):
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= 10:
            user.locked_until = datetime.utcnow() + timedelta(minutes=30)
            db.commit()
            raise HTTPException(423, "Konto zablokowane na 30 min za duzo blednych prob")
        db.commit()
        raise HTTPException(401, "Bledny email lub haslo")

    # Reset failed logins on success
    user.failed_logins = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    db.commit()

    jwt_token = create_token(user.id, user.email)
    return {
        "token": jwt_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "credits": user.credits,
            "is_admin": user.is_admin,
            "email_verified": user.email_verified,
        },
    }


@router.get("/me")
def me(user: models.User = Depends(require_user)):
    return {
        "id": user.id,
        "email": user.email,
        "credits": user.credits,
        "is_admin": user.is_admin,
        "email_verified": user.email_verified,
        "created_at": str(user.created_at),
    }


# ── Email verification ───────────────────────────────────────────────
@router.get("/verify/{token}", response_class=HTMLResponse)
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.verification_token == token).first()
    if not user:
        return HTMLResponse(
            "<!DOCTYPE html><html><body><h2>Link weryfikacyjny nieprawidlowy lub juz uzycio.</h2>"
            "<p><a href='/'>Powrot do MeshToStep</a></p></body></html>",
            status_code=400,
        )
    user.email_verified = True
    user.verification_token = None
    db.commit()
    return HTMLResponse(
        "<!DOCTYPE html><html><body><h2>Email zweryfikowany!</h2>"
        "<p><a href='/'>Powrot do MeshToStep</a></p></body></html>"
    )


# ── Password reset ───────────────────────────────────────────────────
@router.post("/forgot-password")
def forgot_password(body: ResetReq, request: Request, db: Session = Depends(get_db)):
    _rate_limit(_get_ip(request))
    email_lower = body.email.lower().strip()
    user = db.query(models.User).filter(models.User.email == email_lower).first()

    # Always return OK to prevent email enumeration
    if user:
        token = secrets.token_urlsafe(48)
        user.reset_token = token
        user.reset_expires = datetime.utcnow() + timedelta(hours=settings.PASSWORD_RESET_HOURS)
        db.commit()
        # TODO: send reset email via SMTP
        print(f"[PASSWORD RESET] {user.email} -> {settings.APP_URL}/reset?token={token}")

    return {"message": "Jesli email istnieje, otrzymasz link do resetu hasla"}


@router.post("/reset-password")
def reset_password(body: ResetConfirmReq, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.reset_token == body.token,
        models.User.reset_expires > datetime.utcnow(),
    ).first()
    if not user:
        raise HTTPException(400, "Token wygasl lub nieprawidlowy")

    user.password_hash = hash_password(body.password)
    user.reset_token = None
    user.reset_expires = None
    user.failed_logins = 0
    user.locked_until = None
    db.commit()
    return {"message": "Haslo zmienione. Zaloguj sie nowym haslem."}


@router.get("/reset", response_class=HTMLResponse)
def reset_page(token: str):
    """Simple reset password page served by backend."""
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reset hasla - MeshToStep</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f8fafc;color:#1e293b;display:flex;justify-content:center;padding:60px 20px}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:32px;max-width:400px;width:100%}}
h2{{font-size:20px;margin-bottom:16px}}
input{{width:100%;padding:10px 14px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;margin-bottom:12px}}
button{{width:100%;padding:10px;background:#1a56db;color:#fff;border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer}}
button:hover{{background:#1e40af}}
.msg{{padding:12px;border-radius:8px;font-size:13px;margin-bottom:12px}}
.ok{{background:#ecfdf5;color:#059669;border:1px solid #a7f3d0}}
.err{{background:#fef2f2;color:#dc2626;border:1px solid #fecaca}}
</style></head><body>
<div class="card" id="card">
  <h2>Nowe haslo</h2>
  <div class="msg err" id="msg" style="display:none"></div>
  <input type="password" id="pw1" placeholder="Nowe haslo (min 8, duza litera, cyfra, znak)">
  <input type="password" id="pw2" placeholder="Powtorz haslo">
  <button onclick="doReset()">Zmien haslo</button>
</div>
<script>
const token = new URLSearchParams(window.location.search).get('token');
if (!token) document.getElementById('card').innerHTML = '<h2>Brak tokenu</h2><p>Poprosw o reset ponownie.</p>';
async function doReset() {{
  const p1 = document.getElementById('pw1').value;
  const p2 = document.getElementById('pw2').value;
  const msg = document.getElementById('msg');
  if (p1 !== p2) {{ msg.textContent = 'Hasla sie nie zgadzaja'; msg.style.display='block'; return; }}
  try {{
    const r = await fetch('/api/auth/reset-password', {{
      method: 'POST', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{ token, password: p1 }})
    }});
    const d = await r.json();
    if (r.ok) {{ msg.className='msg ok'; msg.textContent=d.message; }}
    else {{ msg.className='msg err'; msg.textContent=d.detail||'Blad'; }}
    msg.style.display='block';
  }} catch(e) {{ msg.textContent='Blad sieci'; msg.style.display='block'; }}
}}
</script></body></html>""")
