"""Central API v1 router definition."""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    auth,
    users,
    staff,
    categories,
    subcategories,
    products,
    variants,
    inventory,
    bills,
    payments,
    expenses,
    finance,
    suppliers,
    purchases,
)

api_router = APIRouter()

# Health & System
api_router.include_router(health.router, prefix="/health", tags=["Health & System"])

# Authentication & Session
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Profile"])

# Staff Management (Phase 5.2 - Owner)
api_router.include_router(staff.router, prefix="/staff", tags=["Staff Management"])

# Legacy Users / Staff Management (Owner)
api_router.include_router(users.router, prefix="/users", tags=["Staff Management (Owner)"])

# Category Management
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])

# Subcategory Management
api_router.include_router(subcategories.router, prefix="/subcategories", tags=["Subcategories"])

# Product Management
api_router.include_router(products.router, prefix="/products", tags=["Products"])

# Variant Management
api_router.include_router(variants.router, prefix="/variants", tags=["Product Variants"])

# Inventory & Stock Movements
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory & Ledger"])

# In-Store Sales Billing & POS Checkout
api_router.include_router(bills.router, prefix="/bills", tags=["Sales Billing & Checkout"])

# Payment Management & Split Payments
api_router.include_router(payments.router, prefix="/payments", tags=["Payment Management"])

# Expense Management (Phase 4.6)
api_router.include_router(expenses.router, prefix="/expenses", tags=["Expenses"])

# Financial Management, Cash & Reports (Phase 4.6)
api_router.include_router(finance.router, prefix="/finance", tags=["Finance & Reports"])

# Supplier Management (Phase 5.4)
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["Suppliers"])

# Purchase Orders, Receiving & Supplier Payments (Phase 5.4)
api_router.include_router(purchases.router, prefix="/purchases", tags=["Purchasing & Goods Receipts"])
