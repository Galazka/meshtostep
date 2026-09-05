"""Database models: users, jobs, shares, comments, sales, geo, ads. — 3dhosty.com"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=True, index=True)  # for /u/{username}/{slug}
    password_hash = Column(String(255), nullable=False)
    credits = Column(Integer, default=3, nullable=False)
    is_admin = Column(Boolean, default=False)
    keep_files_forever = Column(Boolean, default=False)
    retention_days = Column(Integer, default=30)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    email_verified = Column(Boolean, default=False)
    verification_token = Column(String(64), nullable=True)
    failed_logins = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    reset_token = Column(String(64), nullable=True)
    reset_expires = Column(DateTime, nullable=True)
    terms_accepted_at = Column(DateTime, nullable=True)
    privacy_accepted_at = Column(DateTime, nullable=True)
    marketing_consent = Column(Boolean, default=False)
    registered_ip = Column(String(64), nullable=True)
    register_user_agent = Column(String(512), nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(512), nullable=True)
    quota_limit_bytes = Column(Integer, default=500 * 1024 * 1024, nullable=False)  # 500 MB

    jobs = relationship("Job", back_populates="user")
    folders = relationship("Folder", back_populates="user", cascade="all, delete-orphan")
    shares = relationship("ShareLink", back_populates="user")
    geo_logs = relationship("GeoLog", back_populates="user")
    credit_adjustments = relationship("CreditAdjustment", back_populates="user", foreign_keys="CreditAdjustment.user_id")
    comments = relationship("Comment", back_populates="user")
    sales_as_seller = relationship("Sale", back_populates="seller", foreign_keys="Sale.seller_id")
    sales_as_buyer = relationship("Sale", back_populates="buyer", foreign_keys="Sale.buyer_id")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    uuid = Column(String(32), unique=True, nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, default=0)
    mode = Column(String(20), default="auto")
    status = Column(String(20), default="pending")
    result_faces = Column(Integer)
    result_size_bytes = Column(Integer)
    result_step_path = Column(String(512))
    result_stl_path = Column(String(512))
    error_msg = Column(Text)
    processing_time_s = Column(Float)
    credits_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    # community fields
    slug = Column(String(120), nullable=True, index=True)  # editable part of /u/{username}/{slug}
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)  # markdown
    tags = Column(String(500), nullable=True)  # comma-separated
    youtube_url = Column(String(512), nullable=True)
    visibility = Column(String(20), default="public")  # public / unlisted / private
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    is_paid = Column(Boolean, default=False)
    price_cents = Column(Integer, default=0)  # price in cents (USD or PLN — frontend decides)
    preview_image = Column(String(512), nullable=True)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True, index=True)
    # ponytail: no folder nesting (single level). Add Folder.parent_id when needed.

    user = relationship("User", back_populates="jobs")
    folder = relationship("Folder", back_populates="jobs")
    shares = relationship("ShareLink", back_populates="job")
    comments = relationship("Comment", back_populates="job")


class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(16), unique=True, nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    format = Column(String(10), default="step")
    downloads = Column(Integer, default=0)
    max_downloads = Column(Integer, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    views = Column(Integer, default=0)
    show_author = Column(Boolean, default=True)
    slug = Column(String(120), nullable=True)
    visibility = Column(String(20), default="public")  # public / unlisted / private

    job = relationship("Job", back_populates="shares")
    user = relationship("User", back_populates="shares")


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_hidden = Column(Boolean, default=False)
    job = relationship("Job", back_populates="comments")
    user = relationship("User", back_populates="comments")


class Sale(Base):
    """Paid model purchase — 20% commission."""
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null for anon Stripe checkout
    amount_cents = Column(Integer, nullable=False)
    commission_cents = Column(Integer, nullable=False)  # 20%
    seller_payout_cents = Column(Integer, nullable=False)
    stripe_session_id = Column(String(200), nullable=True)
    stripe_payment_id = Column(String(200), nullable=True)
    status = Column(String(20), default="pending")  # pending/completed/failed/refunded
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    job = relationship("Job")
    seller = relationship("User", back_populates="sales_as_seller", foreign_keys=[seller_id])
    buyer = relationship("User", back_populates="sales_as_buyer", foreign_keys=[buyer_id])


class CreditPack(Base):
    __tablename__ = "credit_packs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
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
    status = Column(String(20), default="pending")
    payment_method = Column(String(20))
    reference = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User")
    pack = relationship("CreditPack")


class GeoLog(Base):
    __tablename__ = "geo_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ip_address = Column(String(45), nullable=False)
    country = Column(String(100), nullable=True)
    city = Column(String(200), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    user_agent = Column(String(500), nullable=True)
    endpoint = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="geo_logs")


class CreditAdjustment(Base):
    __tablename__ = "credit_adjustments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    credits_before = Column(Integer, nullable=False)
    credits_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="credit_adjustments", foreign_keys=[user_id])
    admin = relationship("User", foreign_keys=[admin_id])


class AdSlot(Base):
    """Ad slots — position map for admin."""
    __tablename__ = "ad_slots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    slot_key = Column(String(50), unique=True, nullable=False)
    position = Column(String(50), nullable=True)  # hero_bottom / after_convert / page_bottom / sidebar / viewer_overlay / search_top
    ad_code = Column(Text, nullable=False)
    ad_type = Column(String(20), default="adsense")
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Folder(Base):
    __tablename__ = "folders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="folders")
    jobs = relationship("Job", back_populates="folder")
