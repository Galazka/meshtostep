"""SQLAlchemy session management — SQLite and PostgreSQL. — 3dhosty.com"""
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
            print(f"[3dhosty] Added {table}.{col}")

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
            print(f"[3dhosty] users migrate: {e}")
        # jobs
        try:
            existing = {c["name"] for c in insp.get_columns("jobs")}
            for col, dtype in [
                ("slug","VARCHAR(120)"),("title","VARCHAR(200)"),("description","TEXT"),
                ("tags","VARCHAR(500)"),("youtube_url","VARCHAR(512)"),
                ("visibility","VARCHAR(20) DEFAULT 'public'"),("views","INTEGER DEFAULT 0"),
                ("likes","INTEGER DEFAULT 0"),("is_paid","BOOLEAN DEFAULT FALSE"),
                ("price_cents","INTEGER DEFAULT 0"),("preview_image","VARCHAR(512)"),
            ]:
                add_col(conn, "jobs", col, dtype, existing)
        except Exception as e:
            print(f"[3dhosty] jobs migrate: {e}")
        # share_links
        try:
            existing = {c["name"] for c in insp.get_columns("share_links")}
            add_col(conn, "share_links", "show_author", "BOOLEAN DEFAULT TRUE", existing)
            add_col(conn, "share_links", "slug", "VARCHAR(120)", existing)
            add_col(conn, "share_links", "visibility", "VARCHAR(20) DEFAULT 'public'", existing)
        except Exception as e:
            print(f"[3dhosty] share_links migrate: {e}")
        # ad_slots
        try:
            existing = {c["name"] for c in insp.get_columns("ad_slots")}
            add_col(conn, "ad_slots", "position", "VARCHAR(50)", existing)
        except Exception as e:
            print(f"[3dhosty] ad_slots migrate: {e}")
        conn.commit()
    # ensure tables exist
    for tbl in ["comments","sales","ad_slots"]:
        try:
            if not inspect(engine).has_table(tbl):
                from . import models as m
                getattr(m, {"comments": "Comment", "sales": "Sale", "ad_slots": "AdSlot"}[tbl]).__table__.create(engine)
                print(f"[3dhosty] Created {tbl}")
        except Exception as e:
            print(f"[3dhosty] {tbl} create: {e}")

def init_db():
    from . import models
    models.Base.metadata.create_all(bind=engine)
    try:
        _migrate_columns()
    except Exception as e:
        print(f"[3dhosty] Migration warning: {e}")
    db = SessionLocal()
    try:
        if db.query(models.CreditPack).count() == 0:
            db.add_all([models.CreditPack(name="Start 5", credits=5, price_usd=0.99),models.CreditPack(name="Pack 25", credits=25, price_usd=2.99),models.CreditPack(name="Pack 100", credits=100, price_usd=7.99)])
            db.commit()
        if settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD:
            admin = db.query(models.User).filter(models.User.email == settings.ADMIN_EMAIL.lower().strip()).first()
            if not admin:
                from .auth import hash_password
                admin = models.User(email=settings.ADMIN_EMAIL.lower().strip(), password_hash=hash_password(settings.ADMIN_PASSWORD), credits=999999, is_admin=True, email_verified=True)
                db.add(admin); db.commit()
                print(f"[3dhosty] Bootstrap admin {settings.ADMIN_EMAIL}")
            elif not admin.is_admin:
                admin.is_admin=True; db.commit()
    finally:
        db.close()
