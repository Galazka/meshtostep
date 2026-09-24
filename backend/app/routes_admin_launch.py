"""Panel 'Uruchomienie' — stan serwisu + sprzatanie testowych smieci + reset.

Wszystko pod /api/admin/launch/*, admin only. Zamiar: jedno miejsce gdzie widac
czy portal jest gotowy do ruchu (modele, zasmiecenie, zamowienia, SEO, sloty reklam)
i jednym klikiem wyczyscic wlasne testy przed startem.
"""
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from . import models
from .auth import require_admin
from .config import settings
from .database import get_db

router = APIRouter(prefix="/api/admin/launch", tags=["admin-launch"])

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend"
)

_JUNK_USER_RE = re.compile(r"^(uitest|e2e|demouser|testuser|test\d|demo\d|smtptest|admin\d)", re.I)
_JUNK_TAGS = {"test", "demo", "asdf", "qwerty", "abc", "xxx", "tmp"}
_JUNK_AD_RE = re.compile(r"(test|asdf|qwerty|lorem|xxx)", re.I)
CONFIRM = "USUWAM"


# ── helpers ────────────────────────────────────────────────────────────
def _junk_user(name) -> bool:
    if not name:
        return False
    return bool(_JUNK_USER_RE.match(str(name).strip()))


def _junk_slug(slug) -> bool:
    s = str(slug or "").strip().lower()
    if not s:
        return True
    return any(t in s for t in ("uitest", "-test-", "test-")) or s in ("test", "demo", "model")


def _job_dir(uuid: str) -> str:
    return os.path.join(settings.DATA_DIR, "files", uuid or "")


def _rm_tree(path: str) -> bool:
    import shutil
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            return True
    except Exception:
        pass
    return False


def _delete_job_row(db: Session, job: models.Job, remove_files: bool = True):
    """Kasuje model wraz ze wszystkim co na niego wskazuje.

    UWAGA: najpierw ODPINAMY miekkie referencje (kolumny nullable bez FK),
    bo Postgres ma tu NO ACTION i DELETE wywala sie na violation.
    """
    jid = job.id
    db.query(models.ShareLink).filter(models.ShareLink.job_id == jid).delete()
    db.query(models.Comment).filter(models.Comment.job_id == jid).delete()
    db.query(models.JobRating).filter(models.JobRating.job_id == jid).delete()
    db.query(models.UserLike).filter(models.UserLike.job_id == jid).delete()
    for sql in (
        "UPDATE print_requests SET job_id=NULL WHERE job_id=:j",
        "UPDATE orders SET job_id=NULL WHERE job_id=:j",
        "UPDATE order_items SET job_id=NULL WHERE job_id=:j",
        "UPDATE jobs SET folder_id=NULL WHERE id=:j",
    ):
        db.execute(text(sql), {"j": jid})
    if remove_files and job.uuid:
        _rm_tree(_job_dir(job.uuid))
    db.delete(job)
    db.flush()


def _purge_user_deps(db: Session, uid: int):
    """Odepnij/usun WSZYSTKO co wskazuje na konto, zanim je skasujemy (FK NO ACTION).

    Kolejnosc ma znaczenie: oferty -> prosby o druk, opinie -> oferty.
    Historia zamowien NIE jest kasowana, tylko odpinana od konta (user_id=NULL).
    """
    steps = (
        "DELETE FROM comments WHERE user_id=:u",
        "DELETE FROM job_ratings WHERE user_id=:u",
        "DELETE FROM user_likes WHERE user_id=:u",
        "DELETE FROM geo_logs WHERE user_id=:u",
        "DELETE FROM share_links WHERE user_id=:u",
        "DELETE FROM job_reviews WHERE reviewer_id=:u",
        "DELETE FROM job_reviews WHERE offer_id IN (SELECT id FROM print_offers WHERE user_id=:u)",
        "DELETE FROM print_offers WHERE user_id=:u",
        "DELETE FROM print_offers WHERE request_id IN (SELECT id FROM print_requests WHERE user_id=:u)",
        "UPDATE print_requests SET job_id=NULL WHERE user_id=:u",
        "DELETE FROM print_requests WHERE user_id=:u",
        "UPDATE orders SET user_id=NULL WHERE user_id=:u",
        "UPDATE page_events SET user_id=NULL WHERE user_id=:u",
        # modele tego usera: wpisy spolecznosciowe po job_id
        "DELETE FROM comments WHERE job_id IN (SELECT id FROM jobs WHERE user_id=:u)",
        "DELETE FROM job_ratings WHERE job_id IN (SELECT id FROM jobs WHERE user_id=:u)",
        "DELETE FROM user_likes WHERE job_id IN (SELECT id FROM jobs WHERE user_id=:u)",
        "DELETE FROM share_links WHERE job_id IN (SELECT id FROM jobs WHERE user_id=:u)",
        "UPDATE print_requests SET job_id=NULL WHERE job_id IN (SELECT id FROM jobs WHERE user_id=:u)",
        "UPDATE orders SET job_id=NULL WHERE job_id IN (SELECT id FROM jobs WHERE user_id=:u)",
        "UPDATE order_items SET job_id=NULL WHERE job_id IN (SELECT id FROM jobs WHERE user_id=:u)",
        "UPDATE jobs SET folder_id=NULL WHERE user_id=:u",
        "DELETE FROM folders WHERE user_id=:u",
    )
    for sql in steps:
        try:
            db.execute(text(sql), {"u": uid})
        except Exception as e:  # kolumna/tabela moze nie istniec na starszej bazie
            print(f"[launch] purge user {uid}: pomijam ({type(e).__name__}: {e})")


