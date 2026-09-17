"""add print marketplace + auction + reviews

Revision ID: add_print_marketplace_02
Revises:
Create Date: 2026-09-16 19:40:00

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy as _sa


# revision identifiers
revision = 'add_print_marketplace_02'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    _conn = op.get_bind()
    insp = _sa.inspect(_conn)

    _u_cols = {c['name'] for c in insp.get_columns('users')}
    _pr_cols = {c['name'] for c in insp.get_columns('print_requests')}
    _po_cols = {c['name'] for c in insp.get_columns('print_offers')}
    _pr_exists = 'print_requests' in insp.get_table_names()
    _po_exists = 'print_offers' in insp.get_table_names()
    _jr_exists = 'job_reviews' in insp.get_table_names()

    # User fields
    if 'role' not in _u_cols:
        op.add_column('users', sa.Column('role', sa.String(20), nullable=True))
    if 'has_printer' not in _u_cols:
        op.add_column('users', sa.Column('has_printer', sa.Boolean, nullable=True))
    if 'rating_count' not in _u_cols:
        op.add_column('users', sa.Column('rating_count', sa.Integer, nullable=True))
    if 'rating_avg' not in _u_cols:
        op.add_column('users', sa.Column('rating_avg', sa.Float, nullable=True))
    _conn.exec_driver_sql("UPDATE users SET role='buyer' WHERE role IS NULL")
    _conn.exec_driver_sql("UPDATE users SET has_printer=False WHERE has_printer IS NULL")
    _conn.exec_driver_sql("UPDATE users SET rating_count=0 WHERE rating_count IS NULL")
    _conn.exec_driver_sql("UPDATE users SET rating_avg=0.0 WHERE rating_avg IS NULL")

    # Print requests
    if _pr_exists and 'auction_end' not in _pr_cols:
        op.add_column('print_requests', sa.Column('auction_end', sa.DateTime, nullable=True))

    # Print offers
    if _po_exists:
        if 'shipping_method' not in _po_cols:
            op.add_column('print_offers', sa.Column('shipping_method', sa.String(20), nullable=True))
        if 'rating' not in _po_cols:
            op.add_column('print_offers', sa.Column('rating', sa.Float, nullable=True))
        if 'rating_count' not in _po_cols:
            op.add_column('print_offers', sa.Column('rating_count', sa.Integer, nullable=True))
        _conn.exec_driver_sql("UPDATE print_offers SET shipping_method='pickup' WHERE shipping_method IS NULL")
        _conn.exec_driver_sql("UPDATE print_offers SET rating_count=0 WHERE rating_count IS NULL")

    # Job reviews
    if not _jr_exists:
        op.create_table(
            'job_reviews',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('offer_id', sa.Integer, sa.ForeignKey('print_offers.id'), nullable=False),
            sa.Column('reviewer_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
            sa.Column('rating', sa.Integer, nullable=False),
            sa.Column('text', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table('job_reviews')
    for col in ['rating_count', 'rating', 'shipping_method']:
        op.drop_column('print_offers', col)
    op.drop_column('print_requests', 'auction_end')
    for col in ['rating_avg', 'rating_count', 'has_printer', 'role']:
        op.drop_column('users', col)
