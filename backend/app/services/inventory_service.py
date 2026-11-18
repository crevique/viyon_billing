"""Business logic for real-time inventory management and audit ledger movements."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID, uuid4
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog
from app.models.category import Category, Subcategory
from app.models.inventory import Inventory
from app.models.product import Product, ProductVariant
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.schemas.inventory import (
    InventoryAdjustmentRequest,
    InventoryAdjustmentResponse,
    InventoryInwardRequest,
    InventoryOut,
    InventorySummaryOut,
    StockMovementOut,
)


class InventoryService:
    """Service providing stock queries, transactional adjustments, and audit trail ledger."""

    # --------------------------------------------------------------------------
    # Inventory Summary Metrics
    # --------------------------------------------------------------------------
    @classmethod
    def get_inventory_summary(cls, db: Session) -> InventorySummaryOut:
        """Compute real-time summary metrics for inventory dashboard cards."""
        # 1. Total active products
        total_products = (
            db.scalar(
                select(func.count(Product.id)).where(
                    and_(Product.is_active.is_(True), Product.is_archived.is_(False))
                )
            )
            or 0
        )

        # 2. Total active variants
        total_variants = (
            db.scalar(
                select(func.count(ProductVariant.id)).where(ProductVariant.is_active.is_(True))
            )
            or 0
        )

        # 3. Total stock (sum of all inventory quantities)
        total_stock = (
            db.scalar(select(func.coalesce(func.sum(Inventory.quantity), 0)))
            or 0
        )

        # 4. Low stock items (quantity > 0 and quantity <= low_stock_threshold)
        low_stock_items = (
            db.scalar(
                select(func.count(Inventory.id)).where(
                    and_(
                        Inventory.quantity > 0,
                        Inventory.quantity <= Inventory.low_stock_threshold,
                    )
                )
            )
            or 0
        )

        # 5. Out of stock items (quantity == 0)
        out_of_stock_items = (
            db.scalar(select(func.count(Inventory.id)).where(Inventory.quantity == 0))
            or 0
        )

        # 6. Total stock adjustments (movements of type ADJUSTMENT)
        total_adjustments = (
            db.scalar(
                select(func.count(StockMovement.id)).where(
                    StockMovement.movement_type == "ADJUSTMENT"
                )
            )
            or 0
        )

        return InventorySummaryOut(
            total_products=int(total_products),
            total_variants=int(total_variants),
            total_stock=int(total_stock),
            low_stock_items=int(low_stock_items),
            out_of_stock_items=int(out_of_stock_items),
            total_adjustments=int(total_adjustments),
        )

    # --------------------------------------------------------------------------
    # Inventory Queries
    # --------------------------------------------------------------------------
    @classmethod
    def list_inventory(
        cls,
        db: Session,
        product_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
        subcategory_id: Optional[UUID] = None,
        stock_status: Optional[str] = None,
        product_type: Optional[str] = None,
        low_stock_only: bool = False,
        search: Optional[str] = None,
        sort_by: Optional[str] = "product_name",
        sort_desc: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InventoryOut], int]:
        """List inventory records with category, variant details, and stock indicators."""
        query = (
            select(Inventory)
            .join(Product, Inventory.product_id == Product.id)
            .outerjoin(ProductVariant, Inventory.variant_id == ProductVariant.id)
            .outerjoin(Category, Product.category_id == Category.id)
            .outerjoin(Subcategory, Product.subcategory_id == Subcategory.id)
            .options(
                joinedload(Inventory.product).joinedload(Product.category),
                joinedload(Inventory.product).joinedload(Product.subcategory),
                joinedload(Inventory.variant),
            )
        )
        filters = []

        if product_id is not None:
            filters.append(Inventory.product_id == product_id)

        if category_id is not None:
            filters.append(Product.category_id == category_id)

        if subcategory_id is not None:
            filters.append(Product.subcategory_id == subcategory_id)

        if product_type:
            filters.append(Product.product_type == product_type.upper())

        if low_stock_only:
            filters.append(Inventory.quantity <= Inventory.low_stock_threshold)
        elif stock_status:
            status_clean = stock_status.strip().upper()
            if status_clean == "OUT_OF_STOCK":
                filters.append(Inventory.quantity == 0)
            elif status_clean == "LOW_STOCK":
                filters.append(
                    and_(
                        Inventory.quantity > 0,
                        Inventory.quantity <= Inventory.low_stock_threshold,
                    )
                )
            elif status_clean == "IN_STOCK":
                filters.append(Inventory.quantity > Inventory.low_stock_threshold)

        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Product.product_name.ilike(term),
                    Product.product_code.ilike(term),
                    Product.sku.ilike(term),
                    ProductVariant.sku.ilike(term),
                    Product.barcode.ilike(term),
                    ProductVariant.barcode.ilike(term),
                )
            )

        if filters:
            query = query.where(and_(*filters))

        # Total count query
        count_query = (
            select(func.count(Inventory.id))
            .join(Product, Inventory.product_id == Product.id)
            .outerjoin(ProductVariant, Inventory.variant_id == ProductVariant.id)
            .outerjoin(Category, Product.category_id == Category.id)
            .outerjoin(Subcategory, Product.subcategory_id == Subcategory.id)
        )
        if filters:
            count_query = count_query.where(and_(*filters))
        total = db.scalar(count_query) or 0

        # Sorting logic
        order_col = Product.product_name
        if sort_by in ("quantity", "stock"):
            order_col = Inventory.quantity
        elif sort_by == "updated_at":
            order_col = Inventory.updated_at
        elif sort_by == "sku":
            order_col = func.coalesce(ProductVariant.sku, Product.sku)

        if sort_desc:
            query = query.order_by(order_col.desc(), Inventory.variant_id.nulls_first())
        else:
            query = query.order_by(order_col.asc(), Inventory.variant_id.nulls_first())

        query = query.limit(limit).offset(offset)
        rows = db.scalars(query).all()

        results = [cls._build_inventory_out(inv) for inv in rows]
        return results, total

    @classmethod
    def get_inventory_by_product_id(
        cls, db: Session, product_id: UUID
    ) -> List[InventoryOut]:
        """Fetch all inventory records for a given product (1 for SIMPLE, N for VARIANT)."""
        query = (
            select(Inventory)
            .where(Inventory.product_id == product_id)
            .options(
                joinedload(Inventory.product).joinedload(Product.category),
                joinedload(Inventory.product).joinedload(Product.subcategory),
                joinedload(Inventory.variant),
            )
            .order_by(Inventory.variant_id.nulls_first())
        )
        rows = db.scalars(query).all()
        return [cls._build_inventory_out(inv) for inv in rows]

    # --------------------------------------------------------------------------
    # Inventory Adjustment (Transactional with Row Lock)
    # --------------------------------------------------------------------------
    @classmethod
    def adjust_stock(
        cls,
        db: Session,
        adj_in: InventoryAdjustmentRequest,
        current_user: User,
    ) -> InventoryAdjustmentResponse:
        """Adjust stock level using SELECT FOR UPDATE lock and record immutable StockMovement."""
        # 1. Fetch product to determine type
        product = db.scalar(select(Product).where(Product.id == adj_in.product_id))
        if not product:
            raise ValueError(f"Product with ID '{adj_in.product_id}' does not exist.")

        if product.product_type == "SIMPLE" and adj_in.variant_id is not None:
            raise ValueError("Cannot specify variant_id for a SIMPLE product.")

        if product.product_type == "VARIANT" and adj_in.variant_id is None:
            raise ValueError("variant_id is required when adjusting stock for a VARIANT product.")

        # 2. Acquire pessimistic row lock on target inventory row
        inv_query = select(Inventory).with_for_update()
        if adj_in.variant_id is None:
            inv_query = inv_query.where(
                and_(
                    Inventory.product_id == adj_in.product_id,
                    Inventory.variant_id.is_(None),
                )
            )
        else:
            inv_query = inv_query.where(
                and_(
                    Inventory.product_id == adj_in.product_id,
                    Inventory.variant_id == adj_in.variant_id,
                )
            )

        inventory = db.scalar(inv_query)
        if not inventory:
            raise ValueError("No inventory record found for the specified product and variant.")

        # 3. Calculate new quantity and prevent negative stock
        previous_qty = inventory.quantity
        new_qty = previous_qty + adj_in.quantity_change
        if new_qty < 0:
            raise ValueError(
                f"Insufficient stock: Current quantity is {previous_qty}, "
                f"requested adjustment of {adj_in.quantity_change} would result in negative stock ({new_qty})."
            )

        inventory.quantity = new_qty

        # Format audit note
        note_str = adj_in.reason.strip()
        if adj_in.notes:
            note_str = f"{note_str} | {adj_in.notes.strip()}"

        # 4. Insert immutable audit movement in the same transaction
        movement = StockMovement(
            product_id=adj_in.product_id,
            variant_id=adj_in.variant_id,
            movement_type=adj_in.movement_type,
            quantity_change=adj_in.quantity_change,
            reference_type="MANUAL_ADJUSTMENT",
            reference_id=None,
            notes=note_str,
            created_by_user_id=current_user.id,
        )
        db.add(movement)
        db.commit()
        db.refresh(inventory)
        db.refresh(movement)

        return InventoryAdjustmentResponse(
            message="Stock level adjusted successfully.",
            product_id=adj_in.product_id,
            variant_id=adj_in.variant_id,
            previous_quantity=previous_qty,
            quantity_change=adj_in.quantity_change,
            new_quantity=new_qty,
            movement_id=movement.id,
            movement_type=movement.movement_type,
            reason=movement.notes or "",
            updated_at=inventory.updated_at,
        )

    # --------------------------------------------------------------------------
    # Stock Inward (Purchase Receipt with Row Lock)
    # --------------------------------------------------------------------------
    @classmethod
    def stock_inward(
        cls,
        db: Session,
        inward_in: InventoryInwardRequest,
        current_owner: User,
    ) -> InventoryAdjustmentResponse:
        """Record goods receipt / purchase inward with pessimistic row lock and immutable audit ledger."""
        # 1. Fetch product to determine type
        product = db.scalar(select(Product).where(Product.id == inward_in.product_id))
        if not product:
            raise ValueError(f"Product with ID '{inward_in.product_id}' does not exist.")

        if product.product_type == "SIMPLE" and inward_in.variant_id is not None:
            raise ValueError("Cannot specify variant_id for a SIMPLE product.")

        if product.product_type == "VARIANT" and inward_in.variant_id is None:
            raise ValueError("variant_id is required when recording stock inward for a VARIANT product.")

        # 2. Acquire pessimistic row lock
        inv_query = select(Inventory).with_for_update()
        if inward_in.variant_id is None:
            inv_query = inv_query.where(
                and_(
                    Inventory.product_id == inward_in.product_id,
                    Inventory.variant_id.is_(None),
                )
            )
        else:
            inv_query = inv_query.where(
                and_(
                    Inventory.product_id == inward_in.product_id,
                    Inventory.variant_id == inward_in.variant_id,
                )
            )

        inventory = db.scalar(inv_query)
        if not inventory:
            raise ValueError("No inventory record found for the specified product and variant.")

        previous_qty = inventory.quantity
        new_qty = previous_qty + inward_in.quantity
        inventory.quantity = new_qty

        # Format audit notes
        note_parts = []
        if inward_in.supplier_name:
            note_parts.append(f"Supplier: {inward_in.supplier_name.strip()}")
        if inward_in.purchase_reference:
            note_parts.append(f"Ref: {inward_in.purchase_reference.strip()}")
        if inward_in.notes:
            note_parts.append(inward_in.notes.strip())
        notes_str = " | ".join(note_parts) if note_parts else "Goods received inward (Purchase)"

        movement = StockMovement(
            product_id=inward_in.product_id,
            variant_id=inward_in.variant_id,
            movement_type="PURCHASE",
            quantity_change=inward_in.quantity,
            reference_type="PURCHASE_INWARD",
            reference_id=None,
            notes=notes_str,
            created_by_user_id=current_owner.id,
        )
        db.add(movement)
        db.commit()
        db.refresh(inventory)
        db.refresh(movement)

        return InventoryAdjustmentResponse(
            message="Stock inward recorded successfully.",
            product_id=inward_in.product_id,
            variant_id=inward_in.variant_id,
            previous_quantity=previous_qty,
            quantity_change=inward_in.quantity,
            new_quantity=new_qty,
            movement_id=movement.id,
            movement_type="PURCHASE",
            reason=notes_str,
            updated_at=inventory.updated_at,
        )

    # --------------------------------------------------------------------------
    # Low-Stock Threshold Configuration
    # --------------------------------------------------------------------------
    @classmethod
    def update_threshold(
        cls,
        db: Session,
        inventory_id: UUID,
        new_threshold: int,
        current_owner: User,
    ) -> InventoryOut:
        """Update the low-stock alert threshold for an inventory item (Owner only)."""
        if new_threshold < 0:
            raise ValueError("Low-stock threshold must be non-negative.")

        inventory = db.scalar(
            select(Inventory)
            .where(Inventory.id == inventory_id)
            .options(
                joinedload(Inventory.product).joinedload(Product.category),
                joinedload(Inventory.product).joinedload(Product.subcategory),
                joinedload(Inventory.variant),
            )
        )
        if not inventory:
            raise ValueError(f"Inventory record '{inventory_id}' not found.")

        inventory.low_stock_threshold = new_threshold
        db.commit()
        db.refresh(inventory)
        return cls._build_inventory_out(inventory)

    # --------------------------------------------------------------------------
    # Stock Movement Ledger Queries
    # --------------------------------------------------------------------------
    @classmethod
    def list_movements(
        cls,
        db: Session,
        product_id: Optional[UUID] = None,
        variant_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        movement_type: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[StockMovementOut], int]:
        """List historical stock ledger movements with user audit and filter support."""
        query = (
            select(StockMovement)
            .join(Product, StockMovement.product_id == Product.id)
            .outerjoin(ProductVariant, StockMovement.variant_id == ProductVariant.id)
            .outerjoin(Category, Product.category_id == Category.id)
            .options(
                joinedload(StockMovement.product).joinedload(Product.category),
                joinedload(StockMovement.variant),
                joinedload(StockMovement.created_by_user),
            )
        )
        filters = []

        if product_id is not None:
            filters.append(StockMovement.product_id == product_id)
        if variant_id is not None:
            filters.append(StockMovement.variant_id == variant_id)
        if category_id is not None:
            filters.append(Product.category_id == category_id)
        if user_id is not None:
            filters.append(StockMovement.created_by_user_id == user_id)
        if movement_type:
            filters.append(StockMovement.movement_type == movement_type.strip().upper())
        if start_date is not None:
            filters.append(StockMovement.created_at >= start_date)
        if end_date is not None:
            filters.append(StockMovement.created_at <= end_date)
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Product.product_name.ilike(term),
                    Product.sku.ilike(term),
                    ProductVariant.sku.ilike(term),
                    StockMovement.notes.ilike(term),
                    StockMovement.reference_type.ilike(term),
                )
            )

        if filters:
            query = query.where(and_(*filters))

        count_query = (
            select(func.count(StockMovement.id))
            .join(Product, StockMovement.product_id == Product.id)
            .outerjoin(ProductVariant, StockMovement.variant_id == ProductVariant.id)
            .outerjoin(Category, Product.category_id == Category.id)
        )
        if filters:
            count_query = count_query.where(and_(*filters))
        total = db.scalar(count_query) or 0

        query = query.order_by(StockMovement.created_at.desc()).limit(limit).offset(offset)
        movements = db.scalars(query).all()

        results = [
            StockMovementOut(
                id=m.id,
                product_id=m.product_id,
                product_name=m.product.product_name if m.product else "Unknown",
                category_name=m.product.category.name if (m.product and m.product.category) else None,
                variant_id=m.variant_id,
                variant_size=m.variant.size if m.variant else None,
                variant_color=m.variant.color if m.variant else None,
                sku=m.variant.sku if m.variant else (m.product.sku if m.product else None),
                movement_type=m.movement_type,
                quantity_change=m.quantity_change,
                reference_type=m.reference_type,
                reference_id=m.reference_id,
                notes=m.notes,
                created_by_user_id=m.created_by_user_id,
                created_by_user_name=m.created_by_user.full_name if m.created_by_user else None,
                created_at=m.created_at,
            )
            for m in movements
        ]
        return results, total

    # --------------------------------------------------------------------------
    # Helper Serialization
    # --------------------------------------------------------------------------
    @staticmethod
    def _build_inventory_out(inv: Inventory) -> InventoryOut:
        """Convert Inventory ORM instance into InventoryOut response schema."""
        product = inv.product
        variant = inv.variant

        sku = variant.sku if variant else (product.sku if product else None)
        barcode = variant.barcode if variant else (product.barcode if product else None)
        size = variant.size if variant else None
        color = variant.color if variant else None

        category_id = product.category_id if product else None
        category_name = product.category.name if (product and product.category) else None
        subcategory_id = product.subcategory_id if product else None
        subcategory_name = product.subcategory.name if (product and product.subcategory) else None
        image_url = product.product_image_url if product else None

        is_low = inv.quantity <= inv.low_stock_threshold
        if inv.quantity == 0:
            stock_status = "OUT_OF_STOCK"
        elif is_low:
            stock_status = "LOW_STOCK"
        else:
            stock_status = "IN_STOCK"

        return InventoryOut(
            id=inv.id,
            product_id=inv.product_id,
            product_name=product.product_name if product else "Unknown",
            product_code=product.product_code if product else None,
            product_type=product.product_type if product else "SIMPLE",
            product_image_url=image_url,
            category_id=category_id,
            category_name=category_name,
            subcategory_id=subcategory_id,
            subcategory_name=subcategory_name,
            variant_id=inv.variant_id,
            size=size,
            color=color,
            sku=sku,
            barcode=barcode,
            quantity=inv.quantity,
            low_stock_threshold=inv.low_stock_threshold,
            is_low_stock=is_low,
            stock_status=stock_status,
            updated_at=inv.updated_at,
        )

    # --------------------------------------------------------------------------
    # Inventory Deletion (Owner Only)
    # --------------------------------------------------------------------------
    @classmethod
    def delete_inventory(
        cls,
        db: Session,
        inventory_id: UUID,
        current_owner: User,
    ) -> dict:
        """Safely delete an inventory record (Owner Only).

        Preserves product and variant records while removing the inventory row.
        Records an audit log entry for the deletion.
        """
        inv = db.scalar(
            select(Inventory)
            .where(Inventory.id == inventory_id)
            .options(joinedload(Inventory.product), joinedload(Inventory.variant))
            .with_for_update()
        )
        if not inv:
            raise ValueError(f"Inventory record with ID '{inventory_id}' was not found.")

        prod_name = inv.product.product_name if inv.product else "Unknown Product"
        var_sku = inv.variant.sku if inv.variant else None
        qty = inv.quantity

        now_utc = datetime.now(timezone.utc)
        audit = AuditLog(
            id=uuid4(),
            user_id=current_owner.id,
            action="INVENTORY_DELETED",
            entity_type="INVENTORY",
            entity_id=inv.id,
            old_values={
                "product_id": str(inv.product_id),
                "variant_id": str(inv.variant_id) if inv.variant_id else None,
                "product_name": prod_name,
                "variant_sku": var_sku,
                "quantity": qty,
                "low_stock_threshold": inv.low_stock_threshold,
            },
            new_values={
                "deleted": True,
                "actioned_by": str(current_owner.id),
            },
            created_at=now_utc,
        )
        db.add(audit)
        db.delete(inv)
        db.commit()

        return {
            "message": f"Inventory record for '{prod_name}' was successfully deleted.",
            "deleted": True,
            "inventory_id": str(inventory_id),
        }

    # --------------------------------------------------------------------------
    # Stock Movement Deletion (Owner Only with Safe Reversal)
    # --------------------------------------------------------------------------
    @classmethod
    def delete_stock_movement(
        cls,
        db: Session,
        movement_id: UUID,
        current_owner: User,
    ) -> dict:
        """Delete a stock movement and safely reverse its inventory impact (Owner Only).

        - Reverses the quantity change on the corresponding inventory record.
        - Prevents deletion if reversal would drive inventory negative.
        - Prevents deletion if linked to a bill sale/return or goods receipt.
        - Uses a database transaction and records an audit log.
        """
        movement = db.scalar(
            select(StockMovement)
            .where(StockMovement.id == movement_id)
            .with_for_update()
        )
        if not movement:
            raise ValueError(f"Stock movement with ID '{movement_id}' was not found.")

        # Guard against immutable sales and inward records
        if movement.reference_type == "BILL" or movement.movement_type in ("SALE", "RETURN"):
            raise ValueError(
                "Cannot delete stock movement linked to a sales bill or return. "
                "Use Bill Cancellation or Return workflow to reverse sales and preserve financial audit trail."
            )

        if movement.reference_type == "GOODS_RECEIPT":
            raise ValueError(
                "Cannot delete stock movement linked to a Goods Receipt. "
                "Goods receipt reversal must be handled through Purchase Order management."
            )

        # Calculate reversal delta: if original change was +10, reversal is -10; if -5, reversal is +5
        reversal_delta = -movement.quantity_change

        # Locate corresponding inventory record
        inv_filter = [Inventory.product_id == movement.product_id]
        if movement.variant_id:
            inv_filter.append(Inventory.variant_id == movement.variant_id)
        else:
            inv_filter.append(Inventory.variant_id.is_(None))

        inv = db.scalar(
            select(Inventory)
            .where(and_(*inv_filter))
            .with_for_update()
        )

        if inv:
            new_qty = inv.quantity + reversal_delta
            if new_qty < 0:
                raise ValueError(
                    f"Cannot delete stock movement: reversing this {movement.quantity_change:+d} quantity change "
                    f"would reduce current inventory ({inv.quantity}) below zero (to {new_qty})."
                )
            inv.quantity = new_qty
            inv.updated_at = datetime.now(timezone.utc)
            db.add(inv)

        now_utc = datetime.now(timezone.utc)
        audit = AuditLog(
            id=uuid4(),
            user_id=current_owner.id,
            action="STOCK_MOVEMENT_DELETED",
            entity_type="STOCK_MOVEMENT",
            entity_id=movement.id,
            old_values={
                "movement_type": movement.movement_type,
                "quantity_change": movement.quantity_change,
                "product_id": str(movement.product_id),
                "variant_id": str(movement.variant_id) if movement.variant_id else None,
                "reference_type": movement.reference_type,
                "reference_id": str(movement.reference_id) if movement.reference_id else None,
                "notes": movement.notes,
            },
            new_values={
                "deleted": True,
                "reversal_applied": reversal_delta,
                "actioned_by": str(current_owner.id),
            },
            created_at=now_utc,
        )
        db.add(audit)
        db.delete(movement)
        db.commit()

        return {
            "message": f"Stock movement was successfully reversed and deleted. Inventory adjusted by {reversal_delta:+d}.",
            "deleted": True,
            "reversal_delta": reversal_delta,
            "movement_id": str(movement_id),
        }
