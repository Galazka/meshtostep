"""Dynamic sitemap.xml + robots.txt serving for 3dfile.link."""
import html as _html
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from . import models
from .database import get_db

router = APIRouter()

DOMAIN = "https://3dfile.link"

# ── Filtry testowych smieci (nie indeksujemy naszych wlasnych testow) ──
import re as _re
_JUNK_USER_RE = _re.compile(r"^(uitest|e2e|demouser|testuser|test\d|demo\d|smtptest|admin\d)", _re.I)
_JUNK_TAGS = {"test", "demo", "asdf", "qwerty", "abc", "xxx", "tmp"}


def _junk_user(name) -> bool:
    if not name:
        return False
    return bool(_JUNK_USER_RE.match(str(name).strip()))


def _junk_slug(slug) -> bool:
    s = str(slug or "").strip().lower()
    if not s:
        return True
    return any(t in s for t in ("uitest", "-test-", "test-")) or s in ("test", "demo", "model")


def _fmt_date(dt) -> str:
    if not dt:
        return datetime.utcnow().strftime("%Y-%m-%d")
    return str(dt)[:10]


@router.get("/sitemap.xml", response_class=Response)
def sitemap(request: Request, db: Session = Depends(get_db)):
    urls = []
    # Homepage
    urls.append(f"  <url><loc>{DOMAIN}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>")
    # Static / print-shop + blog + articles
    STATIC_PAGES = {
        "/drukuje": 0.9, "/kontakt": 0.8, "/en/print": 0.8, "/blog.html": 0.9, "/en/order": 0.7, "/zamow": 0.8,
        "/blog/jaki-filament-wybrac-3d.html": 0.7, "/blog/jak-przygotowac-plik-do-druku-3d.html": 0.7,
        "/blog/druk-3d-na-zamowienie-ile-kosztuje.html": 0.7, "/blog/druk-wielokolorowy-jak-to-dziala.html": 0.6,
        "/blog/prototypowanie-3d-dla-firm.html": 0.6, "/blog/tolerancje-i-dokladnosc-druku-3d.html": 0.6,
        "/prywatnosc.html": 0.3, "/regulamin.html": 0.3,
    }
    # Wpisy blogowe: glob katalogu frontend/blog (auto-detect nowych)
    try:
        import os as _os, glob as _glob
        blog_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "frontend", "blog")
        for fp in _glob.glob(_os.path.join(blog_dir, "*.html")):
            slug = _os.path.splitext(_os.path.basename(fp))[0]
            path = f"/blog/{slug}.html"
            if path not in STATIC_PAGES:
                STATIC_PAGES[path] = 0.7
    except Exception:
        pass
    for _path, _prio in STATIC_PAGES.items():
        urls.append(f"  <url><loc>{DOMAIN}{_path}</loc><changefreq>weekly</changefreq><priority>{_prio}</priority></url>")

    # All public models: /u/{username}/{slug}
    jobs = (
        db.query(models.Job)
        .filter(
            models.Job.status.in_(["done", "hosted"]),
            models.Job.visibility == "public",
            models.Job.slug.isnot(None),
            models.Job.slug != "",
        )
        .order_by(models.Job.created_at.desc())
        .limit(5000)
        .all()
    )
    _tag_counter = {}
    for j in jobs:
        username = "anon"
        if j.user:
            username = j.user.username or "anon"
        if username == "anon":
            continue  # no PII prefixes in sitemap
        if _junk_user(username) or _junk_slug(j.slug):
            continue  # nasze wlasne testy — nie dla Google
        slug = j.slug or f"model-{j.id}"
        loc = f"{DOMAIN}/u/{_html.escape(username)}/{_html.escape(slug)}"
        lastmod = _fmt_date(j.completed_at or j.created_at)
        # views weight
        prio = "0.8" if (j.views or 0) > 10 else "0.5"
        urls.append(
            f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>"
            f"<changefreq>weekly</changefreq><priority>{prio}</priority></url>"
        )
        for _t in (j.tags or "").split(","):
            _t = _t.strip().lower()
            if _t and _t not in _JUNK_TAGS:
                _tag_counter[_t] = _tag_counter.get(_t, 0) + 1

    # Tag landing pages: /tag/{tag} — max 50, tylko tagi z >= 2 modelami
    # (tag z jednym kafelkiem = thin content dla Google, zgodnie z noindex w tag_page)
    try:
        import urllib.parse as _up
        _tag_added = 0
        for _t, _c in sorted(_tag_counter.items(), key=lambda x: -x[1]):
            if _c < 2 or _tag_added >= 50:
                continue
            _tag_added += 1
            urls.append(
                f"  <url><loc>{DOMAIN}/tag/{_up.quote(_t)}</loc>"
                f"<changefreq>weekly</changefreq><priority>0.6</priority></url>"
            )
    except Exception:
        pass

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return PlainTextResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Allow: /api/ads/slots\n"
        "Allow: /api/tags\n"
        "Disallow: /admin\n"
        "Disallow: /e/\n"
        "\n"
        "Sitemap: https://3dfile.link/sitemap.xml\n"
    )
