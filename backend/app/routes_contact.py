"""Kontakt — formularz zapytań trafiający na mail Toma (tomekgalazka@gmail.com).
GET /api/contact-info  — dane kontaktowe (adres odbioru, email) do renderu
POST /api/contact      — wyślij zapytanie (name, email, subject, message) → mail
"""
from fastapi import APIRouter, Depends, HTTPException
import os, uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from .config import settings
from .database import get_db
from .mail import send_mail

router = APIRouter()

CONTACT_EMAIL = "tomekgalazka@gmail.com"
PICKUP_ADDRESS = "Gdańsk Osowa, 80-299, ul. Międzygwiezdna 31/2"
MAX_FILES = 8
MAX_FILE_MB = 10
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".stl", ".step", ".stp", ".svg", ".txt", ".zip"}


@router.get("/api/contact-info")
def contact_info():
    return {"ok": True,
            "email": CONTACT_EMAIL,
            "phone": "+48 790 824 762",
            "pickup_address": PICKUP_ADDRESS,
            "city": "Gdańsk Osowa",
            "postal": "80-299",
            "street": "ul. Międzygwiezdna 31/2",
            "pickup_note": "Odbiór osobisty po wcześniejszym umówieniu — drukujesz i odbierasz bez kosztów wysyłki."}


def _sign(name: str) -> str:
    """Krótki podpis HMAC dla linku pobierania załącznika (24h)."""
    import hmac, hashlib, time
    exp = int(time.time()) + 86400
    msg = f"{name}:{exp}".encode()
    sig = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:16]
    return f"{exp}-{sig}"


def _contact_link(name: str) -> str:
    return f"https://3dfile.link/api/contact-files/{_sign(name)}/{name}"


@router.get("/api/contact-files/{sig}/{name}")
def contact_file_download(sig: str, name: str):
    """Pobranie załącznika po podpisanym linku (z maila) — bez logowania, 24h."""
    import hmac, hashlib, time
    from fastapi.responses import FileResponse
    from pathlib import Path
    safe = name.replace("..", "").replace("/", "").replace("\\", "")
    if not safe or safe != name:
        raise HTTPException(400, "Zła nazwa")
    try:
        exp_s, sig_got = sig.split("-", 1)
        exp = int(exp_s)
    except Exception:
        raise HTTPException(400, "Zły link")
    if exp < int(time.time()):
        raise HTTPException(410, "Link wygasł (24h) — pobierz plik z panelu admina → Zgłoszenia")
    msg = f"{safe}:{exp}".encode()
    sig_ok = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig_ok, sig_got):
        raise HTTPException(403, "Nieprawidłowy podpis")
    path = Path(settings.DATA_DIR) / "contact" / safe
    if not path.is_file():
        raise HTTPException(404, "Plik usunięty z serwera — pobierz z panelu admina → Zgłoszenia")
    return FileResponse(str(path), filename=safe)


def _save_attachments(files) -> list:
    """Save uploads to DATA_DIR/contact/, return list of (original_name, path)."""
    if not files:
        return []
    out_dir = os.path.join(settings.DATA_DIR, "contact")
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    for f in files[:MAX_FILES]:
        if not f or not f.filename:
            continue
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(400, detail=f"Niedozwolony typ pliku: {f.filename} (dozwolone: zdjęcia, PDF, STL/STEP, SVG, TXT, ZIP)")
        data = f.file.read()
        if len(data) > MAX_FILE_MB * 1024 * 1024:
            raise HTTPException(400, detail=f"Plik {f.filename} za duży (max {MAX_FILE_MB} MB)")
        safe = f"{uuid.uuid4().hex[:8]}_{os.path.basename(f.filename).replace(' ', '_')}"[:120]
        path = os.path.join(out_dir, safe)
        with open(path, "wb") as w:
            w.write(data)
        saved.append((f.filename, path))
    return saved


@router.post("/api/contact")
def contact_submit(
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(None),
    message: str = Form(...),
    files: list[UploadFile] = File(None),
    db=Depends(get_db),
):
    if not name.strip() or not message.strip():
        raise HTTPException(400, detail="Podaj imię i treść wiadomości")
    if "@" not in (email or ""):
        raise HTTPException(400, detail="Podaj poprawny email")
    saved = _save_attachments(files)
    att_html = ""
    if saved:
        items = "".join(f"<li>{_h(n)} ({os.path.getsize(p)//1024} KB)</li>" for n, p in saved)
        links = "".join(
            f"<li><a href='{_contact_link(os.path.basename(p))}'>{_h(n)}</a> ({os.path.getsize(p)//1024} KB)</li>"
            for n, p in saved
        )
        att_html = f"<p><b>Załączniki ({len(saved)}) — kliknij, żeby podejrzeć/pobrać:</b></p><ul>{links}</ul><p style='color:#64748b;font-size:12px'>Linki ważne 24 h. Pliki trwale: panel admina → Zgłoszenia.</p>"
    body = (
        "<h2>Nowe zapytanie ze strony 3dfile.link</h2>"
        f"<p><b>Imię:</b> {_h(name)}</p>"
        f"<p><b>Email:</b> {_h(email)}</p>"
        f"<p><b>Temat:</b> {_h(subject or 'brak')}</p>"
        f"<p><b>Wiadomość:</b></p><blockquote style='background:#f1f5f9;padding:12px 16px;border-left:4px solid #0ea5e9'>{_h(message)}</blockquote>"
        + att_html +
        "<hr><p style='color:#64748b;font-size:12px'>Wysłano automatycznie z formularza kontaktowego 3dfile.link</p>"
    )
    ok = send_mail(CONTACT_EMAIL, f"[3dfile.kontakt] {_h(subject or name)}", body)
    if not ok:
        raise HTTPException(502, detail="Nie udało się wysłać — spróbuj później lub napisz na " + CONTACT_EMAIL)
    return {"ok": True, "to": CONTACT_EMAIL, "attachments": len(saved)}


def _h(x: str) -> str:
    return (x or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")