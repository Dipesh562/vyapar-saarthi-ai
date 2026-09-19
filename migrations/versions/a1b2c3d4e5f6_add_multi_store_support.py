"""Add multi-store support: owner_stores table and new store fields

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-09-19

Changes:
  - Creates owner_stores junction table (owner_id, store_id, is_primary, added_at)
  - Adds stores.phone column (nullable)
  - Adds stores.gstin column (nullable)
  - Adds stores.is_active column (default True)
  - Backfills owner_stores: inserts one row per existing owner (is_primary=True)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------------------------------------------------------
    # 1. Add new columns to stores table
    # -------------------------------------------------------------------------
    with op.batch_alter_table('stores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phone', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('gstin', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))

    # -------------------------------------------------------------------------
    # 2. Create owner_stores junction table
    # -------------------------------------------------------------------------
    op.create_table(
        'owner_stores',
        sa.Column(
            'id',
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True
        ),
        sa.Column(
            'owner_id',
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey('users.user_id', ondelete='CASCADE'),
            nullable=False
        ),
        sa.Column(
            'store_id',
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey('stores.store_id', ondelete='CASCADE'),
            nullable=False
        ),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('added_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('owner_id', 'store_id', name='uq_owner_stores'),
    )
    op.create_index('idx_owner_stores_owner', 'owner_stores', ['owner_id'])

    # -------------------------------------------------------------------------
    # 3. Backfill: for every existing owner user, create a primary OwnerStore row
    # -------------------------------------------------------------------------
    conn = op.get_bind()
    owners = conn.execute(
        text("SELECT user_id, store_id FROM users WHERE role = 'owner'")
    ).fetchall()

    for owner in owners:
        conn.execute(
            text(
                "INSERT INTO owner_stores (owner_id, store_id, is_primary, added_at) "
                "VALUES (:owner_id, :store_id, 1, CURRENT_TIMESTAMP)"
            ),
            {"owner_id": owner[0], "store_id": owner[1]}
        )


def downgrade():
    op.drop_index('idx_owner_stores_owner', table_name='owner_stores')
    op.drop_table('owner_stores')

    with op.batch_alter_table('stores', schema=None) as batch_op:
        batch_op.drop_column('is_active')
        batch_op.drop_column('gstin')
        batch_op.drop_column('phone')
