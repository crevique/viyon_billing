"""Add bill cancellation fields and CANCELLATION stock movement type.

Revision ID: c74e8910d52b
Revises: b83c17d24e10
Create Date: 2026-11-11 15:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c74e8910d52b'
down_revision: Union[str, None] = 'b83c17d24e10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add cancellation metadata columns to bills table
    op.add_column('bills', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bills', sa.Column('cancelled_by_user_id', sa.UUID(), nullable=True))
    op.add_column('bills', sa.Column('cancellation_reason', sa.Text(), nullable=True))

    # 2. Add foreign key and index for cancelled_by_user_id
    op.create_foreign_key(
        op.f('fk_bills_cancelled_by_user_id_users'),
        'bills',
        'users',
        ['cancelled_by_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        op.f('ix_bills_cancelled_by_user_id'),
        'bills',
        ['cancelled_by_user_id'],
        unique=False,
    )

    # 3. Add cancellation consistency check constraint
    op.execute(
        """
        ALTER TABLE bills ADD CONSTRAINT ck_bills_cancellation_consistency CHECK (
            (bill_status = 'CANCELLED' AND cancelled_at IS NOT NULL AND cancelled_by_user_id IS NOT NULL AND cancellation_reason IS NOT NULL)
            OR
            (bill_status <> 'CANCELLED' AND cancelled_at IS NULL AND cancelled_by_user_id IS NULL AND cancellation_reason IS NULL)
        );
        """
    )

    # 4. Update stock_movements movement_type constraint to include CANCELLATION
    op.execute("ALTER TABLE stock_movements DROP CONSTRAINT IF EXISTS ck_stock_movements_ck_stock_movements_movement_type;")
    op.execute(
        """
        ALTER TABLE stock_movements ADD CONSTRAINT ck_stock_movements_ck_stock_movements_movement_type
        CHECK (movement_type IN ('PURCHASE', 'SALE', 'RETURN', 'ADJUSTMENT', 'CANCELLATION'));
        """
    )


def downgrade() -> None:
    # 1. Revert stock_movements constraint
    op.execute("ALTER TABLE stock_movements DROP CONSTRAINT IF EXISTS ck_stock_movements_ck_stock_movements_movement_type;")
    op.execute(
        """
        ALTER TABLE stock_movements ADD CONSTRAINT ck_stock_movements_ck_stock_movements_movement_type
        CHECK (movement_type IN ('PURCHASE', 'SALE', 'RETURN', 'ADJUSTMENT'));
        """
    )

    # 2. Drop cancellation consistency constraint
    op.execute("ALTER TABLE bills DROP CONSTRAINT IF EXISTS ck_bills_cancellation_consistency;")

    # 3. Drop index and foreign key
    op.drop_index(op.f('ix_bills_cancelled_by_user_id'), table_name='bills')
    op.drop_constraint(op.f('fk_bills_cancelled_by_user_id_users'), 'bills', type_='foreignkey')

    # 4. Drop columns
    op.drop_column('bills', 'cancellation_reason')
    op.drop_column('bills', 'cancelled_by_user_id')
    op.drop_column('bills', 'cancelled_at')
