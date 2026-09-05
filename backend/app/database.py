"""SQLAlchemy session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models
    models.Base.metadata.create_all(bind=engine)
    # Seed credit packs
    db = SessionLocal()
    try:
        if db.query(models.CreditPack).count() == 0:
            db.add_all([
                models.CreditPack(name="Start 5", credits=5, price_pln=0.50),
                models.CreditPack(name="Pakiet 25", credits=25, price_pln=1.99),
                models.CreditPack(name="Pakiet 100", credits=100, price_pln=5.99),
            ])
            db.commit()
    finally:
        db.close()
