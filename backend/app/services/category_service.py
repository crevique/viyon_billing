"""Business logic for Category and Subcategory operations."""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.category import Category, Subcategory
from app.models.product import Product
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryOut,
    SubcategoryCreate,
    SubcategoryUpdate,
    SubcategoryOut,
)


class CategoryService:
    """Service providing category and subcategory catalogue management."""

    # --------------------------------------------------------------------------
    # Category Operations
    # --------------------------------------------------------------------------
    @staticmethod
    def list_categories(
        db: Session,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> List[CategoryOut]:
        """Retrieve categories with subcategory and product counts."""
        query = select(Category)
        filters = []
        if is_active is not None:
            filters.append(Category.is_active == is_active)
        if search:
            filters.append(Category.name.ilike(f"%{search.strip()}%"))
        if filters:
            query = query.where(and_(*filters))

        query = query.order_by(Category.name.asc())
        categories = db.scalars(query).all()

        results: List[CategoryOut] = []
        for cat in categories:
            subcat_count = db.scalar(
                select(func.count(Subcategory.id)).where(Subcategory.category_id == cat.id)
            ) or 0
            prod_count = db.scalar(
                select(func.count(Product.id)).where(Product.category_id == cat.id)
            ) or 0
            results.append(
                CategoryOut(
                    id=cat.id,
                    name=cat.name,
                    description=cat.description,
                    is_active=cat.is_active,
                    created_at=cat.created_at,
                    updated_at=cat.updated_at,
                    subcategories_count=subcat_count,
                    products_count=prod_count,
                )
            )
        return results

    @staticmethod
    def get_category_by_id(db: Session, category_id: UUID) -> Optional[Category]:
        """Fetch category by UUID."""
        return db.scalar(select(Category).where(Category.id == category_id))

    @staticmethod
    def get_category_by_name(db: Session, name: str) -> Optional[Category]:
        """Fetch category by exact case-insensitive name."""
        return db.scalar(
            select(Category).where(func.lower(Category.name) == name.strip().lower())
        )

    @classmethod
    def create_category(cls, db: Session, category_in: CategoryCreate) -> Category:
        """Create a new category ensuring name uniqueness."""
        name = category_in.name.strip()
        if cls.get_category_by_name(db, name):
            raise ValueError(f"Category '{name}' already exists.")

        category = Category(
            name=name,
            description=category_in.description.strip() if category_in.description else None,
            is_active=category_in.is_active,
        )
        db.add(category)
        db.commit()
        db.refresh(category)
        return category

    @classmethod
    def update_category(
        cls, db: Session, category: Category, category_in: CategoryUpdate
    ) -> Category:
        """Update category attributes ensuring uniqueness if name changed."""
        if category_in.name is not None:
            new_name = category_in.name.strip()
            if new_name.lower() != category.name.lower():
                existing = cls.get_category_by_name(db, new_name)
                if existing and existing.id != category.id:
                    raise ValueError(f"Category '{new_name}' already exists.")
                category.name = new_name

        if category_in.description is not None:
            category.description = (
                category_in.description.strip() if category_in.description else None
            )

        if category_in.is_active is not None:
            category.is_active = category_in.is_active

        db.commit()
        db.refresh(category)
        return category

    @staticmethod
    def delete_category(db: Session, category: Category) -> None:
        """Delete category if no products or subcategories reference it."""
        prod_count = db.scalar(
            select(func.count(Product.id)).where(Product.category_id == category.id)
        ) or 0
        if prod_count > 0:
            raise ValueError(
                f"Cannot delete category '{category.name}' because {prod_count} product(s) are currently assigned to it. "
                "Please reassign or delete these products first in Product Catalogue before deleting this category."
            )

        subcat_count = db.scalar(
            select(func.count(Subcategory.id)).where(Subcategory.category_id == category.id)
        ) or 0
        if subcat_count > 0:
            raise ValueError(
                f"Cannot delete category '{category.name}' because it contains {subcat_count} subcategories. "
                "Please delete or reassign its subcategories first."
            )

        db.delete(category)
        db.commit()

    # --------------------------------------------------------------------------
    # Subcategory Operations
    # --------------------------------------------------------------------------
    @staticmethod
    def list_subcategories(
        db: Session,
        category_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
    ) -> List[SubcategoryOut]:
        """List subcategories with parent category name."""
        query = select(Subcategory, Category.name.label("category_name")).join(
            Category, Subcategory.category_id == Category.id
        )
        filters = []
        if category_id is not None:
            filters.append(Subcategory.category_id == category_id)
        if is_active is not None:
            filters.append(Subcategory.is_active == is_active)
        if filters:
            query = query.where(and_(*filters))

        query = query.order_by(Category.name.asc(), Subcategory.name.asc())
        rows = db.execute(query).all()

        return [
            SubcategoryOut(
                id=subcat.id,
                category_id=subcat.category_id,
                category_name=cat_name,
                name=subcat.name,
                description=subcat.description,
                is_active=subcat.is_active,
                created_at=subcat.created_at,
                updated_at=subcat.updated_at,
            )
            for subcat, cat_name in rows
        ]

    @staticmethod
    def get_subcategory_by_id(db: Session, subcategory_id: UUID) -> Optional[Subcategory]:
        """Fetch subcategory by UUID."""
        return db.scalar(select(Subcategory).where(Subcategory.id == subcategory_id))

    @staticmethod
    def get_subcategory_by_name_and_category(
        db: Session, name: str, category_id: UUID
    ) -> Optional[Subcategory]:
        """Check duplicate subcategory name within the same parent category."""
        return db.scalar(
            select(Subcategory).where(
                and_(
                    func.lower(Subcategory.name) == name.strip().lower(),
                    Subcategory.category_id == category_id,
                )
            )
        )

    @classmethod
    def create_subcategory(
        cls, db: Session, subcat_in: SubcategoryCreate
    ) -> Subcategory:
        """Create a new subcategory verifying parent category and uniqueness."""
        category = cls.get_category_by_id(db, subcat_in.category_id)
        if not category:
            raise ValueError(f"Parent category with ID '{subcat_in.category_id}' does not exist.")

        name = subcat_in.name.strip()
        if cls.get_subcategory_by_name_and_category(db, name, category.id):
            raise ValueError(
                f"Subcategory '{name}' already exists under category '{category.name}'."
            )

        subcategory = Subcategory(
            category_id=category.id,
            name=name,
            description=subcat_in.description.strip() if subcat_in.description else None,
            is_active=subcat_in.is_active,
        )
        db.add(subcategory)
        db.commit()
        db.refresh(subcategory)
        return subcategory

    @classmethod
    def update_subcategory(
        cls, db: Session, subcategory: Subcategory, subcat_in: SubcategoryUpdate
    ) -> Subcategory:
        """Update subcategory attributes and handle name/category changes."""
        target_category_id = subcategory.category_id

        if subcat_in.category_id is not None and subcat_in.category_id != subcategory.category_id:
            # Verify target category exists
            target_cat = cls.get_category_by_id(db, subcat_in.category_id)
            if not target_cat:
                raise ValueError(f"Category with ID '{subcat_in.category_id}' does not exist.")

            # Check if any products reference the old (subcategory_id, category_id)
            prod_count = db.scalar(
                select(func.count(Product.id)).where(Product.subcategory_id == subcategory.id)
            ) or 0
            if prod_count > 0:
                raise ValueError(
                    f"Cannot move subcategory '{subcategory.name}' to a new category because {prod_count} products "
                    "already reference it under the current category."
                )
            target_category_id = subcat_in.category_id
            subcategory.category_id = target_category_id

        new_name = subcat_in.name.strip() if subcat_in.name is not None else subcategory.name
        if (
            new_name.lower() != subcategory.name.lower()
            or target_category_id != subcategory.category_id
        ):
            existing = cls.get_subcategory_by_name_and_category(db, new_name, target_category_id)
            if existing and existing.id != subcategory.id:
                raise ValueError(
                    f"Subcategory '{new_name}' already exists under the selected category."
                )
            subcategory.name = new_name

        if subcat_in.description is not None:
            subcategory.description = (
                subcat_in.description.strip() if subcat_in.description else None
            )

        if subcat_in.is_active is not None:
            subcategory.is_active = subcat_in.is_active

        db.commit()
        db.refresh(subcategory)
        return subcategory

    @staticmethod
    def delete_subcategory(db: Session, subcategory: Subcategory) -> None:
        """Delete subcategory if no products reference it."""
        prod_count = db.scalar(
            select(func.count(Product.id)).where(Product.subcategory_id == subcategory.id)
        ) or 0
        if prod_count > 0:
            raise ValueError(
                f"Cannot delete subcategory '{subcategory.name}' because {prod_count} products reference it. "
                "Deactivate the subcategory instead."
            )

        db.delete(subcategory)
        db.commit()
