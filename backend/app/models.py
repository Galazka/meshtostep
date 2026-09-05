"""Database models: users, credits, jobs, share links."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    credits = Column(Integer, default=3, nullable=False)  # 3 free on signup
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    jobs = relationship("Job", back_populates="user")
    shares = relationship("ShareLink", back_populates="user")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # nullable for anon
    uuid = Column(String(32), unique=True, nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, default=0)
    mode = Column(String(20), default="auto")  # auto/ultra/light/off/smooth
    status = Column(String(20), default="pending")  # pending/processing/done/error
    result_faces = Column(Integer)
    result_size_bytes = Column(Integer)
    result_step_path = Column(String(512))
    result_stl_path = Column(String(512))
    error_msg = Column(Text)
    processing_time_s = Column(Float)
    credits_used = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    user = relationship("User", back_populates="jobs")
    shares = relationship("ShareLink", back_populates="job")


class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(16), unique=True, nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    format = Column(String(10), default="step")  # step/stl/both
    downloads = Column(Integer, default=0)
    max_downloads = Column(Integer, nullable=True)  # None = unlimited
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    job = relationship("Job", back_populates="shares")
    user = relationship("User", back_populates="shares")


class CreditPack(Base):
    __tablename__ = "credit_packs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)  # "5 credits"
    credits = Column(Integer, nullable=False)
    price_pln = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pack_id = Column(Integer, ForeignKey("credit_packs.id"), nullable=True)
    amount_pln = Column(Float, nullable=False)
    credits_granted = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending/completed/failed
    payment_method = Column(String(20))  # blik/card/transfer
    reference = Column(String(100))  # external payment reference
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    pack = relationship("CreditPack")
