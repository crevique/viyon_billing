"""Comprehensive integration test suite for Phase 3: Catalogue & Inventory Management.

Runs strictly against the isolated PostgreSQL container:
postgresql://postgres:postgres@localhost:5433/viyon_test_fresh

Guarantees 100% isolation: Neon production database is NEVER connected to or modified.
Tests all FastAPI endpoints, SQLAlchemy models, PostgreSQL triggers, constraints,
and role-based permissions (OWNER vs STAFF).
"""

import sys
from pathlib import Path
from decimal import Decimal
from uuid import uuid4

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import psycopg

from app.core.security import create_access_token, get_password_hash
from app.database.connection import get_db
from app.main import app as fastapi_app
from app.models.user import User

TEST_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/viyon_test_fresh"

# Setup engine connecting ONLY to the isolated PostgreSQL 16 container
engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


fastapi_app.dependency_overrides[get_db] = override_get_db
client = TestClient(fastapi_app)


def clean_test_tables():
    """Wipe catalogue and inventory test data in isolated test database."""
    raw_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(raw_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                TRUNCATE TABLE stock_movements CASCADE;
                TRUNCATE TABLE inventory CASCADE;
                TRUNCATE TABLE product_variants CASCADE;
                TRUNCATE TABLE products CASCADE;
                TRUNCATE TABLE product_identifiers CASCADE;
                TRUNCATE TABLE subcategories CASCADE;
                TRUNCATE TABLE categories CASCADE;
                TRUNCATE TABLE users CASCADE;
            """)
        conn.commit()


def seed_test_users():
    """Seed test Owner and Staff users in isolated database."""
    db = TestingSessionLocal()
    try:
        owner = User(
            id=uuid4(),
            full_name="Store Owner",
            email="owner@test.store",
            password_hash=get_password_hash("OwnerSecurePass123!"),
            role="OWNER",
            is_active=True,
        )
        staff = User(
            id=uuid4(),
            full_name="Billing Staff",
            email="staff@test.store",
            password_hash=get_password_hash("StaffSecurePass123!"),
            role="STAFF",
            is_active=True,
        )
        db.add_all([owner, staff])
        db.commit()
        db.refresh(owner)
        db.refresh(staff)

        owner_token = create_access_token(subject=str(owner.id), role="OWNER")
        staff_token = create_access_token(subject=str(staff.id), role="STAFF")
        return (
            owner,
            staff,
            {"Authorization": f"Bearer {owner_token}"},
            {"Authorization": f"Bearer {staff_token}"},
        )
    finally:
        db.close()


def run_phase3_test_suite():
    print("=" * 80)
    print("VIYON PHASE 3: CATALOGUE & INVENTORY BACKEND TEST SUITE")
    print("Target DB: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh)")
    print("=" * 80)

    clean_test_tables()
    owner, staff, owner_auth, staff_auth = seed_test_users()

    # ==========================================================================
    # 1. CATEGORY TESTS
    # ==========================================================================
    print("\n[TEST 1] Category Creation (Owner Only)...")
    cat_payload = {
        "name": "Men's Formal Wear",
        "description": "Suits, Shirts and Trousers",
        "is_active": True,
    }
    # Staff attempt -> 403
    res_staff = client.post("/api/v1/categories", json=cat_payload, headers=staff_auth)
    assert res_staff.status_code == status.HTTP_403_FORBIDDEN
    print("         Staff blocked: 403 Forbidden")

    # Owner attempt -> 201
    res_owner = client.post("/api/v1/categories", json=cat_payload, headers=owner_auth)
    assert res_owner.status_code == status.HTTP_201_CREATED
    cat1 = res_owner.json()
    cat1_id = cat1["id"]
    assert cat1["name"] == "Men's Formal Wear"
    print(f"         Owner created category: {cat1['name']} (ID: {cat1_id})")

    # Duplicate category name rejection -> 409
    print("\n[TEST 2] Duplicate Category Prevention...")
    res_dup = client.post(
        "/api/v1/categories",
        json={"name": "men's formal wear", "description": "Duplicate name"},
        headers=owner_auth,
    )
    assert res_dup.status_code == status.HTTP_409_CONFLICT
    print(f"         Duplicate rejected: 409 Conflict | {res_dup.json()['detail']}")

    # List categories
    print("\n[TEST 3] List Categories (Staff & Owner)...")
    res_list = client.get("/api/v1/categories", headers=staff_auth)
    assert res_list.status_code == status.HTTP_200_OK
    assert len(res_list.json()) >= 1
    print(f"         Staff retrieved {len(res_list.json())} active categories.")

    # Patch category
    print("\n[TEST 4] Update Category (Owner Only)...")
    res_patch = client.patch(
        f"/api/v1/categories/{cat1_id}",
        json={"description": "Updated Formal Clothing Description"},
        headers=owner_auth,
    )
    assert res_patch.status_code == status.HTTP_200_OK
    assert res_patch.json()["description"] == "Updated Formal Clothing Description"
    print("         Category updated successfully.")

    # ==========================================================================
    # 2. SUBCATEGORY TESTS
    # ==========================================================================
    print("\n[TEST 5] Subcategory Creation & Relationship...")
    subcat_payload = {
        "category_id": cat1_id,
        "name": "Formal Shirts",
        "description": "100% Cotton Business Shirts",
        "is_active": True,
    }
    # Staff attempt -> 403
    res_sub_staff = client.post("/api/v1/subcategories", json=subcat_payload, headers=staff_auth)
    assert res_sub_staff.status_code == status.HTTP_403_FORBIDDEN

    # Owner attempt -> 201
    res_sub_owner = client.post("/api/v1/subcategories", json=subcat_payload, headers=owner_auth)
    assert res_sub_owner.status_code == status.HTTP_201_CREATED
    subcat1 = res_sub_owner.json()
    subcat1_id = subcat1["id"]
    assert subcat1["category_name"] == "Men's Formal Wear"
    print(f"         Subcategory created: {subcat1['name']} under {subcat1['category_name']}")

    # Duplicate subcategory in same category -> 409
    print("\n[TEST 6] Duplicate Subcategory in Same Category Prevention...")
    res_sub_dup = client.post(
        "/api/v1/subcategories",
        json={"category_id": cat1_id, "name": "formal shirts"},
        headers=owner_auth,
    )
    assert res_sub_dup.status_code == status.HTTP_409_CONFLICT
    print(f"         Duplicate subcategory rejected: 409 Conflict | {res_sub_dup.json()['detail']}")

    # Nested subcategory listing
    res_nested = client.get(f"/api/v1/categories/{cat1_id}/subcategories", headers=staff_auth)
    assert res_nested.status_code == status.HTTP_200_OK
    assert len(res_nested.json()) == 1

    # ==========================================================================
    # 3. SIMPLE PRODUCT TESTS
    # ==========================================================================
    print("\n[TEST 7] Simple Product Creation with Initial Stock...")
    prod_simple_payload = {
        "product_name": "Executive White Shirt",
        "product_code": "VY-EWS-01",
        "category_id": cat1_id,
        "subcategory_id": subcat1_id,
        "brand": "VIYON SIGNATURE",
        "product_type": "SIMPLE",
        "base_price": 1499.00,
        "cost_price": 750.00,
        "description": "Premium wrinkle-free white shirt",
        "sku": "SKU-EWS-WHT",
        "barcode": "BAR-8901001",
        "initial_stock": 25,
        "low_stock_threshold": 5,
        "is_active": True,
    }
    res_prod1 = client.post("/api/v1/products", json=prod_simple_payload, headers=owner_auth)
    assert res_prod1.status_code == status.HTTP_201_CREATED
    prod1 = res_prod1.json()
    prod1_id = prod1["id"]
    assert prod1["product_type"] == "SIMPLE"
    assert prod1["sku"] == "SKU-EWS-WHT"
    assert prod1["current_stock"] == 25
    print(f"         Simple Product Created: {prod1['product_name']} | SKU: {prod1['sku']} | Stock: {prod1['current_stock']}")

    # Verify inventory row was created with variant_id = NULL
    res_inv1 = client.get(f"/api/v1/inventory/{prod1_id}", headers=owner_auth)
    assert res_inv1.status_code == status.HTTP_200_OK
    inv_data = res_inv1.json()
    assert len(inv_data) == 1
    assert inv_data[0]["variant_id"] is None
    assert inv_data[0]["quantity"] == 25
    print(f"         Verified Inventory Record: variant_id = NULL | qty = {inv_data[0]['quantity']}")

    # Cross-Category Subcategory Mismatch Rejection
    print("\n[TEST 8] Cross-Category Subcategory Rejection...")
    # Create a second category
    res_cat2 = client.post("/api/v1/categories", json={"name": "Women's Ethnic"}, headers=owner_auth)
    cat2_id = res_cat2.json()["id"]
    mismatch_payload = {
        "product_name": "Invalid Mismatch Item",
        "category_id": cat2_id,
        "subcategory_id": subcat1_id,  # belongs to cat1!
        "product_type": "SIMPLE",
        "base_price": 999.00,
        "sku": "SKU-MISMATCH-99",
    }
    res_mismatch = client.post("/api/v1/products", json=mismatch_payload, headers=owner_auth)
    assert res_mismatch.status_code == status.HTTP_409_CONFLICT
    print(f"         Cross-category mismatch rejected: 409 Conflict | {res_mismatch.json()['detail']}")

    # ==========================================================================
    # 4. VARIANT PRODUCT TESTS
    # ==========================================================================
    print("\n[TEST 9] Variant Product Creation with Variations...")
    prod_var_payload = {
        "product_name": "Premium Chino Trousers",
        "product_code": "VY-PCT-02",
        "category_id": cat1_id,
        "subcategory_id": subcat1_id,
        "brand": "VIYON CLASSIC",
        "product_type": "VARIANT",
        "base_price": 1899.00,
        "cost_price": 900.00,
        "variants": [
            {
                "size": "32",
                "color": "Navy",
                "sku": "PANT-NVY-32",
                "barcode": "BAR-PANT-01",
                "initial_stock": 10,
                "low_stock_threshold": 3,
            },
            {
                "size": "34",
                "color": "Navy",
                "sku": "PANT-NVY-34",
                "barcode": "BAR-PANT-02",
                "initial_stock": 15,
                "low_stock_threshold": 3,
            },
            {
                "size": "32",
                "color": "Beige",
                "sku": "PANT-BGE-32",
                "initial_stock": 8,
                "price_override": 1999.00,
            },
        ],
    }
    res_prod2 = client.post("/api/v1/products", json=prod_var_payload, headers=owner_auth)
    assert res_prod2.status_code == status.HTTP_201_CREATED
    prod2 = res_prod2.json()
    prod2_id = prod2["id"]
    assert prod2["product_type"] == "VARIANT"
    assert prod2["sku"] is None  # Parent does not claim variant SKU
    assert len(prod2["variants"]) == 3
    assert prod2["current_stock"] == 33  # 10 + 15 + 8
    print(f"         Variant Product Created: {prod2['product_name']} | 3 Variants | Total Stock: {prod2['current_stock']}")

    # ==========================================================================
    # 5. GLOBAL IDENTIFIER REGISTRY TESTS (SIMPLE vs VARIANT)
    # ==========================================================================
    print("\n[TEST 10] Cross-Entity Global SKU & Barcode Uniqueness...")
    # Attempt to create simple product reusing variant SKU 'PANT-NVY-32'
    conflict_simple = {
        "product_name": "Rogue Simple Pants",
        "category_id": cat1_id,
        "product_type": "SIMPLE",
        "base_price": 1200.00,
        "sku": "PANT-NVY-32",
    }
    res_conf = client.post("/api/v1/products", json=conflict_simple, headers=owner_auth)
    assert res_conf.status_code == status.HTTP_409_CONFLICT
    print(f"         Variant SKU collision on simple product rejected: 409 Conflict | {res_conf.json()['detail']}")

    # Attempt to add variant with SKU already used by simple product 'SKU-EWS-WHT'
    res_conf_var = client.post(
        f"/api/v1/products/{prod2_id}/variants",
        json={"size": "36", "color": "Navy", "sku": "SKU-EWS-WHT"},
        headers=owner_auth,
    )
    assert res_conf_var.status_code == status.HTTP_409_CONFLICT
    print(f"         Simple SKU collision on variant rejected: 409 Conflict | {res_conf_var.json()['detail']}")

    # ==========================================================================
    # 6. INVENTORY ADJUSTMENTS & LEDGER TESTS
    # ==========================================================================
    print("\n[TEST 11] Inventory Adjustments & Transactional Ledger...")
    # Positive adjustment on simple product (Stock Receipt)
    adj_payload = {
        "product_id": prod1_id,
        "variant_id": None,
        "quantity_change": 10,
        "movement_type": "PURCHASE",
        "reason": "Supplier shipment PO-9842 received",
    }
    res_adj = client.post("/api/v1/inventory/adjustments", json=adj_payload, headers=owner_auth)
    assert res_adj.status_code == status.HTTP_200_OK
    adj_data = res_adj.json()
    assert adj_data["previous_quantity"] == 25
    assert adj_data["new_quantity"] == 35
    assert adj_data["quantity_change"] == 10
    print(f"         Stock Added: 25 -> {adj_data['new_quantity']} | Movement: {adj_data['movement_type']}")

    # Negative adjustment (Damaged Stock)
    adj_sub = {
        "product_id": prod1_id,
        "variant_id": None,
        "quantity_change": -5,
        "movement_type": "ADJUSTMENT",
        "reason": "Water damage in storage",
    }
    res_adj_sub = client.post("/api/v1/inventory/adjustments", json=adj_sub, headers=owner_auth)
    assert res_adj_sub.status_code == status.HTTP_200_OK
    assert res_adj_sub.json()["new_quantity"] == 30
    print(f"         Stock Deducted: 35 -> 30")

    # Negative stock prevention (Cannot reduce below 0)
    print("\n[TEST 12] Negative Stock Prevention...")
    adj_excessive = {
        "product_id": prod1_id,
        "variant_id": None,
        "quantity_change": -100,  # Only 30 available
        "reason": "Accidental massive deduction",
    }
    res_neg = client.post("/api/v1/inventory/adjustments", json=adj_excessive, headers=owner_auth)
    assert res_neg.status_code == status.HTTP_400_BAD_REQUEST
    print(f"         Negative stock prevented: 400 Bad Request | {res_neg.json()['detail']}")

    # Staff forbidden from stock adjustment
    print("\n[TEST 13] Staff Blocked from Stock Adjustments...")
    res_staff_adj = client.post("/api/v1/inventory/adjustments", json=adj_payload, headers=staff_auth)
    assert res_staff_adj.status_code == status.HTTP_403_FORBIDDEN
    print("         Staff blocked: 403 Forbidden")

    # Low stock alert check
    print("\n[TEST 14] Low Stock Detection...")
    # Reduce variant stock down to threshold
    variant_navy_32_id = prod2["variants"][0]["id"]
    client.post(
        "/api/v1/inventory/adjustments",
        json={
            "product_id": prod2_id,
            "variant_id": variant_navy_32_id,
            "quantity_change": -8,  # 10 - 8 = 2 (threshold is 3)
            "reason": "Sales dispatch",
        },
        headers=owner_auth,
    )
    res_low = client.get("/api/v1/inventory/low-stock", headers=staff_auth)
    assert res_low.status_code == status.HTTP_200_OK
    low_items = res_low.json()["items"]
    assert any(item["sku"] == "PANT-NVY-32" and item["is_low_stock"] for item in low_items)
    print(f"         Low-stock alert caught variant: PANT-NVY-32 (qty <= threshold)")

    # Stock Movement Audit Ledger
    print("\n[TEST 15] Stock Movement Audit Ledger...")
    res_movements = client.get(f"/api/v1/inventory/movements?product_id={prod1_id}", headers=owner_auth)
    assert res_movements.status_code == status.HTTP_200_OK
    movements = res_movements.json()["items"]
    assert len(movements) >= 3  # Initial + Purchase + Adjustment
    assert all(m["created_by_user_name"] == "Store Owner" for m in movements)
    print(f"         Audit ledger verified: {len(movements)} movements recorded with user attribution.")

    # ==========================================================================
    # 7. PRODUCT ARCHIVE & RESTORE
    # ==========================================================================
    print("\n[TEST 16] Product Archive & Restore Lifecycle...")
    res_archive = client.post(f"/api/v1/products/{prod1_id}/archive", headers=owner_auth)
    assert res_archive.status_code == status.HTTP_200_OK
    assert res_archive.json()["is_archived"] is True
    assert res_archive.json()["is_active"] is False

    # Staff listing should exclude archived product by default
    res_staff_prods = client.get("/api/v1/products", headers=staff_auth)
    prod_ids = [p["id"] for p in res_staff_prods.json()["items"]]
    assert prod1_id not in prod_ids
    print("         Archived product automatically hidden from staff catalogue.")

    # Restore product
    res_restore = client.post(f"/api/v1/products/{prod1_id}/restore", headers=owner_auth)
    assert res_restore.status_code == status.HTTP_200_OK
    assert res_restore.json()["is_archived"] is False
    assert res_restore.json()["is_active"] is True
    print("         Product restored to active catalogue successfully.")

    # ==========================================================================
    # 8. SEARCH & PAGINATION
    # ==========================================================================
    print("\n[TEST 17] Search & Pagination...")
    res_search = client.get("/api/v1/products?search=chino", headers=staff_auth)
    assert res_search.status_code == status.HTTP_200_OK
    assert res_search.json()["total"] == 1
    assert res_search.json()["items"][0]["product_name"] == "Premium Chino Trousers"

    res_search_sku = client.get("/api/v1/products?search=PANT-NVY-32", headers=staff_auth)
    assert res_search_sku.status_code == status.HTTP_200_OK
    assert res_search_sku.json()["total"] == 1
    print("         Full-text search verified by product name and variant SKU.")

    # ==========================================================================
    # 9. DELETION RESTRICTIONS
    # ==========================================================================
    print("\n[TEST 18] Deletion Protection for Entities with History...")
    # Attempting to delete category cat1 which has subcategory and products
    res_del_cat = client.delete(f"/api/v1/categories/{cat1_id}", headers=owner_auth)
    assert res_del_cat.status_code == status.HTTP_409_CONFLICT
    print(f"         Category deletion blocked: 409 Conflict | {res_del_cat.json()['detail']}")

    # Attempting to delete product with inventory movements
    res_del_prod = client.delete(f"/api/v1/products/{prod1_id}", headers=owner_auth)
    assert res_del_prod.status_code == status.HTTP_409_CONFLICT
    print(f"         Product deletion with transactions blocked: 409 Conflict | {res_del_prod.json()['detail']}")

    clean_test_tables()
    print("\n" + "=" * 80)
    print("ALL 18 PHASE 3 CATALOGUE & INVENTORY TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 80)


if __name__ == "__main__":
    run_phase3_test_suite()
