"""Add Phase 4.6 expense fields, daily cash registers, and cash movements.

Revision ID: d38f1902a7b1
Revises: c74e8910d52b
Create Date: 2026-11-11 16:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd38f1902a7b1'
down_revision: Union[str, None] = 'c74e8910d52b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --------------------------------------------------------------------------
    # 1. Update expenses table
    # --------------------------------------------------------------------------
    op.add_column('expenses', sa.Column('payment_method', sa.String(length=20), nullable=False, server_default='CASH'))
    op.add_column('expenses', sa.Column('reference_number', sa.String(length=100), nullable=True))
    op.add_column('expenses', sa.Column('receipt_url', sa.String(length=1024), nullable=True))
    op.add_column('expenses', sa.Column('is_voided', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('expenses', sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('expenses', sa.Column('voided_by_user_id', sa.UUID(), nullable=True))
    op.add_column('expenses', sa.Column('void_reason', sa.Text(), nullable=True))
    op.add_column('expenses', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')))

    op.create_foreign_key(
        'fk_expenses_voided_by_user_id_users',
        'expenses',
        'users',
        ['voided_by_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_expenses_payment_method'), 'expenses', ['payment_method'], unique=False)
    op.create_index(op.f('ix_expenses_is_voided'), 'expenses', ['is_voided'], unique=False)
    op.create_index(op.f('ix_expenses_reference_number'), 'expenses', ['reference_number'], unique=False)
    op.create_index(op.f('ix_expenses_voided_by_user_id'), 'expenses', ['voided_by_user_id'], unique=False)

    op.execute(
        """
        ALTER TABLE expenses ADD CONSTRAINT ck_expenses_payment_method
        CHECK (payment_method IN ('CASH', 'UPI', 'CARD'));
        """
    )
    op.execute(
        """
        ALTER TABLE expenses ADD CONSTRAINT ck_expenses_void_consistency
        CHECK (
            (is_voided = TRUE AND voided_at IS NOT NULL AND void_reason IS NOT NULL)
            OR
            (is_voided = FALSE AND voided_at IS NULL AND void_reason IS NULL)
        );
        """
    )

    # --------------------------------------------------------------------------
    # 2. Create daily_cash_registers table
    # --------------------------------------------------------------------------
    op.create_table(
        'daily_cash_registers',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('business_date', sa.Date(), nullable=False),
        sa.Column('opening_cash', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('opening_notes', sa.Text(), nullable=True),
        sa.Column('opened_by_user_id', sa.UUID(), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('cash_sales', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('cash_expenses', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('other_cash_inflow', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('other_cash_outflow', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('expected_closing_cash', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('actual_closing_cash', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('cash_difference', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('closing_notes', sa.Text(), nullable=True),
        sa.Column('closed_by_user_id', sa.UUID(), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_closed', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('is_corrected', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('correction_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['closed_by_user_id'], ['users.id'], name=op.f('fk_daily_cash_registers_closed_by_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['opened_by_user_id'], ['users.id'], name=op.f('fk_daily_cash_registers_opened_by_user_id_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_daily_cash_registers')),
        sa.UniqueConstraint('business_date', name=op.f('uq_daily_cash_registers_business_date')),
        sa.CheckConstraint('opening_cash >= 0', name='ck_cash_registers_opening_non_negative'),
        sa.CheckConstraint('other_cash_inflow >= 0', name='ck_cash_registers_inflow_non_negative'),
        sa.CheckConstraint('other_cash_outflow >= 0', name='ck_cash_registers_outflow_non_negative'),
        sa.CheckConstraint('actual_closing_cash IS NULL OR actual_closing_cash >= 0', name='ck_cash_registers_closing_non_negative'),
        sa.CheckConstraint(
            "((is_closed = TRUE AND closed_at IS NOT NULL AND closed_by_user_id IS NOT NULL AND actual_closing_cash IS NOT NULL) OR (is_closed = FALSE AND closed_at IS NULL AND actual_closing_cash IS NULL))",
            name='ck_cash_registers_closing_consistency',
        ),
    )
    op.create_index(op.f('ix_daily_cash_registers_business_date'), 'daily_cash_registers', ['business_date'], unique=True)
    op.create_index(op.f('ix_daily_cash_registers_is_closed'), 'daily_cash_registers', ['is_closed'], unique=False)
    op.create_index(op.f('ix_daily_cash_registers_opened_by_user_id'), 'daily_cash_registers', ['opened_by_user_id'], unique=False)
    op.create_index(op.f('ix_daily_cash_registers_closed_by_user_id'), 'daily_cash_registers', ['closed_by_user_id'], unique=False)

    # --------------------------------------------------------------------------
    # 3. Create cash_movements table
    # --------------------------------------------------------------------------
    op.create_table(
        'cash_movements',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('register_id', sa.UUID(), nullable=False),
        sa.Column('movement_type', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('created_by_user_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('fk_cash_movements_created_by_user_id_users'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['register_id'], ['daily_cash_registers.id'], name=op.f('fk_cash_movements_register_id_daily_cash_registers'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_cash_movements')),
        sa.CheckConstraint('amount > 0', name='ck_cash_movements_amount_positive'),
        sa.CheckConstraint("movement_type IN ('INFLOW', 'OUTFLOW')", name='ck_cash_movements_type'),
    )
    op.create_index(op.f('ix_cash_movements_register_id'), 'cash_movements', ['register_id'], unique=False)
    op.create_index(op.f('ix_cash_movements_created_by_user_id'), 'cash_movements', ['created_by_user_id'], unique=False)


def downgrade() -> None:
    # 1. Drop cash_movements
    op.drop_index(op.f('ix_cash_movements_created_by_user_id'), table_name='cash_movements')
    op.drop_index(op.f('ix_cash_movements_register_id'), table_name='cash_movements')
    op.drop_table('cash_movements')

    # 2. Drop daily_cash_registers
    op.drop_index(op.f('ix_daily_cash_registers_closed_by_user_id'), table_name='daily_cash_registers')
    op.drop_index(op.f('ix_daily_cash_registers_opened_by_user_id'), table_name='daily_cash_registers')
    op.drop_index(op.f('ix_daily_cash_registers_is_closed'), table_name='daily_cash_registers')
    op.drop_index(op.f('ix_daily_cash_registers_business_date'), table_name='daily_cash_registers')
    op.drop_table('daily_cash_registers')

    # 3. Revert expenses table
    op.execute("ALTER TABLE expenses DROP CONSTRAINT IF EXISTS ck_expenses_void_consistency;")
    op.execute("ALTER TABLE expenses DROP CONSTRAINT IF EXISTS ck_expenses_payment_method;")
    op.drop_index(op.f('ix_expenses_voided_by_user_id'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_reference_number'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_is_voided'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_payment_method'), table_name='expenses')
    op.drop_constraint('fk_expenses_voided_by_user_id_users', 'expenses', type_='foreignkey')
    op.drop_column('expenses', 'updated_at')
    op.drop_column('expenses', 'void_reason')
    op.drop_column('expenses', 'voided_by_user_id')
    op.drop_column('expenses', 'voided_at')
    op.drop_column('expenses', 'is_voided')
    op.drop_column('expenses', 'receipt_url')
    op.drop_column('expenses', 'reference_number')
    op.drop_column('expenses', 'payment_method')
