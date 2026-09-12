import html as _html
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session
from . import models
from .database import get_db

router = APIRouter()

DOMAIN = \"https://3dfile.link\"

def _fmt_date(dt) -> str:
    if not dt:
        return datetime.utcnow().strftime(\"%Y-%m-%d\")
    return str(dt)[:10]

@router.get(\"/sitemap.xml\", response_class=Response)
def sitemap(request: Request, db: Session = Depends(get_db)):
    urls = []
    # Homepage
    urls.append(f\"  <url><loc>{DOMAIN}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>\")
    
    # All public models: /u/{username}/{slug}
    jobs = (
        db.query(models.Job)
        .filter(
            models.Job.status.in_([\"done\", \"hosted\"]),
            models.Job.visibility == \"public\",
            models.Job.slug.isnot(None),
            models.Job.slug != \"\",
        )
        .order_by(models.Job.created_at.desc())
        .limit(5000)
        .all()
    )
    for j in jobs:
        username = \"anon\"
        if j.user:
            username = j.user.username or (j.user.email.split(\"@\")[0] if j.user.email else \"anon\")
        slug = j.slug or f\"model-{j.id}\"
        loc = f\"{DOMAIN}/u/{_html.escape(username)}/{_html.escape(slug)}\"
        lastmod = _fmt_date(j.completed_at or j.created_at)
        prio = \"0.8\" if (j.views or 0) > 10 else \"0.5\"
        urls.append(
            f\"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>\"\n
            f\"<changefreq>weekly</changefreq><priority>{prio}</priority></url>\"
        )
    
    xml = (
        '<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n'
        + '<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\\n'
        + \"\\n\".join(urls)
        + \"\\n</urlset>\"
    )
    return Response(content=xml, media_type=\"application/xml\")

@router.get(\"/robots.txt\", response_class=PlainTextResponse)
def robots_txt():\n    return PlainTextResponse(\n        \"User-agent: *\\n\"\n        \"Allow: /\\n\"\n        \"Disallow: /api/\\n\"\n        \"Allow: /api/ads/slots\\n\"\n        \"Allow: /api/tags\\n\"\n        \"Disallow: /admin\\n\"\n        \"Disallow: /e/\\n\"\n        \"Sitemap: https://3dfile.link/sitemap.xml\\n\"\n    )