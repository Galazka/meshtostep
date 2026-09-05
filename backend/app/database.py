"""SQLAlchemy session management — SQLite and PostgreSQL."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .config import settings

connect_args = {}
engine_kwargs = {"pool_pre_ping": True}  # auto-reconnect

if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine_kwargs["connect_args"] = connect_args
else:
    # PostgreSQL pooling
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
    """Add missing columns to existing tables (SQLite + PostgreSQL safe)."""
    from sqlalchemy import text, inspect
    is_pg = not settings.DATABASE_URL.startswith("sqlite")
    with engine.connect() as conn:
        inspector = inspect(engine)
        existing = {col["name"] for col in inspector.get_columns("users")}
        new_cols = {
            "terms_accepted_at": "TIMESTAMP" if is_pg else "DATETIME",
            "privacy_accepted_at": "TIMESTAMP" if is_pg else "DATETIME",
            "marketing_consent": "BOOLEAN DEFAULT FALSE",
            "registered_ip": "VARCHAR(45)" if is_pg else "VARCHAR(45)",
            "register_user_agent": "TEXT",
        }
        for col, dtype in new_cols.items():
            if col not in existing:
                conn.execute(text(f'ALTER TABLE users ADD COLUMN {col} {dtype}'))
                print(f"[MeshToStep] Added column users.{col}")
        conn.commit()


def init_db():
    from . import models
    from .config import settings
    models.Base.metadata.create_all(bind=engine)

    # Migrate missing columns for GDPR fields
    try:
        _migrate_columns()
    except Exception as e:
        print(f"[MeshToStep] Migration warning: {e}")

    # Seed credit packs
    db = SessionLocal()
    try:
        if db.query(models.CreditPack).count() == 0:
            db.add_all([
                models.CreditPack(name="Start 5", credits=5, price_usd=0.99),
                models.CreditPack(name="Pack 25", credits=25, price_usd=2.99),
                models.CreditPack(name="Pack 100", credits=100, price_usd=7.99),
            ])
            db.commit()

        # Bootstrap admin from env (first run)
        if settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD:
            admin = db.query(models.User).filter(
                models.User.email == settings.ADMIN_EMAIL.lower().strip()
            ).first()
            if not admin:
                from .auth import hash_password
                admin = models.User(
                    email=settings.ADMIN_EMAIL.lower().strip(),
                    password_hash=hash_password(settings.ADMIN_PASSWORD),
                    credits=999999,
                    is_admin=True,
                    email_verified=True,
                )
                db.add(admin)
                db.commit()
                print(f"[MeshToStep] Bootstrap admin created: {settings.ADMIN_EMAIL}")
            elif not admin.is_admin:
                admin.is_admin = True
                db.commit()
                print(f"[MeshToStep] Promoted to admin: {settings.ADMIN_EMAIL}")
    finally:
        db.close()
