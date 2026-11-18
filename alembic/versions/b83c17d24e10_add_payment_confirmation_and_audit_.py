"""Add payment confirmation, audit, and rejection fields.

Revision ID: b83c17d24e10
Revises: 947a01c804f1
Create Date: 2026-11-11 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b83c17d24e10'
down_revision: Union[str, None] = '947a01c804f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns to payments table
    op.add_column('payments', sa.Column('confirmed_by_user_id', sa.UUID(), nullable=True))
    op.add_column('payments', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payments', sa.Column('rejection_reason', sa.Text(), nullable=True))
    op.add_column(
        'payments',
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 2. Add foreign key and index for confirmed_by_user_id
    op.create_foreign_key(
        op.f('fk_payments_confirmed_by_user_id_users'),
        'payments',
        'users',
        ['confirmed_by_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        op.f('ix_payments_confirmed_by_user_id'),
        'payments',
        ['confirmed_by_user_id'],
        unique=False,
    )

    # 3. Update payment_status check constraint to include REJECTED
    op.execute("ALTER TABLE payments DROP CONSTRAINT IF EXISTS ck_payments_ck_payments_payment_status;")
    op.execute(
        "ALTER TABLE payments ADD CONSTRAINT ck_payments_ck_payments_payment_status "
        "CHECK (payment_status IN ('PENDING', 'CONFIRMED', 'FAILED', 'REJECTED', 'REFUNDED'));"
    )

    # 4. Partial unique index on transaction_reference for active payments (prevent duplicate UTR)
    op.create_index(
        'uq_payments_active_transaction_ref',
        'payments',
        ['transaction_reference'],
        unique=True,
        postgresql_where=sa.text("transaction_reference IS NOT NULL AND transaction_reference <> '' AND payment_status IN ('CONFIRMED', 'PENDING')"),
    )


def downgrade() -> None:
    # 1. Drop partial unique index on transaction_reference
    op.drop_index('uq_payments_active_transaction_ref', table_name='payments')

    # 2. Restore previous payment_status check constraint
    op.execute("ALTER TABLE payments DROP CONSTRAINT IF EXISTS ck_payments_ck_payments_payment_status;")
    op.execute(
        "ALTER TABLE payments ADD CONSTRAINT ck_payments_ck_payments_payment_status "
        "CHECK (payment_status IN ('PENDING', 'CONFIRMED', 'FAILED', 'REFUNDED'));"
    )

    # 3. Drop foreign key and index
    op.drop_index(op.f('ix_payments_confirmed_by_user_id'), table_name='payments')
    op.drop_constraint(op.f('fk_payments_confirmed_by_user_id_users'), 'payments', type_='foreignkey')

    # 4. Drop added columns
    op.drop_column('payments', 'updated_at')
    op.drop_column('payments', 'rejection_reason')
    op.drop_column('payments', 'confirmed_at')
    op.drop_column('payments', 'confirmed_by_user_id')
