"""Database models: users, credits, jobs, share links, geo tracking, credit adjustments."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    credits = Column(Integer, default=3, nullable=False)  # 3 free on signup (legacy, unused in free mode)
    is_admin = Column(Boolean, default=False)
    keep_files_forever = Column(Boolean, default=False)  # premium: files not deleted after 30d
    retention_days = Column(Integer, default=30)  # file retention: 30 default, +7 per ad click, max 180
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    # -- hardening --
    email_verified = Column(Boolean, default=False)
    verification_token = Column(String(64), nullable=True)
    failed_logins = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    reset_token = Column(String(64), nullable=True)
    reset_expires = Column(DateTime, nullable=True)
    # -- RODO: zgody i audyt --
    terms_accepted_at = Column(DateTime, nullable=True)  # kiedy zaakceptowal regulamin
    privacy_accepted_at = Column(DateTime, nullable=True)  # kiedy zaakceptowal polityke
    marketing_consent = Column(Boolean, default=False)  # zgoda marketingowa (opcjonalna)
    registered_ip = Column(String(64), nullable=True)  # IP rejestracji (audyt)
    register_user_agent = Column(String(512), nullable=True)  # UA rejestracji (audyt)

    jobs = relationship("Job", back_populates="user")
    shares = relationship("ShareLink", back_populates="user")
    geo_logs = relationship("GeoLog", back_populates="user")
    credit_adjustments = relationship(
        "CreditAdjustment", back_populates="user",
        foreign_keys="CreditAdjustment.user_id"
    )


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
    views = Column(Integer, default=0)  # track share page views
    show_author = Column(Boolean, default=True)  # display author email on share page

    job = relationship("Job", back_populates="shares")
    user = relationship("User", back_populates="shares")


class CreditPack(Base):
    __tablename__ = "credit_packs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)  # "5 credits"
    credits = Column(Integer, nullable=False)
    price_usd = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pack_id = Column(Integer, ForeignKey("credit_packs.id"), nullable=True)
    amount_usd = Column(Float, nullable=False)
    credits_granted = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending/completed/failed
    payment_method = Column(String(20))  # blik/card/transfer
    reference = Column(String(100))  # external payment reference
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    pack = relationship("CreditPack")


class GeoLog(Base):
    """Tracks IP, country, city for every request with geo data."""
    __tablename__ = "geo_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # nullable for anon
    ip_address = Column(String(45), nullable=False)  # IPv4 or IPv6
    country = Column(String(100), nullable=True)
    city = Column(String(200), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    user_agent = Column(String(500), nullable=True)
    endpoint = Column(String(200), nullable=True)  # which route triggered this
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="geo_logs")


class CreditAdjustment(Base):
    """Admin manual credit adjustments with full audit trail."""
    __tablename__ = "credit_adjustments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # who made the change
    amount = Column(Integer, nullable=False)  # positive = grant, negative = revoke
    reason = Column(Text, nullable=True)
    credits_before = Column(Integer, nullable=False)  # snapshot before
    credits_after = Column(Integer, nullable=False)   # snapshot after
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="credit_adjustments", foreign_keys=[user_id])
    admin = relationship("User", foreign_keys=[admin_id])


class AdSlot(Base):
    """Ad slots for monetization (AdSense etc.). Managed via admin panel."""
    __tablename__ = "ad_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)  # "Banner pod konwerterem"
    slot_key = Column(String(50), unique=True, nullable=False)  # "hero_bottom", "after_convert"
    ad_code = Column(Text, nullable=False)  # HTML/JS snippet
    ad_type = Column(String(20), default="adsense")  # adsense / custom / image
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
