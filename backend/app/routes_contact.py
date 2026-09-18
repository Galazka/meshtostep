"""Kontakt — formularz zapytań trafiający na mail Toma (tomekgalazka@gmail.com).
GET /api/contact-info  — dane kontaktowe (adres odbioru, email) do renderu
POST /api/contact      — wyślij zapytanie (name, email, subject, message) → mail
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .database import get_db
from .mail import send_mail

router = APIRouter()

CONTACT_EMAIL = "tomekgalazka@gmail.com"
PICKUP_ADDRESS = "Gdańsk Osowa, 80-299, ul. Międzygwiezdna 31/2"


@router.get("/api/contact-info")
def contact_info():
    return {"ok": True,
            "email": CONTACT_EMAIL,
            "phone": "+48 000 000 000",
            "pickup_address": PICKUP_ADDRESS,
            "city": "Gdańsk Osowa",
            "postal": "80-299",
            "street": "ul. Międzygwiezdna 31/2",
            "pickup_note": "Odbiór osobisty po wcześniejszym umówieniu — drukujesz i odbierasz bez kosztów wysyłki."}


class ContactIn(BaseModel):
    name: str
    email: str
    subject: str = None
    message: str


@router.post("/api/contact")
def contact_submit(req: ContactIn, db=Depends(get_db)):
    if not req.name.strip() or not req.message.strip():
        raise HTTPException(400, detail="Podaj imię i treść wiadomości")
    if "@" not in req.email:
        raise HTTPException(400, detail="Podaj poprawny email")
    body = (
        "<h2>Nowe zapytanie ze strony 3dfile.link</h2>"
        f"<p><b>Imię:</b> {_h(req.name)}</p>"
        f"<p><b>Email:</b> {_h(req.email)}</p>"
        f"<p><b>Temat:</b> {_h(req.subject or 'brak')}</p>"
        f"<p><b>Wiadomość:</b></p><blockquote style='background:#f1f5f9;padding:12px 16px;border-left:4px solid #0ea5e9'>{_h(req.message)}</blockquote>"
        "<hr><p style='color:#64748b;font-size:12px'>Wysłano automatycznie z formularza kontaktowego 3dfile.link</p>"
    )
    ok = send_mail(CONTACT_EMAIL, f"[3dfile.kontakt] {_h(req.subject or req.name)}", body)
    if not ok:
        raise HTTPException(502, detail="Nie udało się wysłać — spróbuj później lub napisz na " + CONTACT_EMAIL)
    return {"ok": True, "to": CONTACT_EMAIL}


def _h(x: str) -> str:
    return (x or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")