def _gather(db: Session):
    """Zbierz wszystkie smieci-testowe (nie usuwajac) — uzywane przez state i cleanup."""
    users = db.query(models.User).all()
    admins = {u.id for u in users if getattr(u, "is_admin", False)}
    junk_users = [u for u in users if u.id not in admins and _junk_user(getattr(u, "username", ""))]

    jobs = db.query(models.Job).all()
    junk_jobs = []
    for j in jobs:
        uname = j.user.username if j.user else ""
        if _junk_slug(j.slug) or _junk_user(uname) or j.user_id in {u.id for u in junk_users}:
            junk_jobs.append(j)

    ads = db.query(models.AdSlot).all()
    junk_ads = [a for a in ads if _JUNK_AD_RE.search(f"{a.name or ''} {a.ad_code or ''}")]

    return {"users": users, "admins": admins, "junk_users": junk_users,
            "jobs": jobs, "junk_jobs": junk_jobs, "ads": ads, "junk_ads": junk_ads}


# ── 1. STAN SERWISU ────────────────────────────────────────────────────
@router.get("/state")
def launch_state(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    g = _gather(db)

    def _cnt(model, *flt):
        q = db.query(func.count(model.id))
        if flt:
            q = q.filter(*flt)
        try:
            return int(q.scalar() or 0)
        except Exception:
            return 0

    models_total = len(g["jobs"])
    models_public = _cnt(models.Job, models.Job.visibility == "public")
    models_junk = len(g["junk_jobs"])
    users_total = len(g["users"])
    users_junk = len(g["junk_users"])

    orders_total = _cnt(models.Order)
    orders_paid = _cnt(models.Order, models.Order.is_paid == True)  # noqa: E712
    try:
        orders_open = int(db.execute(text(
            "SELECT COUNT(*) FROM orders WHERE COALESCE(is_paid,false)=false"
        )).scalar() or 0)
    except Exception:
        orders_open = orders_total - orders_paid

    ads_total = len(g["ads"])
    ads_junk = len(g["junk_ads"])
    ads_active = sum(1 for a in g["ads"] if getattr(a, "is_active", False))

    blog_dir = os.path.join(FRONTEND_DIR, "blog")
    try:
        blog_n = len([f for f in os.listdir(blog_dir) if f.endswith(".html")])
    except Exception:
        blog_n = 0

    try:
        ev_n = int(db.execute(text("SELECT COUNT(*) FROM page_events")).scalar() or 0)
    except Exception:
        ev_n = 0

    issues = []
    if models_junk:
        issues.append({"level": "warn", "code": "junk_models",
                       "text": f"{models_junk} testowych modeli w indeksie/przegladarce",
                       "fix": "cleanup-test"})
    if users_junk:
        issues.append({"level": "warn", "code": "junk_users",
                       "text": f"{users_junk} kont testowych",
                       "fix": "cleanup-test"})
    if ads_junk:
        issues.append({"level": "info", "code": "junk_ads",
                       "text": f"{ads_junk} slotow reklamowych z testowym kodem",
                       "fix": "cleanup-ads"})
    if orders_open:
        issues.append({"level": "info", "code": "orders_open",
                       "text": f"{orders_open} zamowien nieoplaconych w bazie",
                       "fix": "reset-orders"})
    if blog_n < 6:
        issues.append({"level": "warn", "code": "blog_thin",
                       "text": f"tylko {blog_n} artykulow bloga (SEO chce >= 6)", "fix": None})
    if not ads_active:
        issues.append({"level": "info", "code": "ads_off",
                       "text": "zaden slot reklamowy nie jest aktywny", "fix": "admin/ads"})

    return {
        "ok": True,
        "models": {"total": models_total, "public": models_public, "junk": models_junk,
                   "clean": models_total - models_junk},
        "users": {"total": users_total, "junk": users_junk, "admins": len(g["admins"]),
                  "clean": users_total - users_junk},
        "orders": {"total": orders_total, "paid": orders_paid, "open": orders_open},
        "ads": {"total": ads_total, "active": ads_active, "junk": ads_junk},
        "seo": {"blog_articles": blog_n, "sitemap": "https://3dfile.link/sitemap.xml"},
        "analytics": {"page_events": ev_n},
        "issues": issues,
    }


# ── 2. SPRZATANIE TESTOW ───────────────────────────────────────────────
@router.post("/cleanup-test")
def cleanup_test(
    dry_run: bool = Query(True),
    remove_files: bool = Query(True),
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Usuwa WYLACZNIE testowe konta/modele/sloty. Adminow nigdy nie rusza."""
    g = _gather(db)
    report = {
        "dry_run": dry_run,
        "users": [{"id": u.id, "username": u.username} for u in g["junk_users"]],
        "models": [{"id": j.id, "slug": j.slug,
                    "user": (j.user.username if j.user else None)} for j in g["junk_jobs"]],
        "ads": [{"id": a.id, "name": a.name, "slot_key": a.slot_key} for a in g["junk_ads"]],
    }
    if dry_run:
        report["ok"] = True
        report["counts"] = {"users": len(g["junk_users"]), "models": len(g["junk_jobs"]),
                            "ads": len(g["junk_ads"])}
        return report

    removed_files = 0
    try:
        for j in g["junk_jobs"]:
            if remove_files and j.uuid and _rm_tree(_job_dir(j.uuid)):
                removed_files += 1
            _delete_job_row(db, j, remove_files=False)
        db.flush()

        for u in g["junk_users"]:
            _purge_user_deps(db, u.id)
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": u.id})
        db.flush()

        for a in g["junk_ads"]:
            db.delete(a)

        db.commit()
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=f"cleanup nieudany: {type(e).__name__}: {e}")
    report["ok"] = True
    report["removed"] = {"users": len(g["junk_users"]), "models": len(g["junk_jobs"]),
                         "ads": len(g["junk_ads"]), "file_dirs": removed_files}
    return report


# ── 3. RESET ZAKRESOWY (na haslo) ──────────────────────────────────────
@router.post("/reset")
def launch_reset(
    scope: str = Query("all", description="models|users|orders|ads|analytics|all"),
    confirm: str = Query("", description=f"wpisz {CONFIRM}"),
    keep_admin: bool = Query(True),
    remove_files: bool = Query(True),
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if confirm.strip().upper() != CONFIRM:
        raise HTTPException(400, detail=f'Wpisz "{CONFIRM}" aby potwierdzic. Nic nie usunieto.')
    scope = (scope or "all").lower()
    out = {}

    if scope in ("models", "all"):
        jobs = db.query(models.Job).all()
        for j in jobs:
            if remove_files and j.uuid:
                _rm_tree(_job_dir(j.uuid))
            _delete_job_row(db, j, remove_files=False)
        out["models"] = len(jobs)

    if scope in ("users", "all"):
        q = db.query(models.User)
        users = [u for u in q.all() if not (keep_admin and getattr(u, "is_admin", False))]
        try:
            for u in users:
                _purge_user_deps(db, u.id)
                db.execute(text("DELETE FROM users WHERE id=:u"), {"u": u.id})
            db.flush()
        except Exception as e:
            db.rollback()
            import traceback
            traceback.print_exc()
            raise HTTPException(500, detail=f"reset users nieudany: {type(e).__name__}: {e}")
        out["users"] = len(users)

    if scope in ("orders", "all"):
        n = int(db.query(func.count(models.Order.id)).scalar() or 0)
        db.query(models.OrderItem).delete()
        db.query(models.OrderReview).delete()
        db.query(models.Order).delete()
        out["orders"] = n

    if scope in ("ads", "all"):
        n = int(db.query(func.count(models.AdSlot.id)).scalar() or 0)
        db.query(models.AdSlot).delete()
        out["ads"] = n

    if scope in ("analytics", "all"):
        try:
            n = int(db.execute(text("SELECT COUNT(*) FROM page_events")).scalar() or 0)
            db.execute(text("DELETE FROM page_events"))
            out["page_events"] = n
        except Exception:
            out["page_events"] = 0

    db.commit()
    return {"ok": True, "scope": scope, "removed": out}
