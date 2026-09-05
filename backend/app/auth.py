"""JWT auth + password hashing."""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db

bearer = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
ACCESS_TOKEN_HOURS = 24 * 30  # 30 days


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return salt + ":" + h.hex()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split(":")
        return hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100000).hex() == h
    except Exception:
        return False


def create_token(user_id: int, email: str) -> str:
    exp = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "exp": exp},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """Returns user or None (soft auth — anon allowed for free tier)."""
    if not creds:
        return None
    try:
        payload = jwt.decode(creds.credentials, settings.SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None
    return db.query(models.User).filter(models.User.id == uid).first()


def require_user(
    user: Optional[models.User] = Depends(get_current_user),
) -> models.User:
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Zaloguj się")
    return user


def require_admin(
    user: models.User = Depends(require_user),
) -> models.User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Brak uprawnień admina")
    return user
