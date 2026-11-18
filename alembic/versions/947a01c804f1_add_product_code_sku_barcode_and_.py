"""add_product_code_sku_barcode_and_product_identifiers

Revision ID: 947a01c804f1
Revises: 002e11099e78
Create Date: 2026-11-11 14:25:45.309687

"""
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '947a01c804f1'
down_revision: Union[str, Sequence[str], None] = '002e11099e78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with product_code, sku, barcode, and shared product_identifiers registry."""
    # --------------------------------------------------------------------------
    # 1. Add nullable columns to products table
    # --------------------------------------------------------------------------
    op.add_column('products', sa.Column('product_code', sa.String(length=50), nullable=True))
    op.add_column('products', sa.Column('sku', sa.String(length=100), nullable=True))
    op.add_column('products', sa.Column('barcode', sa.String(length=100), nullable=True))

    # Approved indexes on products
    op.create_index(op.f('ix_products_product_code'), 'products', ['product_code'], unique=True)
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=False)
    op.create_index(op.f('ix_products_barcode'), 'products', ['barcode'], unique=False)

    # --------------------------------------------------------------------------
    # 2. Create product_identifiers table (Shared Central Registry)
    # --------------------------------------------------------------------------
    op.create_table(
        'product_identifiers',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('identifier_type', sa.String(length=20), nullable=False),
        sa.Column('identifier_value', sa.String(length=100), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=True),
        sa.Column('variant_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("identifier_type IN ('SKU', 'BARCODE')", name=op.f('ck_product_identifiers_ck_product_identifiers_type')),
        sa.CheckConstraint('length(btrim(identifier_value)) > 0', name=op.f('ck_product_identifiers_ck_product_identifiers_value_non_empty')),
        sa.CheckConstraint(
            '((product_id IS NOT NULL AND variant_id IS NULL) OR (product_id IS NULL AND variant_id IS NOT NULL))',
            name=op.f('ck_product_identifiers_ck_product_identifiers_single_owner'),
        ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_product_identifiers_product_id_products'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], name=op.f('fk_product_identifiers_variant_id_product_variants'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_product_identifiers')),
        sa.UniqueConstraint('identifier_type', 'identifier_value', name=op.f('uq_product_identifiers_identifier_type_identifier_value')),
    )

    op.create_index(op.f('ix_product_identifiers_product_id'), 'product_identifiers', ['product_id'], unique=False)
    op.create_index(op.f('ix_product_identifiers_variant_id'), 'product_identifiers', ['variant_id'], unique=False)
    op.create_index('ix_product_identifiers_type_val', 'product_identifiers', ['identifier_type', 'identifier_value'], unique=False)

    # --------------------------------------------------------------------------
    # 3. PostgreSQL Functions & Triggers for Normalization & Registry Sync
    # --------------------------------------------------------------------------
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Normalization Trigger Function (BEFORE INSERT/UPDATE)
        op.execute("""
        CREATE OR REPLACE FUNCTION normalize_product_identifiers()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.sku := NULLIF(UPPER(BTRIM(NEW.sku)), '');
            NEW.barcode := NULLIF(UPPER(BTRIM(NEW.barcode)), '');
            IF TG_TABLE_NAME = 'products' THEN
                NEW.product_code := NULLIF(UPPER(BTRIM(NEW.product_code)), '');
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_normalize_products
        BEFORE INSERT OR UPDATE OF sku, barcode, product_code ON products
        FOR EACH ROW EXECUTE FUNCTION normalize_product_identifiers();
        """)

        op.execute("""
        CREATE TRIGGER trg_normalize_variants
        BEFORE INSERT OR UPDATE OF sku, barcode ON product_variants
        FOR EACH ROW EXECUTE FUNCTION normalize_product_identifiers();
        """)

        # Products Registry Synchronization (AFTER INSERT/UPDATE)
        op.execute("""
        CREATE OR REPLACE FUNCTION sync_products_identifiers()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.sku IS NOT NULL THEN
                    INSERT INTO product_identifiers (identifier_type, identifier_value, product_id, variant_id)
                    VALUES ('SKU', NEW.sku, NEW.id, NULL);
                END IF;
                IF NEW.barcode IS NOT NULL THEN
                    INSERT INTO product_identifiers (identifier_type, identifier_value, product_id, variant_id)
                    VALUES ('BARCODE', NEW.barcode, NEW.id, NULL);
                END IF;

            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.sku IS DISTINCT FROM NEW.sku THEN
                    IF OLD.sku IS NOT NULL THEN
                        DELETE FROM product_identifiers
                        WHERE product_id = NEW.id AND identifier_type = 'SKU';
                    END IF;
                    IF NEW.sku IS NOT NULL THEN
                        INSERT INTO product_identifiers (identifier_type, identifier_value, product_id, variant_id)
                        VALUES ('SKU', NEW.sku, NEW.id, NULL);
                    END IF;
                END IF;

                IF OLD.barcode IS DISTINCT FROM NEW.barcode THEN
                    IF OLD.barcode IS NOT NULL THEN
                        DELETE FROM product_identifiers
                        WHERE product_id = NEW.id AND identifier_type = 'BARCODE';
                    END IF;
                    IF NEW.barcode IS NOT NULL THEN
                        INSERT INTO product_identifiers (identifier_type, identifier_value, product_id, variant_id)
                        VALUES ('BARCODE', NEW.barcode, NEW.id, NULL);
                    END IF;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_sync_products
        AFTER INSERT OR UPDATE OF sku, barcode ON products
        FOR EACH ROW EXECUTE FUNCTION sync_products_identifiers();
        """)

        # Variants Registry Synchronization (AFTER INSERT/UPDATE)
        op.execute("""
        CREATE OR REPLACE FUNCTION sync_variants_identifiers()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.sku IS NOT NULL THEN
                    INSERT INTO product_identifiers (identifier_type, identifier_value, product_id, variant_id)
                    VALUES ('SKU', NEW.sku, NULL, NEW.id);
                END IF;
                IF NEW.barcode IS NOT NULL THEN
                    INSERT INTO product_identifiers (identifier_type, identifier_value, product_id, variant_id)
                    VALUES ('BARCODE', NEW.barcode, NULL, NEW.id);
                END IF;

            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.sku IS DISTINCT FROM NEW.sku THEN
                    IF OLD.sku IS NOT NULL THEN
                        DELETE FROM product_identifiers
                        WHERE variant_id = NEW.id AND identifier_type = 'SKU';
                    END IF;
                    IF NEW.sku IS NOT NULL THEN
                        INSERT INTO product_identifiers (identifier_type, identifier_value, product_id, variant_id)
                        VALUES ('SKU', NEW.sku, NULL, NEW.id);
                    END IF;
                END IF;

                IF OLD.barcode IS DISTINCT FROM NEW.barcode THEN
                    IF OLD.barcode IS NOT NULL THEN
                        DELETE FROM product_identifiers
                        WHERE variant_id = NEW.id AND identifier_type = 'BARCODE';
                    END IF;
                    IF NEW.barcode IS NOT NULL THEN
                        INSERT INTO product_identifiers (identifier_type, identifier_value, product_id, variant_id)
                        VALUES ('BARCODE', NEW.barcode, NULL, NEW.id);
                    END IF;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_sync_variants
        AFTER INSERT OR UPDATE OF sku, barcode ON product_variants
        FOR EACH ROW EXECUTE FUNCTION sync_variants_identifiers();
        """)


