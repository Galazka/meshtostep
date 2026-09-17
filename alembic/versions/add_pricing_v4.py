"""add pricing_config, discount_codes, order cost columns
Revision ID: add_pricing_v4
Revises: add_orders_03
Create Date: 2026-09-17

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision: Union[str, Sequence[str]] = "add_pricing_v4"
down_revision: Union[str, Sequence[str]] = "add_orders_03"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def _has_column(table: str, column: str) -> bool:
    insp = inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns(table)}
    return column in cols


def upgrade() -> None:
    insp = inspect(op.get_bind())

    # --- pricing_config ---
    if "pricing_config" not in insp.get_table_names():
        op.create_table(
            "pricing_config",
            sa.Column("key", sa.String(80), primary_key=True),
            sa.Column("value", sa.String(120), nullable=False),
            sa.Column("kind", sa.String(20), default="float"),
            sa.Column("created_at", sa.DateTime, default=lambda: text("now()")),
            sa.Column("updated_at", sa.DateTime, nullable=True),
        )

    # --- discount_codes ---
    if "discount_codes" not in insp.get_table_names():
        op.create_table(
            "discount_codes",
            sa.Column("code", sa.String(50), primary_key=True),
            sa.Column("discount_pln", sa.Float, default=0),
            sa.Column("discount_pct", sa.Float, default=0),
            sa.Column("is_active", sa.Boolean, default=True),
            sa.Column("uses", sa.Integer, default=0),
            sa.Column("max_uses", sa.Integer, nullable=True),
            sa.Column("expires_at", sa.DateTime, nullable=True),
            sa.Column("min_order_pln", sa.Float, nullable=True, server_default="0"),
            sa.Column("created_at", sa.DateTime, default=lambda: text("now()")),
        )

    # --- orders new columns ---
    if _has_column("orders", "status"):
        pass
    if not _has_column("orders", "discount_pln"):
        op.add_column("orders", sa.Column("discount_pln", sa.Float, nullable=True, server_default="0"))
    if not _has_column("orders", "print_parts"):
        op.add_column("orders", sa.Column("print_parts", sa.Integer, nullable=True, server_default="1"))
    if not _has_column("orders", "admin_notes"):
        op.add_column("orders", sa.Column("admin_notes", sa.Text, nullable=True))
    if not _has_column("orders", "customer_phone"):
        op.add_column("orders", sa.Column("customer_phone", sa.String(30), nullable=True))
    if not _has_column("orders", "payment_method"):
        op.add_column("orders", sa.Column("payment_method", sa.String(20), nullable=True, server_default="blik"))
    conn = op.get_bind()
    conn.exec_driver_sql("UPDATE orders SET discount_pln=0 WHERE discount_pln IS NULL")
    conn.exec_driver_sql("UPDATE orders SET print_parts=1 WHERE print_parts IS NULL")
    conn.exec_driver_sql("UPDATE orders SET admin_notes='' WHERE admin_notes IS NULL")


def downgrade() -> None:
    for col in ["admin_notes", "print_parts", "discount_pln", "payment_method", "customer_phone"]:
        if _has_column("orders", col):
            op.drop_column("orders", col)
    if inspect(op.get_bind()).has_table("discount_codes"):
        op.drop_table("discount_codes")
    if inspect(op.get_bind()).has_table("pricing_config"):
        op.drop_table("pricing_config")
