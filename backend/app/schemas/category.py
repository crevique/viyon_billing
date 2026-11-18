"""Pydantic schemas for Category and Subcategory management."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ------------------------------------------------------------------------------
# Category Schemas
# ------------------------------------------------------------------------------
class CategoryBase(BaseModel):
    """Shared category attributes."""

    name: str = Field(..., min_length=1, max_length=100, description="Unique category name")
    description: Optional[str] = Field(default=None, description="Optional category description")
    is_active: bool = Field(default=True, description="Whether category is active")


class CategoryCreate(CategoryBase):
    """Schema for creating a new category."""
    pass


class CategoryUpdate(BaseModel):
    """Schema for updating an existing category."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryOut(CategoryBase):
    """Public category response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
    subcategories_count: Optional[int] = Field(default=0, description="Number of subcategories")
    products_count: Optional[int] = Field(default=0, description="Number of products")


# ------------------------------------------------------------------------------
# Subcategory Schemas
# ------------------------------------------------------------------------------
class SubcategoryBase(BaseModel):
    """Shared subcategory attributes."""

    name: str = Field(..., min_length=1, max_length=100, description="Subcategory name")
    description: Optional[str] = Field(default=None, description="Optional subcategory description")
    is_active: bool = Field(default=True, description="Whether subcategory is active")


class SubcategoryCreate(SubcategoryBase):
    """Schema for creating a new subcategory."""

    category_id: UUID = Field(..., description="ID of the parent category")


class SubcategoryUpdate(BaseModel):
    """Schema for updating an existing subcategory."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class SubcategoryOut(SubcategoryBase):
    """Public subcategory response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID
    category_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
