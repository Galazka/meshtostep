"""Auth routes: register, login, me."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from . import models
from .auth import hash_password, verify_password, create_token, require_user
from .config import settings
from .database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterReq(BaseModel):
    email: EmailStr
    password: str


class LoginReq(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
def register(body: RegisterReq, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(400, "Email już zarejestrowany")
    user = models.User(
        email=body.email,
        password_hash=hash_password(body.password),
        credits=settings.FREE_CREDITS,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.id, user.email)
    return {"token": token, "user": {"id": user.id, "email": user.email, "credits": user.credits}}


@router.post("/login")
def login(body: LoginReq, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Błędny email lub hasło")
    from datetime import datetime
    user.last_login = datetime.utcnow()
    db.commit()
    token = create_token(user.id, user.email)
    return {"token": token, "user": {"id": user.id, "email": user.email, "credits": user.credits, "is_admin": user.is_admin}}


@router.get("/me")
def me(user: models.User = Depends(require_user)):
    return {"id": user.id, "email": user.email, "credits": user.credits, "is_admin": user.is_admin, "created_at": str(user.created_at)}