def downgrade() -> None:
    """Downgrade schema removing triggers, functions, registry, and added product columns."""
    bind = op.get_bind()

    # Precondition: Refuse destructive downgrade when identifier or product data exists unless overridden
    allow_data_loss = os.environ.get("ALLOW_DESTRUCTIVE_DOWNGRADE", "").strip() == "1"
    if not allow_data_loss:
        has_identifiers = bind.execute(
            sa.text("SELECT 1 FROM product_identifiers LIMIT 1;")
        ).first()
        has_products = bind.execute(
            sa.text("SELECT 1 FROM products WHERE sku IS NOT NULL OR barcode IS NOT NULL OR product_code IS NOT NULL LIMIT 1;")
        ).first()

        if has_identifiers or has_products:
            raise RuntimeError(
                "CRITICAL: Downgrade aborted to prevent irreversible data loss! "
                "The database contains active SKU, barcode, or product_identifiers records that would be dropped. "
                "To force destructive downgrade after taking a full database backup, set environment variable "
                "ALLOW_DESTRUCTIVE_DOWNGRADE=1 and rerun."
            )

    # 1. Drop Triggers and Functions
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_sync_variants ON product_variants;")
        op.execute("DROP TRIGGER IF EXISTS trg_sync_products ON products;")
        op.execute("DROP FUNCTION IF EXISTS sync_variants_identifiers();")
        op.execute("DROP FUNCTION IF EXISTS sync_products_identifiers();")
        op.execute("DROP TRIGGER IF EXISTS trg_normalize_variants ON product_variants;")
        op.execute("DROP TRIGGER IF EXISTS trg_normalize_products ON products;")
        op.execute("DROP FUNCTION IF EXISTS normalize_product_identifiers();")

    # 2. Drop product_identifiers table
    op.drop_index('ix_product_identifiers_type_val', table_name='product_identifiers')
    op.drop_index(op.f('ix_product_identifiers_variant_id'), table_name='product_identifiers')
    op.drop_index(op.f('ix_product_identifiers_product_id'), table_name='product_identifiers')
    op.drop_table('product_identifiers')

    # 3. Drop indexes and columns from products
    op.drop_index(op.f('ix_products_barcode'), table_name='products')
    op.drop_index(op.f('ix_products_sku'), table_name='products')
    op.drop_index(op.f('ix_products_product_code'), table_name='products')
    op.drop_column('products', 'barcode')
    op.drop_column('products', 'sku')
    op.drop_column('products', 'product_code')
