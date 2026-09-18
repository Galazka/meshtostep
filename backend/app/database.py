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
            add_col(conn, "users", "token_version", "INTEGER DEFAULT 0", existing)
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
        # dead payments column: NOT NULL without default breaks INSERTs (model has no credits attr)
        try:
            existing_u = {c["name"] for c in insp.get_columns("users")}
            if "credits" in existing_u and is_pg:
                conn.execute(text("ALTER TABLE users ALTER COLUMN credits DROP NOT NULL"))
                print("[3dfile] Relaxed users.credits NOT NULL")
        except Exception as e:
            print(f"[3dfile] credits relax: {e}")
        try:
            existing = {c["name"] for c in insp.get_columns("users")}
            add_col(conn, "users", "quota_limit_bytes", "INTEGER DEFAULT 104857600", existing)
            add_col(conn, "users", "bonus_mb", "INTEGER DEFAULT 0", existing)
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
        try:
            existing_orders = {c["name"] for c in insp.get_columns("orders")}
            add_col(conn, "orders", "job_uuid", "VARCHAR(64)", existing_orders)
            add_col(conn, "orders", "discount_pln", "FLOAT DEFAULT 0", existing_orders)
            add_col(conn, "orders", "print_parts", "INTEGER DEFAULT 1", existing_orders)
            add_col(conn, "orders", "admin_notes", "TEXT", existing_orders)
            add_col(conn, "orders", "customer_phone", "VARCHAR(30)", existing_orders)
            add_col(conn, "orders", "filament_cost", "FLOAT DEFAULT 0", existing_orders)
            add_col(conn, "orders", "electricity_cost", "FLOAT DEFAULT 0", existing_orders)
            add_col(conn, "orders", "color_premium", "FLOAT DEFAULT 0", existing_orders)
            add_col(conn, "orders", "currency", "VARCHAR(10) DEFAULT 'PLN'", existing_orders)
            add_col(conn, "orders", "exchange_rate", "FLOAT DEFAULT 1.0", existing_orders)
            add_col(conn, "orders", "updated_at", "TIMESTAMP" if is_pg else "DATETIME", existing_orders)
        except Exception as e:
            print(f"[3dfile] orders migrate: {e}")
        conn.commit()
    # ensure tables exist
    _tbl_map = {"comments": "Comment", "ad_slots": "AdSlot", "folders": "Folder", "job_ratings": "JobRating", "user_likes": "UserLike", "orders": "Order", "print_requests": "PrintRequest", "pricing_config": "PricingConfig"}
    for tbl in ["comments","ad_slots","folders","job_ratings","user_likes","orders","print_requests","pricing_config"]:
        try:
            if not inspect(engine).has_table(tbl):
                from . import models as m
                getattr(m, _tbl_map[tbl]).__table__.create(engine)
                print(f"[3dfile] Created {tbl}")
        except Exception as e:
            print(f"[3dfile] {tbl} create: {e}")

def init_db():
    from . import models
    # Alembic is source of truth; legacy create_all+migrate stays as fallback
    try:
        from alembic.config import Config as _ACfg
        from alembic import command as _acmd
        _cfg = _ACfg("/app/alembic.ini")
        _cfg.set_main_option("script_location", "/app/alembic")
        _acmd.upgrade(_cfg, "head")
        print("[3dfile] alembic upgrade head OK")
        # create_all is idempotent — adds any tables missing from alembic (e.g. new order_items)
        models.Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[3dfile] alembic upgrade failed, legacy fallback: {e}")
        models.Base.metadata.create_all(bind=engine)
        # self-heal: if schema exists but was never stamped, stamp head
        try:
            import os as _os
            from sqlalchemy import inspect as _insp
            from alembic.config import Config as _ACfg2
            from alembic import command as _acmd2
            if "alembic_version" not in _insp(engine).get_table_names():
                _cfg2 = _ACfg2("/app/alembic.ini") if _os.path.exists("/app/alembic.ini") else _ACfg("alembic.ini")
                _cfg2.set_main_option("script_location", "/app/alembic" if _os.path.exists("/app/alembic") else "alembic")
                _acmd2.stamp(_cfg2, "head")
                print("[3dfile] stamped baseline head")
        except Exception as e2:
            print(f"[3dfile] stamp skipped: {e2}")
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
                (AdSlot.ad_code.is_(None)) | (AdSlot.ad_code == "") | (AdSlot.ad_code == "<!-- AdSense: wstaw kod -->")
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
