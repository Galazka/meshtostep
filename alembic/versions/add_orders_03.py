"""add orders table + printer fields + user role/rating

Revision ID: add_orders_03
Revises: add_print_marketplace_02
Create Date: 2026-09-16 19:40:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers
revision: Union[str, Sequence[str]] = "add_orders_03"
down_revision: Union[str, Sequence[str]] = "add_print_marketplace_02"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def _has_column(table: str, column: str) -> bool:
    insp = inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns(table)}
    return column in cols


def upgrade() -> None:
    # --- User fields ---
    u_cols = {c["name"] for c in inspect(op.get_bind()).get_columns("users")}
    if "role" not in u_cols:
        op.add_column("users", sa.Column("role", sa.String(20), nullable=True))
    if "has_printer" not in u_cols:
        op.add_column("users", sa.Column("has_printer", sa.Boolean, nullable=True))
    if "rating_count" not in u_cols:
        op.add_column("users", sa.Column("rating_count", sa.Integer, nullable=True))
    if "rating_avg" not in u_cols:
        op.add_column("users", sa.Column("rating_avg", sa.Float, nullable=True))
    conn = op.get_bind()
    conn.exec_driver_sql("UPDATE users SET role='buyer' WHERE role IS NULL")
    conn.exec_driver_sql("UPDATE users SET has_printer=False WHERE has_printer IS NULL")
    conn.exec_driver_sql("UPDATE users SET rating_count=0 WHERE rating_count IS NULL")
    conn.exec_driver_sql("UPDATE users SET rating_avg=0.0 WHERE rating_avg IS NULL")

    # --- Print requests: auction_end ---
    if _has_column("print_requests", "deadline") and not _has_column("print_requests", "auction_end"):
        op.add_column("print_requests", sa.Column("auction_end", sa.DateTime, nullable=True))

    # --- Print offers: shipping / rating ---
    if not _has_column("print_offers", "shipping_method"):
        op.add_column("print_offers", sa.Column("shipping_method", sa.String(20), nullable=True))
        conn.exec_driver_sql("UPDATE print_offers SET shipping_method='pickup' WHERE shipping_method IS NULL")
    if not _has_column("print_offers", "rating"):
        op.add_column("print_offers", sa.Column("rating", sa.Float, nullable=True))
    if not _has_column("print_offers", "rating_count"):
        op.add_column("print_offers", sa.Column("rating_count", sa.Integer, nullable=True, server_default="0"))
        conn.exec_driver_sql("UPDATE print_offers SET rating_count=0 WHERE rating_count IS NULL")

    # --- Orders table (new) ---
    insp = inspect(op.get_bind())
    if "orders" not in insp.get_table_names():
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id"), nullable=True),
            sa.Column("job_uuid", sa.String(32), nullable=True),
            sa.Column("customer_name", sa.String(100), nullable=False),
            sa.Column("customer_email", sa.String(255), nullable=False),
            sa.Column("customer_phone", sa.String(30), nullable=True),
            sa.Column("customer_address", sa.String(500), nullable=True),
            sa.Column("customer_city", sa.String(100), nullable=True),
            sa.Column("customer_postal", sa.String(20), nullable=True),
            sa.Column("customer_country", sa.String(30), nullable=True),
            sa.Column("material", sa.String(30), nullable=True),
            sa.Column("color", sa.String(20), nullable=True),
            sa.Column("quantity", sa.Integer, nullable=True),
            sa.Column("shipping_method", sa.String(20), nullable=True),
            sa.Column("shipping_region", sa.String(20), nullable=True),
            sa.Column("estimated_hours", sa.Float, nullable=True),
            sa.Column("volume_cm3", sa.Float, nullable=True),
            sa.Column("filament_grams", sa.Float, nullable=True),
            sa.Column("printing_hours", sa.Float, nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("payment_method", sa.String(20), nullable=True),
            sa.Column("subtotal", sa.Float, nullable=True),
            sa.Column("margin_pln", sa.Float, nullable=True),
            sa.Column("shipping_cost", sa.Float, nullable=True),
            sa.Column("total", sa.Float, nullable=True),
            sa.Column("status", sa.String(20), nullable=True),
            sa.Column("is_paid", sa.Boolean, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=True),
            sa.Column("updated_at", sa.DateTime, nullable=True),
        )


def downgrade() -> None:
    op.drop_table("orders")
    for col in ["rating_count", "rating", "shipping_method"]:
        if _has_column("print_offers", col):
            op.drop_column("print_offers", col)
    if _has_column("print_requests", "auction_end"):
        op.drop_column("print_requests", "auction_end")
    for col in ["rating_avg", "rating_count", "has_printer", "role"]:
        if _has_column("users", col):
            op.drop_column("users", col)
