"""Business logic for Product and ProductVariant catalogue management."""

from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, func, and_, or_, distinct
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category, Subcategory
from app.models.product import Product, ProductVariant
from app.models.product_identifier import ProductIdentifier
from app.models.inventory import Inventory
from app.models.stock_movement import StockMovement
from app.models.bill import BillItem
from app.models.user import User
try:
    from app.models.purchase import PurchaseOrderItem, GoodsReceiptItem
except ImportError:
    PurchaseOrderItem = None
    GoodsReceiptItem = None
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductOut,
    VariantCreate,
    VariantUpdate,
    VariantOut,
)


class ProductService:
    """Service handling products, variants, and catalogue lifecycle."""

    # --------------------------------------------------------------------------
    # Product Operations
    # --------------------------------------------------------------------------
    @classmethod
    def list_products(
        cls,
        db: Session,
        search: Optional[str] = None,
        category_id: Optional[UUID] = None,
        subcategory_id: Optional[UUID] = None,
        brand: Optional[str] = None,
        product_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_archived: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ProductOut], int]:
        """Query products with comprehensive filtering, search, pagination, and stock aggregation."""
        query = select(Product)
        filters = []

        if category_id is not None:
            filters.append(Product.category_id == category_id)
        if subcategory_id is not None:
            filters.append(Product.subcategory_id == subcategory_id)
        if brand:
            filters.append(Product.brand.ilike(f"%{brand.strip()}%"))
        if product_type:
            filters.append(Product.product_type == product_type.upper())
        if is_active is not None:
            filters.append(Product.is_active == is_active)
        if is_archived is not None:
            filters.append(Product.is_archived == is_archived)

        if search:
            term = f"%{search.strip()}%"
            # Search across product_name, product_code, product SKU/barcode, and variant SKU/barcode
            variant_match_subquery = (
                select(ProductVariant.product_id)
                .where(
                    or_(
                        ProductVariant.sku.ilike(term),
                        ProductVariant.barcode.ilike(term),
                    )
                )
            )
            filters.append(
                or_(
                    Product.product_name.ilike(term),
                    Product.product_code.ilike(term),
                    Product.sku.ilike(term),
                    Product.barcode.ilike(term),
                    Product.id.in_(variant_match_subquery),
                )
            )

        if filters:
            query = query.where(and_(*filters))

        # Total count query
        count_query = select(func.count(distinct(Product.id)))
        if filters:
            count_query = count_query.where(and_(*filters))
        total = db.scalar(count_query) or 0

        # Order and paginate
        query = (
            query.order_by(Product.product_name.asc())
            .options(
                joinedload(Product.category),
                joinedload(Product.subcategory),
                joinedload(Product.variants),
                joinedload(Product.inventory),
            )
            .limit(limit)
            .offset(offset)
        )
        products = db.scalars(query).unique().all()

        results = [cls._build_product_out(p) for p in products]
        return results, total

    @classmethod
    def get_product_by_id(cls, db: Session, product_id: UUID) -> Optional[Product]:
        """Fetch product with associated category, subcategory, variants, and inventory."""
        query = (
            select(Product)
            .where(Product.id == product_id)
            .options(
                joinedload(Product.category),
                joinedload(Product.subcategory),
                joinedload(Product.variants).joinedload(ProductVariant.inventory),
                joinedload(Product.inventory),
            )
        )
        return db.scalar(query)

    @classmethod
    def create_product(
        cls, db: Session, product_in: ProductCreate, current_user: User
    ) -> Product:
        """Create a simple or variant product with initial inventory and stock ledger."""
        # 1. Validate Category
        category = db.scalar(select(Category).where(Category.id == product_in.category_id))
        if not category:
            raise ValueError(f"Category with ID '{product_in.category_id}' does not exist.")

        # 2. Validate Subcategory
        if product_in.subcategory_id:
            subcat = db.scalar(
                select(Subcategory).where(
                    and_(
                        Subcategory.id == product_in.subcategory_id,
                        Subcategory.category_id == product_in.category_id,
                    )
                )
            )
            if not subcat:
                raise ValueError("Selected subcategory does not belong to the selected category.")

        # 3. Check Product Code uniqueness if provided
        product_code = product_in.product_code.strip().upper() if product_in.product_code else None
        if product_code:
            existing_code = db.scalar(
                select(Product.id).where(Product.product_code == product_code)
            )
            if existing_code:
                raise ValueError(f"Product code '{product_code}' is already in use.")

        try:
            # 4. Handle SIMPLE Product
            if product_in.product_type == "SIMPLE":
                sku = product_in.sku.strip().upper() if product_in.sku else None
                barcode = product_in.barcode.strip().upper() if product_in.barcode else None

                # Pre-check shared registry to provide informative error
                if sku:
                    existing_sku = db.scalar(
                        select(ProductIdentifier.id).where(
                            and_(
                                ProductIdentifier.identifier_type == "SKU",
                                ProductIdentifier.identifier_value == sku,
                            )
                        )
                    )
                    if existing_sku:
                        raise ValueError(f"SKU '{sku}' is already assigned to another product or variant.")

                if barcode:
                    existing_bar = db.scalar(
                        select(ProductIdentifier.id).where(
                            and_(
                                ProductIdentifier.identifier_type == "BARCODE",
                                ProductIdentifier.identifier_value == barcode,
                            )
                        )
                    )
                    if existing_bar:
                        raise ValueError(f"Barcode '{barcode}' is already assigned to another product or variant.")

                product = Product(
                    product_name=product_in.product_name.strip(),
                    product_code=product_code,
                    category_id=product_in.category_id,
                    subcategory_id=product_in.subcategory_id,
                    brand=product_in.brand.strip() if product_in.brand else None,
                    product_type="SIMPLE",
                    base_price=product_in.base_price,
                    cost_price=product_in.cost_price,
                    description=product_in.description.strip() if product_in.description else None,
                    product_image_url=product_in.product_image_url,
                    sku=sku,
                    barcode=barcode,
                    is_active=product_in.is_active,
                    is_archived=False,
                )
                db.add(product)
                db.flush()  # Generates product.id, runs normalization & sync triggers

                # Create single inventory row with variant_id = NULL
                inventory = Inventory(
                    product_id=product.id,
                    variant_id=None,
                    quantity=product_in.initial_stock,
                    low_stock_threshold=product_in.low_stock_threshold,
                )
                db.add(inventory)
                db.flush()

                # Record stock ledger movement if initial stock > 0
                if product_in.initial_stock > 0:
                    movement = StockMovement(
                        product_id=product.id,
                        variant_id=None,
                        movement_type="PURCHASE",
                        quantity_change=product_in.initial_stock,
                        reference_type="INITIAL_STOCK",
                        reference_id=product.id,
                        notes="Initial opening stock on product creation",
                        created_by_user_id=current_user.id,
                    )
                    db.add(movement)

            # 5. Handle VARIANT Product
            else:
                product = Product(
                    product_name=product_in.product_name.strip(),
                    product_code=product_code,
                    category_id=product_in.category_id,
                    subcategory_id=product_in.subcategory_id,
                    brand=product_in.brand.strip() if product_in.brand else None,
                    product_type="VARIANT",
                    base_price=product_in.base_price,
                    cost_price=product_in.cost_price,
                    description=product_in.description.strip() if product_in.description else None,
                    product_image_url=product_in.product_image_url,
                    sku=None,
                    barcode=None,
                    is_active=product_in.is_active,
                    is_archived=False,
                )
                db.add(product)
                db.flush()

                # Process initial variants if provided
                if product_in.variants:
                    seen_combos = set()
                    for v_in in product_in.variants:
                        size_raw = v_in.size.strip()
                        color_raw = v_in.color.strip()
                        if not size_raw:
                            raise ValueError("Size cannot be empty for a variant.")

                        size_upper = size_raw.upper()
                        color_upper = color_raw.upper()
                        combo = (size_upper, color_upper)
                        if combo in seen_combos:
                            raise ValueError(f"Duplicate variant combination ({size_raw}, {color_raw}) in request.")
                        seen_combos.add(combo)

                        # Standardize standard size codes to uppercase; preserve words like Free Size
                        if size_upper in ("XS", "S", "M", "L", "XL", "XXL", "2XL", "3XL", "4XL", "5XL", "6XL"):
                            size_clean = size_upper
                        elif size_upper in ("FREE SIZE", "FREESIZE"):
                            size_clean = "Free Size"
                        else:
                            size_clean = size_raw

                        v_sku = v_in.sku.strip().upper()
                        v_barcode = v_in.barcode.strip().upper() if v_in.barcode else None

                        variant = ProductVariant(
                            product_id=product.id,
                            size=size_clean,
                            color=color_raw.title() if color_raw.lower() in ("standard", "black", "white", "blue", "navy", "grey") else color_raw,
                            sku=v_sku,
                            barcode=v_barcode,
                            price_override=v_in.price_override,
                            is_active=v_in.is_active,
                        )
                        db.add(variant)
                        db.flush()

                        inv = Inventory(
                            product_id=product.id,
                            variant_id=variant.id,
                            quantity=v_in.initial_stock,
                            low_stock_threshold=v_in.low_stock_threshold,
                        )
                        db.add(inv)
                        db.flush()

                        if v_in.initial_stock > 0:
                            m = StockMovement(
                                product_id=product.id,
                                variant_id=variant.id,
                                movement_type="PURCHASE",
                                quantity_change=v_in.initial_stock,
                                reference_type="INITIAL_STOCK",
                                reference_id=variant.id,
                                notes="Initial opening stock on variant creation",
                                created_by_user_id=current_user.id,
                            )
                            db.add(m)

            db.commit()
            return cls.get_product_by_id(db, product.id)  # type: ignore

        except IntegrityError as e:
            db.rollback()
            err_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            if "ix_products_product_code" in err_msg or "product_code" in err_msg:
                raise ValueError(f"Product code '{product_code}' is already in use.")
            if "ix_product_identifiers_type_val" in err_msg or "product_identifiers" in err_msg:
                raise ValueError("A product or variant with this SKU or barcode already exists.")
            if "uq_product_variants_product_size_color" in err_msg:
                raise ValueError("A variant with this size and color already exists for this product.")
            raise ValueError(f"Database constraint violation: {err_msg}")
        except Exception:
            db.rollback()
            raise

    @classmethod
    def update_product(
        cls, db: Session, product: Product, product_in: ProductUpdate
    ) -> Product:
        """Update product details, handling category/subcategory changes and simple product SKU/barcode."""
        # 1. Category / Subcategory validation if updated
        new_cat_id = product_in.category_id or product.category_id
        new_subcat_id = product_in.subcategory_id if product_in.subcategory_id is not None else product.subcategory_id

        if product_in.category_id is not None:
            cat = db.scalar(select(Category).where(Category.id == product_in.category_id))
            if not cat:
                raise ValueError(f"Category with ID '{product_in.category_id}' does not exist.")

        if new_subcat_id:
            subcat = db.scalar(
                select(Subcategory).where(
                    and_(
                        Subcategory.id == new_subcat_id,
                        Subcategory.category_id == new_cat_id,
                    )
                )
            )
            if not subcat:
                raise ValueError("Selected subcategory does not belong to the selected category.")

        # 2. Product code check
        if product_in.product_code is not None:
            code = product_in.product_code.strip().upper() if product_in.product_code else None
            if code and code != product.product_code:
                existing_code = db.scalar(
                    select(Product.id).where(
                        and_(Product.product_code == code, Product.id != product.id)
                    )
                )
                if existing_code:
                    raise ValueError(f"Product code '{code}' is already in use.")
            product.product_code = code

        # 3. Simple Product SKU / Barcode updates
        if product.product_type == "SIMPLE":
            if product_in.sku is not None:
                new_sku = product_in.sku.strip().upper()
                if not new_sku:
                    raise ValueError("A SIMPLE product requires a valid non-empty SKU.")
                product.sku = new_sku
            if product_in.barcode is not None:
                product.barcode = (
                    product_in.barcode.strip().upper() if product_in.barcode.strip() else None
                )
        else:
            if product_in.sku or product_in.barcode:
                raise ValueError("Cannot assign SKU or barcode to a VARIANT parent product.")

        if product_in.product_name is not None:
            product.product_name = product_in.product_name.strip()
        if product_in.category_id is not None:
            product.category_id = product_in.category_id
        if product_in.subcategory_id is not None:
            product.subcategory_id = product_in.subcategory_id
        if product_in.brand is not None:
            product.brand = product_in.brand.strip() if product_in.brand else None
        if product_in.base_price is not None:
            product.base_price = product_in.base_price
        if product_in.cost_price is not None:
            product.cost_price = product_in.cost_price
        if product_in.description is not None:
            product.description = product_in.description.strip() if product_in.description else None
        if product_in.product_image_url is not None:
            product.product_image_url = product_in.product_image_url
        if product_in.is_active is not None:
            product.is_active = product_in.is_active

        try:
            db.commit()
            return cls.get_product_by_id(db, product.id)  # type: ignore
        except IntegrityError as e:
            db.rollback()
            err_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            if "ix_products_product_code" in err_msg:
                raise ValueError("Product code is already in use.")
            if "ix_product_identifiers_type_val" in err_msg:
                raise ValueError("This SKU or barcode is already assigned to another product or variant.")
            raise ValueError(f"Constraint violation: {err_msg}")

    @classmethod
    def archive_product(cls, db: Session, product: Product) -> Product:
        """Soft-archive product to prevent billing while preserving SKU reservation and sales history."""
        product.is_archived = True
        product.is_active = False
        db.commit()
        return cls.get_product_by_id(db, product.id)  # type: ignore

    @classmethod
    def restore_product(cls, db: Session, product: Product) -> Product:
        """Restore an archived product back to active catalogue status."""
        product.is_archived = False
        product.is_active = True
        db.commit()
        return cls.get_product_by_id(db, product.id)  # type: ignore

    @classmethod
    def delete_product(cls, db: Session, product: Product) -> dict:
        """Safely delete a product:
        - If dependent records (sales bills, purchase orders, goods receipts, non-initial stock movements)
          exist, perform a safe soft-delete/archive and deactivate variants to preserve historical integrity.
        - If no dependent records exist, cleanly and permanently delete all related identifiers,
          inventory, variants, initial stock movements, and the product itself.
        """
        # 1. Check historical sales records
        bill_items_count = db.scalar(
            select(func.count(BillItem.id)).where(BillItem.product_id == product.id)
        ) or 0

        # 2. Check purchase orders
        po_count = 0
        if PurchaseOrderItem is not None:
            po_count = db.scalar(
                select(func.count(PurchaseOrderItem.id)).where(PurchaseOrderItem.product_id == product.id)
            ) or 0

        # 3. Check goods receipts
        gr_count = 0
        if GoodsReceiptItem is not None:
            gr_count = db.scalar(
                select(func.count(GoodsReceiptItem.id)).where(GoodsReceiptItem.product_id == product.id)
            ) or 0

        # 4. Check active stock movements beyond initial creation
        non_initial_movements = db.scalar(
            select(func.count(StockMovement.id)).where(
                and_(
                    StockMovement.product_id == product.id,
                    StockMovement.reference_type != "INITIAL_STOCK",
                )
            )
        ) or 0

        # If any dependent historical records exist, SOFT-DELETE / ARCHIVE
        has_history = (bill_items_count > 0 or po_count > 0 or gr_count > 0 or non_initial_movements > 0)
        if has_history:
            product.is_archived = True
            product.is_active = False
            for variant in product.variants:
                variant.is_active = False
            db.commit()
            return {
                "message": (
                    f"Product '{product.product_name}' has associated sales or transaction history. "
                    "It has been safely archived and deactivated to protect financial and inventory records."
                ),
                "soft_deleted": True,
            }

        # Otherwise, cleanly and permanently DELETE product and its children
        db.query(StockMovement).filter(StockMovement.product_id == product.id).delete()
        db.query(Inventory).filter(Inventory.product_id == product.id).delete()
        for variant in product.variants:
            db.query(ProductIdentifier).filter(ProductIdentifier.variant_id == variant.id).delete()
        db.query(ProductIdentifier).filter(ProductIdentifier.product_id == product.id).delete()
        db.query(ProductVariant).filter(ProductVariant.product_id == product.id).delete()
        db.delete(product)
        db.commit()
        return {
            "message": f"Product '{product.product_name}' was permanently deleted.",
            "soft_deleted": False,
        }

    # --------------------------------------------------------------------------
    # Variant Operations
    # --------------------------------------------------------------------------
    @classmethod
    def create_variant(
        cls,
        db: Session,
        product: Product,
        variant_in: VariantCreate,
        current_user: User,
    ) -> ProductVariant:
        """Add a size/color variant to a VARIANT-type parent product."""
        if product.product_type != "VARIANT":
            raise ValueError("Variants can only be added to products of type 'VARIANT'.")

        size_raw = variant_in.size.strip()
        color_raw = variant_in.color.strip()
        if not size_raw:
            raise ValueError("Size cannot be empty for a variant.")

        size_upper = size_raw.upper()
        color_upper = color_raw.upper()

        # Standardize standard size codes to uppercase; preserve words like Free Size
        if size_upper in ("XS", "S", "M", "L", "XL", "XXL", "2XL", "3XL", "4XL", "5XL", "6XL"):
            size_clean = size_upper
        elif size_upper in ("FREE SIZE", "FREESIZE"):
            size_clean = "Free Size"
        else:
            size_clean = size_raw

        sku = variant_in.sku.strip().upper()
        barcode = variant_in.barcode.strip().upper() if variant_in.barcode else None

        # Check duplicate size/color combo case-insensitively
        existing_combo = db.scalar(
            select(ProductVariant.id).where(
                and_(
                    ProductVariant.product_id == product.id,
                    func.upper(ProductVariant.size) == size_upper,
                    func.upper(ProductVariant.color) == color_upper,
                )
            )
        )
        if existing_combo:
            raise ValueError(
                f"Variant with size '{size_clean}' and color '{color_raw}' already exists for this product."
            )

        # Pre-check registry for duplicate SKU
        existing_sku = db.scalar(
            select(ProductIdentifier.id).where(
                and_(
                    ProductIdentifier.identifier_type == "SKU",
                    ProductIdentifier.identifier_value == sku,
                )
            )
        )
        if existing_sku:
            raise ValueError(f"SKU '{sku}' is already assigned to another product or variant.")

        if barcode:
            existing_bar = db.scalar(
                select(ProductIdentifier.id).where(
                    and_(
                        ProductIdentifier.identifier_type == "BARCODE",
                        ProductIdentifier.identifier_value == barcode,
                    )
                )
            )
            if existing_bar:
                raise ValueError(f"Barcode '{barcode}' is already assigned to another product or variant.")

        try:
            variant = ProductVariant(
                product_id=product.id,
                size=size_clean,
                color=color_raw.title() if color_raw.lower() in ("standard", "black", "white", "blue", "navy", "grey") else color_raw,
                sku=sku,
                barcode=barcode,
                price_override=variant_in.price_override,
                is_active=variant_in.is_active,
            )
            db.add(variant)
            db.flush()

            inv = Inventory(
                product_id=product.id,
                variant_id=variant.id,
                quantity=variant_in.initial_stock,
                low_stock_threshold=variant_in.low_stock_threshold,
            )
            db.add(inv)
            db.flush()

            if variant_in.initial_stock > 0:
                m = StockMovement(
                    product_id=product.id,
                    variant_id=variant.id,
                    movement_type="PURCHASE",
                    quantity_change=variant_in.initial_stock,
                    reference_type="INITIAL_STOCK",
                    reference_id=variant.id,
                    notes="Initial opening stock on variant creation",
                    created_by_user_id=current_user.id,
                )
                db.add(m)

            db.commit()
            db.refresh(variant)
            return variant

        except IntegrityError as e:
            db.rollback()
            err_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            if "uq_product_variants_product_size_color" in err_msg:
                raise ValueError(f"Variant combination ({size}, {color}) already exists.")
            if "ix_product_identifiers_type_val" in err_msg or "product_identifiers" in err_msg:
                raise ValueError("This SKU or barcode is already assigned to another product or variant.")
            raise ValueError(f"Database constraint violation: {err_msg}")

    @classmethod
    def update_variant(
        cls, db: Session, variant: ProductVariant, variant_in: VariantUpdate
    ) -> ProductVariant:
        """Update variant attributes including size, color, SKU, barcode, price override."""
        new_size_raw = variant_in.size.strip() if variant_in.size is not None else variant.size
        new_color_raw = variant_in.color.strip() if variant_in.color is not None else variant.color

        size_upper = new_size_raw.upper()
        if size_upper in ("XS", "S", "M", "L", "XL", "XXL", "2XL", "3XL", "4XL", "5XL", "6XL"):
            new_size = size_upper
        elif size_upper in ("FREE SIZE", "FREESIZE"):
            new_size = "Free Size"
        else:
            new_size = new_size_raw

        new_color = new_color_raw.title() if new_color_raw.lower() in ("standard", "black", "white", "blue", "navy", "grey") else new_color_raw

        if new_size != variant.size or new_color != variant.color:
            existing_combo = db.scalar(
                select(ProductVariant.id).where(
                    and_(
                        ProductVariant.product_id == variant.product_id,
                        func.upper(ProductVariant.size) == new_size.upper(),
                        func.upper(ProductVariant.color) == new_color.upper(),
                        ProductVariant.id != variant.id,
                    )
                )
            )
            if existing_combo:
                raise ValueError(f"Variant combination ({new_size}, {new_color}) already exists.")
            variant.size = new_size
            variant.color = new_color

        if variant_in.sku is not None:
            new_sku = variant_in.sku.strip().upper()
            if not new_sku:
                raise ValueError("Variant requires a valid non-empty SKU.")
            variant.sku = new_sku

        if variant_in.barcode is not None:
            variant.barcode = (
                variant_in.barcode.strip().upper() if variant_in.barcode.strip() else None
            )

        if variant_in.price_override is not None:
            variant.price_override = variant_in.price_override

        if variant_in.is_active is not None:
            variant.is_active = variant_in.is_active

        try:
            db.commit()
            db.refresh(variant)
            return variant
        except IntegrityError as e:
            db.rollback()
            err_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            if "ix_product_identifiers_type_val" in err_msg or "product_identifiers" in err_msg:
                raise ValueError("This SKU or barcode is already assigned to another product or variant.")
            raise ValueError(f"Constraint violation: {err_msg}")

    @classmethod
    def delete_variant(cls, db: Session, variant: ProductVariant) -> None:
        """Hard-delete variant only if no historical sales or transactions exist."""
        sales_count = db.scalar(
            select(func.count(BillItem.id)).where(BillItem.variant_id == variant.id)
        ) or 0
        if sales_count > 0:
            raise ValueError(
                f"Cannot delete variant '{variant.sku}' because it has {sales_count} historical sales records. "
                "Deactivate the variant instead."
            )

        non_initial_movements = db.scalar(
            select(func.count(StockMovement.id)).where(
                and_(
                    StockMovement.variant_id == variant.id,
                    StockMovement.reference_type != "INITIAL_STOCK",
                )
            )
        ) or 0
        if non_initial_movements > 0:
            raise ValueError(
                f"Cannot delete variant '{variant.sku}' because it has active inventory transactions. "
                "Deactivate the variant instead."
            )

        db.query(StockMovement).filter(StockMovement.variant_id == variant.id).delete()
        db.query(Inventory).filter(Inventory.variant_id == variant.id).delete()
        db.delete(variant)
        db.commit()

    # --------------------------------------------------------------------------
    # Helper Serialization
    # --------------------------------------------------------------------------
    @staticmethod
    def _build_product_out(product: Product) -> ProductOut:
        """Convert Product ORM instance into public ProductOut response schema."""
        variants_out: List[VariantOut] = []
        total_stock = 0

        if product.product_type == "SIMPLE":
            if product.inventory:
                total_stock = product.inventory[0].quantity if isinstance(product.inventory, list) and product.inventory else (product.inventory.quantity if hasattr(product.inventory, "quantity") else 0)
        else:
            for v in product.variants:
                v_stock = 0
                v_thresh = 5
                if v.inventory:
                    inv_rec = v.inventory[0] if isinstance(v.inventory, list) and v.inventory else (v.inventory if hasattr(v.inventory, "quantity") else None)
                    if inv_rec:
                        v_stock = inv_rec.quantity
                        v_thresh = inv_rec.low_stock_threshold
                total_stock += v_stock
                variants_out.append(
                    VariantOut(
                        id=v.id,
                        product_id=v.product_id,
                        size=v.size,
                        color=v.color,
                        sku=v.sku,
                        barcode=v.barcode,
                        price_override=v.price_override,
                        is_active=v.is_active,
                        current_stock=v_stock,
                        low_stock_threshold=v_thresh,
                        created_at=v.created_at,
                        updated_at=v.updated_at,
                    )
                )

        return ProductOut(
            id=product.id,
            product_name=product.product_name,
            product_code=product.product_code,
            category_id=product.category_id,
            subcategory_id=product.subcategory_id,
            brand=product.brand,
            product_type=product.product_type,
            base_price=product.base_price,
            cost_price=product.cost_price,
            description=product.description,
            product_image_url=product.product_image_url,
            is_active=product.is_active,
            is_archived=product.is_archived,
            sku=product.sku,
            barcode=product.barcode,
            category_name=product.category.name if product.category else None,
            subcategory_name=product.subcategory.name if product.subcategory else None,
            current_stock=total_stock,
            variants=variants_out,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )
