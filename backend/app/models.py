"""Database models: users, jobs, shares, comments, geo, ads. — 3dfile.link"""
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
    quota_limit_bytes = Column(Integer, default=100 * 1024 * 1024, nullable=False)  # 100 MB

    jobs = relationship("Job", back_populates="user")
    folders = relationship("Folder", back_populates="user", cascade="all, delete-orphan")
    shares = relationship("ShareLink", back_populates="user")
    geo_logs = relationship("GeoLog", back_populates="user")
    comments = relationship("Comment", back_populates="user")


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
    dims_mm = Column(String(60), nullable=True)  # "X x Y x Z mm"
    volume_cm3 = Column(Float, nullable=True)  # trimesh volume in cm³
    result_size_bytes = Column(Integer)
    result_step_path = Column(String(512))
    result_stl_path = Column(String(512))
    error_msg = Column(Text)
    processing_time_s = Column(Float)
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


class JobRating(Base):
    """Star rating 1-5 per user per job — one vote per user, update allowed."""
    __tablename__ = "job_ratings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stars = Column(Integer, nullable=False)  # 1-5
    created_at = Column(DateTime, default=datetime.utcnow)


class UserLike(Base):
    """One like per user per job — toggleable."""
    __tablename__ = "user_likes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


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
