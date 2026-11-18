"""Add Phase 5.4 Supplier & Purchase Management System tables.
Tables created: suppliers, purchase_orders, purchase_order_items, goods_receipts, goods_receipt_items, supplier_payments.
Sequences created: po_number_seq, grn_number_seq, supplier_payment_seq.

Revision ID: f62a39b81c05
Revises: e51f28b79a04
Create Date: 2026-11-13 21:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f62a39b81c05'
down_revision: Union[str, None] = 'e51f28b79a04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --------------------------------------------------------------------------
    # 1. Sequences for Concurrency-Safe Document Numbers
    # --------------------------------------------------------------------------
    op.execute("CREATE SEQUENCE IF NOT EXISTS po_number_seq START WITH 1;")
    op.execute("CREATE SEQUENCE IF NOT EXISTS grn_number_seq START WITH 1;")
    op.execute("CREATE SEQUENCE IF NOT EXISTS supplier_payment_seq START WITH 1;")

    # --------------------------------------------------------------------------
    # 2. Table: suppliers
    # --------------------------------------------------------------------------
    op.create_table(
        'suppliers',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('company_name', sa.String(length=200), nullable=False),
        sa.Column('contact_person', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('alternate_phone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=150), nullable=True),
        sa.Column('gstin', sa.String(length=20), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('pincode', sa.String(length=10), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_suppliers_company_name'), 'suppliers', ['company_name'], unique=True)
    op.create_index(op.f('ix_suppliers_phone'), 'suppliers', ['phone'], unique=False)
    op.create_index(op.f('ix_suppliers_email'), 'suppliers', ['email'], unique=False)
    op.create_index(op.f('ix_suppliers_gstin'), 'suppliers', ['gstin'], unique=False)
    op.create_index(op.f('ix_suppliers_is_active'), 'suppliers', ['is_active'], unique=False)
    op.create_index(op.f('ix_suppliers_created_at'), 'suppliers', ['created_at'], unique=False)

    # --------------------------------------------------------------------------
    # 3. Table: purchase_orders
    # --------------------------------------------------------------------------
    op.create_table(
        'purchase_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('po_number', sa.String(length=50), nullable=False),
        sa.Column('supplier_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('po_date', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expected_delivery_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='DRAFT', nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('discount_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('tax_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('grand_total', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT', 'ORDERED', 'PARTIALLY_RECEIVED', 'RECEIVED', 'CANCELLED')", name='ck_purchase_orders_status'),
        sa.CheckConstraint('subtotal >= 0', name='ck_purchase_orders_subtotal_non_negative'),
        sa.CheckConstraint('discount_amount >= 0', name='ck_purchase_orders_discount_non_negative'),
        sa.CheckConstraint('tax_amount >= 0', name='ck_purchase_orders_tax_non_negative'),
        sa.CheckConstraint('grand_total >= 0', name='ck_purchase_orders_grand_total_non_negative'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_purchase_orders_po_number'), 'purchase_orders', ['po_number'], unique=True)
    op.create_index(op.f('ix_purchase_orders_supplier_id'), 'purchase_orders', ['supplier_id'], unique=False)
    op.create_index(op.f('ix_purchase_orders_status'), 'purchase_orders', ['status'], unique=False)
    op.create_index(op.f('ix_purchase_orders_po_date'), 'purchase_orders', ['po_date'], unique=False)
    op.create_index(op.f('ix_purchase_orders_created_by_user_id'), 'purchase_orders', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_purchase_orders_created_at'), 'purchase_orders', ['created_at'], unique=False)

    # --------------------------------------------------------------------------
    # 4. Table: purchase_order_items
    # --------------------------------------------------------------------------
    op.create_table(
        'purchase_order_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('purchase_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('variant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quantity_ordered', sa.Integer(), nullable=False),
        sa.Column('quantity_received', sa.Integer(), server_default='0', nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('discount_percent', sa.Numeric(precision=5, scale=2), server_default='0.00', nullable=False),
        sa.Column('tax_percent', sa.Numeric(precision=5, scale=2), server_default='0.00', nullable=False),
        sa.Column('line_total', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('quantity_ordered > 0', name='ck_po_items_quantity_ordered_positive'),
        sa.CheckConstraint('quantity_received >= 0', name='ck_po_items_quantity_received_non_negative'),
        sa.CheckConstraint('unit_cost >= 0', name='ck_po_items_unit_cost_non_negative'),
        sa.CheckConstraint('discount_percent >= 0', name='ck_po_items_discount_percent_non_negative'),
        sa.CheckConstraint('tax_percent >= 0', name='ck_po_items_tax_percent_non_negative'),
        sa.CheckConstraint('line_total >= 0', name='ck_po_items_line_total_non_negative'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_purchase_order_items_purchase_order_id'), 'purchase_order_items', ['purchase_order_id'], unique=False)
    op.create_index(op.f('ix_purchase_order_items_product_id'), 'purchase_order_items', ['product_id'], unique=False)
    op.create_index(op.f('ix_purchase_order_items_variant_id'), 'purchase_order_items', ['variant_id'], unique=False)

    # --------------------------------------------------------------------------
    # 5. Table: goods_receipts (GRN)
    # --------------------------------------------------------------------------
    op.create_table(
        'goods_receipts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('grn_number', sa.String(length=50), nullable=False),
        sa.Column('purchase_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('supplier_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('receiving_date', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('supplier_invoice_ref', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('received_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('total_accepted_quantity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_rejected_quantity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['received_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_goods_receipts_grn_number'), 'goods_receipts', ['grn_number'], unique=True)
    op.create_index(op.f('ix_goods_receipts_purchase_order_id'), 'goods_receipts', ['purchase_order_id'], unique=False)
    op.create_index(op.f('ix_goods_receipts_supplier_id'), 'goods_receipts', ['supplier_id'], unique=False)
    op.create_index(op.f('ix_goods_receipts_received_by_user_id'), 'goods_receipts', ['received_by_user_id'], unique=False)
    op.create_index(op.f('ix_goods_receipts_receiving_date'), 'goods_receipts', ['receiving_date'], unique=False)
    op.create_index(op.f('ix_goods_receipts_created_at'), 'goods_receipts', ['created_at'], unique=False)

    # --------------------------------------------------------------------------
    # 6. Table: goods_receipt_items
    # --------------------------------------------------------------------------
    op.create_table(
        'goods_receipt_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('goods_receipt_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('purchase_order_item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('variant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quantity_received', sa.Integer(), nullable=False),
        sa.Column('quantity_accepted', sa.Integer(), server_default='0', nullable=False),
        sa.Column('quantity_rejected', sa.Integer(), server_default='0', nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('quantity_received > 0', name='ck_gr_items_qty_received_positive'),
        sa.CheckConstraint('quantity_accepted >= 0', name='ck_gr_items_qty_accepted_non_negative'),
        sa.CheckConstraint('quantity_rejected >= 0', name='ck_gr_items_qty_rejected_non_negative'),
        sa.CheckConstraint('quantity_received = quantity_accepted + quantity_rejected', name='ck_gr_items_received_sum_accepted_rejected'),
        sa.ForeignKeyConstraint(['goods_receipt_id'], ['goods_receipts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['purchase_order_item_id'], ['purchase_order_items.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_goods_receipt_items_goods_receipt_id'), 'goods_receipt_items', ['goods_receipt_id'], unique=False)
    op.create_index(op.f('ix_goods_receipt_items_purchase_order_item_id'), 'goods_receipt_items', ['purchase_order_item_id'], unique=False)
    op.create_index(op.f('ix_goods_receipt_items_product_id'), 'goods_receipt_items', ['product_id'], unique=False)
    op.create_index(op.f('ix_goods_receipt_items_variant_id'), 'goods_receipt_items', ['variant_id'], unique=False)

    # --------------------------------------------------------------------------
    # 7. Table: supplier_payments
    # --------------------------------------------------------------------------
    op.create_table(
        'supplier_payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('payment_number', sa.String(length=50), nullable=False),
        sa.Column('supplier_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('purchase_order_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('payment_date', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('payment_method', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('transaction_reference', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("payment_method IN ('CASH', 'UPI', 'BANK_TRANSFER', 'CHEQUE')", name='ck_supplier_payments_method'),
        sa.CheckConstraint("status IN ('PENDING', 'CONFIRMED', 'REJECTED')", name='ck_supplier_payments_status'),
        sa.CheckConstraint('amount > 0', name='ck_supplier_payments_amount_positive'),
        sa.ForeignKeyConstraint(['confirmed_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_supplier_payments_payment_number'), 'supplier_payments', ['payment_number'], unique=True)
    op.create_index(op.f('ix_supplier_payments_supplier_id'), 'supplier_payments', ['supplier_id'], unique=False)
    op.create_index(op.f('ix_supplier_payments_purchase_order_id'), 'supplier_payments', ['purchase_order_id'], unique=False)
    op.create_index(op.f('ix_supplier_payments_status'), 'supplier_payments', ['status'], unique=False)
    op.create_index(op.f('ix_supplier_payments_payment_date'), 'supplier_payments', ['payment_date'], unique=False)
    op.create_index(op.f('ix_supplier_payments_created_by_user_id'), 'supplier_payments', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_supplier_payments_created_at'), 'supplier_payments', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('supplier_payments')
    op.drop_table('goods_receipt_items')
    op.drop_table('goods_receipts')
    op.drop_table('purchase_order_items')
    op.drop_table('purchase_orders')
    op.drop_table('suppliers')

    op.execute("DROP SEQUENCE IF EXISTS supplier_payment_seq;")
    op.execute("DROP SEQUENCE IF EXISTS grn_number_seq;")
    op.execute("DROP SEQUENCE IF EXISTS po_number_seq;")
