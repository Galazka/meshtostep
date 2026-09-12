"""SQLAlchemy session management — SQLite and PostgreSQL. — 3dfile.link"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings

connect_args = {}
engine_kwargs = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine_kwargs["connect_args"] = connect_args
else:
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _migrate_columns():
    from sqlalchemy import text, inspect
    is_pg = not settings.DATABASE_URL.startswith("sqlite")
    def add_col(conn, table, col, dtype, existing):
        if col not in existing:
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {dtype}'))
            print(f"[3dfile] Added {table}.{col}")

    with engine.connect() as conn:
        insp = inspect(engine)
        # users
        try:
            existing = {c["name"] for c in insp.get_columns("users")}
            add_col(conn, "users", "username", "VARCHAR(50)", existing)
            add_col(conn, "users", "bio", "TEXT", existing)
            add_col(conn, "users", "avatar_url", "VARCHAR(512)", existing)
            add_col(conn, "users", "terms_accepted_at", "TIMESTAMP" if is_pg else "DATETIME", existing)
            add_col(conn, "users", "privacy_accepted_at", "TIMESTAMP" if is_pg else "DATETIME", existing)
            add_col(conn, "users", "marketing_consent", "BOOLEAN DEFAULT FALSE", existing)
            add_col(conn, "users", "registered_ip", "VARCHAR(64)", existing)
            add_col(conn, "users", "register_user_agent", "TEXT", existing)
            add_col(conn, "users", "keep_files_forever", "BOOLEAN DEFAULT FALSE", existing)
            add_col(conn, "users", "retention_days", "INTEGER DEFAULT 30", existing)
        except Exception as e:
            print(f"[3dfile] users migrate: {e}")
        # jobs
        try:
            existing = {c["name"] for c in insp.get_columns("jobs")}
            for col, dtype in [
                ("slug","VARCHAR(120)"),("title","VARCHAR(200)"),("description","TEXT"),
                ("tags","VARCHAR(500)"),("youtube_url","VARCHAR(512)"),
                ("visibility","VARCHAR(20) DEFAULT 'public'"),("views","INTEGER DEFAULT 0"),
                ("likes","INTEGER DEFAULT 0"),("preview_image","VARCHAR(512)"),
                ("dims_mm","VARCHAR(60)"),("volume_cm3","FLOAT"),
            ]:
                add_col(conn, "jobs", col, dtype, existing)
        except Exception as e:
            print(f"[3dfile] jobs migrate: {e}")
        # share_links
        try:
            existing = {c["name"] for c in insp.get_columns("share_links")}
            add_col(conn, "share_links", "show_author", "BOOLEAN DEFAULT TRUE", existing)
            add_col(conn, "share_links", "slug", "VARCHAR(120)", existing)
            add_col(conn, "share_links", "visibility", "VARCHAR(20) DEFAULT 'public'", existing)
        except Exception as e:
            print(f"[3dfile] share_links migrate: {e}")
        # ad_slots
        try:
            existing = {c["name"] for c in insp.get_columns("ad_slots")}
            add_col(conn, "ad_slots", "position", "VARCHAR(50)", existing)
        except Exception as e:
            print(f"[3dfile] ad_slots migrate: {e}")
        # folders + quota
        try:
            if not insp.has_table("folders"):
                from . import models as m
                m.Folder.__table__.create(engine)
                print("[3dfile] Created folders")
        except Exception as e:
            print(f"[3dfile] folders create: {e}")
        try:
            existing = {c["name"] for c in insp.get_columns("users")}
            add_col(conn, "users", "quota_limit_bytes", "INTEGER DEFAULT 104857600", existing)
        except Exception as e:
            print(f"[3dfile] quota migrate: {e}")
        try:
            existing_jobs = {c["name"] for c in insp.get_columns("jobs")}
            add_col(conn, "jobs", "dims_mm", "VARCHAR(60)", existing_jobs)
        except Exception as e:
            print(f"[3dfile] dims_mm migrate: {e}")
        try:
            existing = {c["name"] for c in insp.get_columns("jobs")}
            add_col(conn, "jobs", "folder_id", "INTEGER", existing)
        except Exception as e:
            print(f"[3dfile] folder_id migrate: {e}")
        conn.commit()
    # ensure tables exist
    _tbl_map = {"comments": "Comment", "ad_slots": "AdSlot", "folders": "Folder", "job_ratings": "JobRating", "user_likes": "UserLike"}
    for tbl in ["comments","ad_slots","folders","job_ratings","user_likes"]:
        try:
            if not inspect(engine).has_table(tbl):
                from . import models as m
                getattr(m, _tbl_map[tbl]).__table__.create(engine)
                print(f"[3dfile] Created {tbl}")
        except Exception as e:
            print(f"[3dfile] {tbl} create: {e}")

def init_db():
    from . import models
    models.Base.metadata.create_all(bind=engine)
    try:
        _migrate_columns()
    except Exception as e:
        print(f"[3dfile] Migration warning: {e}")
    db = SessionLocal()
    try:
        if settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD:
            admin = db.query(models.User).filter(models.User.email == settings.ADMIN_EMAIL.lower().strip()).first()
            if not admin:
                from .auth import hash_password
                admin = models.User(email=settings.ADMIN_EMAIL.lower().strip(), password_hash=hash_password(settings.ADMIN_PASSWORD), is_admin=True, email_verified=True)
                db.add(admin); db.commit()
                print(f"[3dfile] Bootstrap admin {settings.ADMIN_EMAIL}")
            elif not admin.is_admin:
                admin.is_admin=True; db.commit()
        # Ad slots: clean junk + seed if empty
        try:
            from .models import AdSlot
            junk = db.query(AdSlot).filter(
                AdSlot.ad_code.like("%><%")
            ).all()
            for j in junk:
                db.delete(j)
            if junk:
                db.commit()
                print(f"[3dfile] Cleaned {len(junk)} junk ad slots")
            if db.query(AdSlot).count() == 0:
                for s in [
                    ("Hero top", "hero_top", 99),
                    ("Hero bottom", "hero_bottom", 100),
                    ("After convert", "after_convert", 50),
                    ("Page bottom", "page_bottom", 200),
                    ("Search top", "search_top", 75),
                ]:
                    db.add(AdSlot(name=s[0], slot_key=s[1], position=s[1],
                                  ad_code="<!-- AdSense: wstaw kod -->", ad_type="adsense",
                                  sort_order=s[2], is_active=True))
                db.commit()
                print("[3dfile] Seeded 5 default ad slots")
        except Exception as e:
            print(f"[3dfile] Ad slot seed warning: {e}")
    finally:
        db.close()
