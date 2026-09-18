"""Database models: users, jobs, shares, comments, geo, ads. — 3dfile.link"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
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
    token_version = Column(Integer, default=0)  # bump = kill all sessions
    role = Column(String(20), default="buyer")  # buyer | printer | both
    has_printer = Column(Boolean, default=False)
    rating_count = Column(Integer, default=0)
    rating_avg = Column(Float, default=0.0)
    registered_ip = Column(String(64), nullable=True)
    register_user_agent = Column(String(512), nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(512), nullable=True)
    quota_limit_bytes = Column(Integer, default=100 * 1024 * 1024, nullable=False)  # 100 MB
    bonus_mb = Column(Integer, default=0)  # bonus MB earned from print orders
    # — zapisane dane do wysyłki druku (profil klienta, auto-fill w zamówieniach) —
    ship_full_name = Column(String(100), nullable=True)
    ship_phone = Column(String(30), nullable=True)
    ship_address = Column(String(500), nullable=True)
    ship_city = Column(String(100), nullable=True)
    ship_postal = Column(String(20), nullable=True)
    ship_country = Column(String(30), default="PL")

    jobs = relationship("Job", back_populates="user")
    folders = relationship("Folder", back_populates="user", cascade="all, delete-orphan")
    shares = relationship("ShareLink", back_populates="user")
    geo_logs = relationship("GeoLog", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    print_requests = relationship("PrintRequest", back_populates="user")


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
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_userlike_user_job"),)


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


class PrintRequest(Base):
    """Print job posting: buyer wants something printed. No money handled (lead board)."""
    __tablename__ = "print_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)  # optional attached model
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    material = Column(String(30), default="PLA")
    quantity = Column(Integer, default=1)
    city = Column(String(100), nullable=True)
    budget_pln = Column(Float, nullable=True)
    deadline = Column(DateTime, nullable=True)
    auction_end = Column(DateTime, nullable=True)
    status = Column(String(20), default="open")
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="print_requests")
    offers = relationship("PrintOffer", back_populates="request", cascade="all, delete-orphan")


class PrintOffer(Base):
    """Printer's offer on a request. Contact revealed on accept."""
    __tablename__ = "print_offers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("print_requests.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    price_pln = Column(Float, nullable=False)
    days = Column(Integer, nullable=True)
    message = Column(Text, nullable=True)
    shipping_method = Column(String(20), default="pickup")
    rating = Column(Float, nullable=True)
    rating_count = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending / accepted / rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    request = relationship("PrintRequest", back_populates="offers")
    printer = relationship("User", foreign_keys=[user_id])


class JobReview(Base):
    """Review left by request owner for a printer after job completion."""
    __tablename__ = "job_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    offer_id = Column(Integer, ForeignKey("print_offers.id"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1-5
    text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Order(Base):
    """Print-on-demand order: customer orders a print from Tom's shop."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    job_uuid = Column(String(64), nullable=True)
    customer_name = Column(String(100), nullable=False)
    customer_email = Column(String(255), nullable=False)
    customer_phone = Column(String(30), nullable=True)
    customer_address = Column(String(500), nullable=True)
    customer_city = Column(String(100), nullable=True)
    customer_postal = Column(String(20), nullable=True)
    customer_country = Column(String(30), default="PL")
    material = Column(String(30), default="PLA")
    color = Column(String(20), default="natural")
    quantity = Column(Integer, default=1)
    shipping_method = Column(String(20), default="standard")
    shipping_region = Column(String(20), default="PL")
    estimated_hours = Column(Float, default=2.0)
    volume_cm3 = Column(Float, nullable=True)
    filament_grams = Column(Float, nullable=True)
    filament_cost = Column(Float, default=0.0)  # koszt samego filamentu (PLN)
    electricity_cost = Column(Float, default=0.0)  # koszt prądu (PLN)
    color_premium = Column(Float, default=0.0)  # premium za kolor (PLN)
    printing_hours = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    payment_method = Column(String(20), default="blik")
    subtotal = Column(Float, default=0.0)  # filament + electricity + color premium (internal cost)
    margin_pln = Column(Float, default=0.0)  # Tom's markup (hidden)
    shipping_cost = Column(Float, default=0.0)  # shown to customer
    discount_pln = Column(Float, default=0.0)  # coupon / global discount (visible as line)
    total = Column(Float, default=0.0)  # = subtotal + margin + shipping - discount
    print_parts = Column(Integer, default=1)  # how many 25x25mm parts model was split into
    currency = Column(String(10), default="PLN")  # PLN, USD, EUR
    exchange_rate = Column(Float, default=1.0)  # PLN per unit of currency (e.g., 4.20 for USD)
    status = Column(String(20), default="nowy")
    is_paid = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    user = relationship("User", foreign_keys=[user_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """One line of a print order - each uploaded model is a separate item."""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, nullable=True)
    job_uuid = Column(String(64), nullable=True)
    model_name = Column(String(255), nullable=True)
    material = Column(String(30), default="PLA")
    color = Column(String(20), default="natural")
    quantity = Column(Integer, default=1)
    volume_cm3 = Column(Float, nullable=True)
    dims_mm = Column(String(80), nullable=True)
    filament_grams = Column(Float, default=0.0)
    filament_cost = Column(Float, default=0.0)
    electricity_cost = Column(Float, default=0.0)
    color_premium = Column(Float, default=0.0)
    subtotal = Column(Float, default=0.0)
    margin_pln = Column(Float, default=0.0)
    print_parts = Column(Integer, default=1)
    order = relationship("Order", back_populates="items")




class PricingConfig(Base):
    """Dynamic pricing config — editable from admin panel. One row per key."""
    __tablename__ = "pricing_config"

    key = Column(String(80), primary_key=True)  # material:PLA, shipping:PL, margin_percent, kwh, watts, max_part_25mm etc.
    value = Column(String(120), nullable=False)
    kind = Column(String(20), default="float")  # float / string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)


# Default config seed for PricingConfig (used by _migrate_columns fallback)
PRICING_SEED = {
    "margin_percent": "68",
    "kwh_pln": "1.15",
    "watts": "150",
    "max_part_area_mm2": "625",      # 25×25 mm bed — larger models split into parts
    "density_default_g_cm3": "1.24",
    "shipping_PL": "15",
    "shipping_EU": "35",
    "shipping_GLOBAL": "55",
    "shipping_express_PL": "25",
    "shipping_express_EU": "55",
    "shipping_express_GLOBAL": "85",
    "material:PLA": "79",
    "material:PLA HT": "120",
    "material:PLA CF": "199",
    "material:PLA Matte": "100",
    "material:PLA Silk": "110",
    "material:PLA Glow": "130",
    "material:BAMBU PLA Basic": "99",
    "material:BAMBU PLA Matte": "109",
    "material:PETG": "95",
    "material:PETG HF": "129",
    "material:PETG FR": "150",
    "material:BAMBU PETG HF": "129",
    "material:ABS": "89",
    "material:ASA": "159",
    "material:ASA CF": "299",
    "material:BAMBU ASA": "159",
    "material:PA12 CF": "349",
    "material:BAMBU PA12-CF": "349",
    "material:PA12": "180",
    "material:TPU": "130",
    "material:TPU 75D": "150",
    "material:PCTG": "140",
    "color:black": "0",
    "color:white": "0",
    "color:blue": "5",
    "color:red": "5",
    "color:green": "5",
    "color:yellow": "5",
    "color:silver": "10",
    "color:brass": "25",
}
