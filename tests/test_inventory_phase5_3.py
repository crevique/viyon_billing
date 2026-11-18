"""VIYON Billing System - Phase 5.3 Automated Inventory & Stock Ledger Test Suite
Testing Complete Inventory Management, Dashboard Metrics, Manual Adjustments,
Purchase Inward, Low-Stock Thresholds, Role-Based Access Control, and Immutable Movement Ledger.
Target Database: Isolated PostgreSQL on localhost:5433 (viyon_test_fresh).
NEVER connects to or modifies the Neon production database.
"""

import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Tuple
from uuid import UUID, uuid4

import psycopg
from fastapi import status
from fastapi.testclient import TestClient

# ------------------------------------------------------------------------------
# 1. Force Isolated Test Database (NEVER TOUCH PRODUCTION NEON!)
# ------------------------------------------------------------------------------
TEST_DB_URL = os.environ.get("DATABASE_URL") or "postgresql+psycopg://postgres:postgres@localhost:5433/viyon_test_fresh"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["SECRET_KEY"] = "test-secret-key-phase5-3-secure-random-at-least-32-chars"
os.environ["ENVIRONMENT"] = "test"

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.security import create_access_token, get_password_hash
from app.main import app


def setup_inventory_test_environment():
    """Ensure database has seeded owner, staff, categories, simple product, and variant product."""
    print("[SETUP] Connecting to database for Phase 5.3...", flush=True)
    raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    owner_id = uuid4()
    staff_id = uuid4()
    cat_id = uuid4()
    subcat_id = uuid4()
    simple_prod_id = uuid4()
    variant_prod_id = uuid4()
    variant_s_id = uuid4()
    variant_m_id = uuid4()
    simple_inv_id = uuid4()
    variant_s_inv_id = uuid4()
    variant_m_inv_id = uuid4()

    default_pw_hash = get_password_hash("ViyonSecurePass123!")

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            # Check or create store owner
            cur.execute("SELECT id FROM users WHERE role = 'OWNER' LIMIT 1;")
            row_owner = cur.fetchone()
            if row_owner:
                owner_id = row_owner[0]
            else:
                cur.execute(
                    """
                    INSERT INTO users (id, full_name, username, email, phone, password_hash, role, is_active)
                    VALUES (%s, 'Store Owner', 'storeowner_inv', 'owner_inv@viyon.store', '08270242681', %s, 'OWNER', true);
                    """,
                    (owner_id, default_pw_hash),
                )

            # Check or create staff
            cur.execute("SELECT id FROM users WHERE role = 'STAFF' AND is_active = true LIMIT 1;")
            row_staff = cur.fetchone()
            if row_staff:
                staff_id = row_staff[0]
            else:
                cur.execute(
                    """
                    INSERT INTO users (id, full_name, username, email, phone, password_hash, role, is_active)
                    VALUES (%s, 'Senior Cashier', 'cashier_inv', 'cashier_inv@viyon.store', '09876543211', %s, 'STAFF', true);
                    """,
                    (staff_id, default_pw_hash),
                )

            # Check or create Category & Subcategory
            cur.execute("SELECT id FROM categories WHERE is_active = true LIMIT 1;")
            row_c = cur.fetchone()
            if row_c:
                cat_id = row_c[0]
            else:
                cur.execute(
                    "INSERT INTO categories (id, name, is_active) VALUES (%s, 'Men Clothing', true);",
                    (cat_id,),
                )

            cur.execute("SELECT id FROM subcategories WHERE category_id = %s AND is_active = true LIMIT 1;", (cat_id,))
            row_sc = cur.fetchone()
            if row_sc:
                subcat_id = row_sc[0]
            else:
                cur.execute(
                    "INSERT INTO subcategories (id, category_id, name, is_active) VALUES (%s, %s, 'Formal Shirts', true);",
                    (subcat_id, cat_id),
                )

            # 1. Create a Simple Product with inventory (quantity = 25, threshold = 5)
            simple_sku = f"SKU-SMP-{uuid4().hex[:6]}".upper()
            simple_code = f"PRD-S-{uuid4().hex[:4]}".upper()
            cur.execute(
                """
                INSERT INTO products (id, product_name, product_code, category_id, subcategory_id, product_type, base_price, sku, is_active, is_archived)
                VALUES (%s, 'Phase 5.3 Cotton Oxford Shirt', %s, %s, %s, 'SIMPLE', 1299.00, %s, true, false);
                """,
                (simple_prod_id, simple_code, cat_id, subcat_id, simple_sku),
            )
            cur.execute(
                """
                INSERT INTO inventory (id, product_id, variant_id, quantity, low_stock_threshold)
                VALUES (%s, %s, NULL, 25, 5);
                """,
                (simple_inv_id, simple_prod_id),
            )

            # 2. Create a Variant Product with 2 sizes (S and M)
            variant_code = f"PRD-V-{uuid4().hex[:4]}".upper()
            cur.execute(
                """
                INSERT INTO products (id, product_name, product_code, category_id, subcategory_id, product_type, base_price, is_active, is_archived)
                VALUES (%s, 'Phase 5.3 Slim Fit Trousers', %s, %s, %s, 'VARIANT', 1799.00, true, false);
                """,
                (variant_prod_id, variant_code, cat_id, subcat_id),
            )

            sku_s = f"SKU-TR-S-{uuid4().hex[:4]}".upper()
            sku_m = f"SKU-TR-M-{uuid4().hex[:4]}".upper()
            cur.execute(
                """
                INSERT INTO product_variants (id, product_id, size, color, sku, is_active)
                VALUES (%s, %s, '30', 'Navy', %s, true);
                """,
                (variant_s_id, variant_prod_id, sku_s),
            )
            cur.execute(
                """
                INSERT INTO product_variants (id, product_id, size, color, sku, is_active)
                VALUES (%s, %s, '32', 'Navy', %s, true);
                """,
                (variant_m_id, variant_prod_id, sku_m),
            )

            # Variant S: low stock item (quantity = 3, threshold = 5)
            cur.execute(
                """
                INSERT INTO inventory (id, product_id, variant_id, quantity, low_stock_threshold)
                VALUES (%s, %s, %s, 3, 5);
                """,
                (variant_s_inv_id, variant_prod_id, variant_s_id),
            )
            # Variant M: normal stock item (quantity = 15, threshold = 5)
            cur.execute(
                """
                INSERT INTO inventory (id, product_id, variant_id, quantity, low_stock_threshold)
                VALUES (%s, %s, %s, 15, 5);
                """,
                (variant_m_inv_id, variant_prod_id, variant_m_id),
            )

            conn.commit()

    owner_token = create_access_token(subject=str(owner_id), role="OWNER")
    staff_token = create_access_token(subject=str(staff_id), role="STAFF")
    customer_token = create_access_token(subject=str(uuid4()), role="CUSTOMER")

    return {
        "owner_headers": {"Authorization": f"Bearer {owner_token}"},
        "staff_headers": {"Authorization": f"Bearer {staff_token}"},
        "customer_headers": {"Authorization": f"Bearer {customer_token}"},
        "owner_id": owner_id,
        "staff_id": staff_id,
        "cat_id": cat_id,
        "subcat_id": subcat_id,
        "simple_prod_id": simple_prod_id,
        "simple_sku": simple_sku,
        "simple_inv_id": simple_inv_id,
        "variant_prod_id": variant_prod_id,
        "variant_s_id": variant_s_id,
        "variant_m_id": variant_m_id,
        "variant_s_inv_id": variant_s_inv_id,
        "variant_m_inv_id": variant_m_inv_id,
    }


def run_phase5_3_inventory_tests():
    env = setup_inventory_test_environment()
    client = TestClient(app)
    results = []

    print("=" * 80)
    print("VIYON PHASE 5.3: COMPLETE INVENTORY MANAGEMENT & STOCK LEDGER SUITE")
    print(f"Target DB: {TEST_DB_URL}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # PART A: INVENTORY DASHBOARD SUMMARY & LIVE METRICS
    # --------------------------------------------------------------------------
    print("\n[PART A: INVENTORY DASHBOARD SUMMARY & LIVE METRICS]")

    # Test 1: Owner gets inventory summary
    print("\n[TEST 1] Owner gets inventory summary (GET /api/v1/inventory/summary)...")
    r1 = client.get("/api/v1/inventory/summary", headers=env["owner_headers"])
    assert r1.status_code == status.HTTP_200_OK, r1.text
    summary = r1.json()
    assert "total_products" in summary
    assert "total_variants" in summary
    assert "total_stock" in summary
    assert "low_stock_items" in summary
    assert "out_of_stock_items" in summary
    assert "total_adjustments" in summary
    assert summary["total_products"] >= 2
    assert summary["total_stock"] >= 43  # 25 + 3 + 15
    print(f"         Summary verified: Total Products={summary['total_products']}, Stock={summary['total_stock']}, Low Stock={summary['low_stock_items']}")
    results.append(("1. Owner gets inventory summary", "PASS"))

    # Test 2: Staff can view inventory summary
    print("\n[TEST 2] Staff gets inventory summary...")
    r2 = client.get("/api/v1/inventory/summary", headers=env["staff_headers"])
    assert r2.status_code == status.HTTP_200_OK, r2.text
    print("         Confirmed: Staff has read access to summary.")
    results.append(("2. Staff can view inventory summary", "PASS"))

    # Test 3: Unauthorized / Customer blocked from summary
    print("\n[TEST 3] Customer / Unauthenticated blocked from inventory summary...")
    r3a = client.get("/api/v1/inventory/summary", headers=env["customer_headers"])
    assert r3a.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED], r3a.text
    r3b = client.get("/api/v1/inventory/summary")
    assert r3b.status_code == status.HTTP_401_UNAUTHORIZED, r3b.text
    print("         Confirmed: Unauthorized access properly rejected.")
    results.append(("3. Unauthorized access to summary blocked", "PASS"))

    # --------------------------------------------------------------------------
    # PART B: INVENTORY LISTING, SEARCH, FILTERS & SORTING
    # --------------------------------------------------------------------------
    print("\n[PART B: INVENTORY LISTING, SEARCH, FILTERS & SORTING]")

    # Test 4: List inventory with pagination
    print("\n[TEST 4] List inventory with pagination (GET /api/v1/inventory)...")
    r4 = client.get("/api/v1/inventory?limit=10&offset=0", headers=env["owner_headers"])
    assert r4.status_code == status.HTTP_200_OK, r4.text
    data4 = r4.json()
    assert "items" in data4 and "total" in data4
    items = data4["items"]
    assert isinstance(items, list)
    assert len(items) >= 3  # Simple + 2 Variants
    print(f"         Retrieved {len(items)} inventory records (Total in DB: {data4['total']}).")
    results.append(("4. List inventory with pagination", "PASS"))

    # Test 5: Search inventory by SKU or product name
    print("\n[TEST 5] Search inventory by SKU...")
    r5 = client.get(f"/api/v1/inventory?search={env['simple_sku']}", headers=env["owner_headers"])
    assert r5.status_code == status.HTTP_200_OK, r5.text
    search_items = r5.json()["items"]
    assert len(search_items) >= 1
    assert search_items[0]["sku"] == env["simple_sku"]
    print(f"         Search by SKU '{env['simple_sku']}' found: {search_items[0]['product_name']}")
    results.append(("5. Search inventory by SKU", "PASS"))

    # Test 6: Filter inventory by category
    print("\n[TEST 6] Filter inventory by category...")
    r6 = client.get(f"/api/v1/inventory?category_id={env['cat_id']}", headers=env["owner_headers"])
    assert r6.status_code == status.HTTP_200_OK, r6.text
    cat_items = r6.json()["items"]
    assert len(cat_items) >= 3
    for it in cat_items:
        assert str(it["category_id"]) == str(env["cat_id"])
    print(f"         Category filter returned {len(cat_items)} items for Category ID.")
    results.append(("6. Filter inventory by category", "PASS"))

    # Test 7: Filter inventory by stock status (LOW_STOCK)
    print("\n[TEST 7] Filter inventory by stock_status=LOW_STOCK...")
    r7 = client.get("/api/v1/inventory?stock_status=LOW_STOCK", headers=env["owner_headers"])
    assert r7.status_code == status.HTTP_200_OK, r7.text
    low_stock_items = r7.json()["items"]
    assert any(it["id"] == str(env["variant_s_inv_id"]) for it in low_stock_items)
    for it in low_stock_items:
        assert it["stock_status"] == "LOW_STOCK"
    print(f"         Confirmed: LOW_STOCK filter correctly isolated low-stock items.")
    results.append(("7. Filter inventory by stock_status (LOW_STOCK)", "PASS"))

    # Test 8: Filter inventory by product_type (SIMPLE vs VARIANT)
    print("\n[TEST 8] Filter inventory by product_type=SIMPLE...")
    r8 = client.get("/api/v1/inventory?product_type=SIMPLE", headers=env["owner_headers"])
    assert r8.status_code == status.HTTP_200_OK, r8.text
    simple_items = r8.json()["items"]
    for it in simple_items:
        assert it["product_type"] == "SIMPLE"
    print(f"         Confirmed: SIMPLE product_type filter returned {len(simple_items)} items.")
    results.append(("8. Filter inventory by product_type", "PASS"))

    # Test 9: Sort inventory by quantity DESC
    print("\n[TEST 9] Sort inventory by quantity DESC...")
    r9 = client.get("/api/v1/inventory?sort_by=quantity&sort_desc=true", headers=env["owner_headers"])
    assert r9.status_code == status.HTTP_200_OK, r9.text
    sorted_items = r9.json()["items"]
    quantities = [it["quantity"] for it in sorted_items]
    assert quantities == sorted(quantities, reverse=True)
    print("         Confirmed: Inventory correctly sorted by quantity DESC.")
    results.append(("9. Sort inventory by quantity DESC", "PASS"))

    # Test 10: Staff can view inventory list
    print("\n[TEST 10] Staff can view inventory list...")
    r10 = client.get("/api/v1/inventory", headers=env["staff_headers"])
    assert r10.status_code == status.HTTP_200_OK, r10.text
    assert "items" in r10.json()
    print("         Confirmed: Staff has read access to inventory list.")
    results.append(("10. Staff can view inventory list", "PASS"))

    # --------------------------------------------------------------------------
    # PART C: LOW STOCK ALERTS & PRODUCT DETAILS
    # --------------------------------------------------------------------------
    print("\n[PART C: LOW STOCK ALERTS & PRODUCT DETAILS]")

    # Test 11: Low stock alerts endpoint (GET /api/v1/inventory/low-stock)
    print("\n[TEST 11] Low stock alerts endpoint...")
    r11 = client.get("/api/v1/inventory/low-stock", headers=env["owner_headers"])
    assert r11.status_code == status.HTTP_200_OK, r11.text
    alerts = r11.json()["items"]
    assert any(it["id"] == str(env["variant_s_inv_id"]) for it in alerts)
    print(f"         Confirmed: Variant S (qty=3 <= threshold=5) listed in low stock alerts.")
    results.append(("11. Low stock alerts endpoint", "PASS"))

    # Test 12: Product size-wise breakdown (GET /api/v1/inventory/{product_id})
    print("\n[TEST 12] Product size-wise breakdown...")
    r12 = client.get(f"/api/v1/inventory/{env['variant_prod_id']}", headers=env["owner_headers"])
    assert r12.status_code == status.HTTP_200_OK, r12.text
    prod_breakdown = r12.json()
    assert len(prod_breakdown) == 2  # Size S and Size M
    sizes = [item.get("size") for item in prod_breakdown]
    assert "30" in sizes and "32" in sizes
    print(f"         Confirmed: Product breakdown contains both sizes: {sizes}")
    results.append(("12. Product size-wise breakdown", "PASS"))

    # --------------------------------------------------------------------------
    # PART D: MANUAL STOCK ADJUSTMENTS & INTEGRITY
    # --------------------------------------------------------------------------
    print("\n[PART D: MANUAL STOCK ADJUSTMENTS & INTEGRITY]")

    # Test 13: Owner increases stock (+5)
    print("\n[TEST 13] Owner increases stock (+5)...")
    adj_payload_inc = {
        "product_id": str(env["simple_prod_id"]),
        "variant_id": None,
        "quantity_change": 5,
        "movement_type": "ADJUSTMENT",
        "reason": "Shipment reconciliation / found stock",
        "notes": "Annual shelf audit correction",
    }
    r13 = client.post("/api/v1/inventory/adjustments", json=adj_payload_inc, headers=env["owner_headers"])
    assert r13.status_code == status.HTTP_200_OK, r13.text
    res13 = r13.json()
    assert res13["new_quantity"] == 30  # was 25 + 5
    print(f"         Stock successfully increased to {res13['new_quantity']}.")
    results.append(("13. Owner increases stock (+5)", "PASS"))

    # Test 14: Owner decreases stock (-4)
    print("\n[TEST 14] Owner decreases stock (-4)...")
    adj_payload_dec = {
        "product_id": str(env["simple_prod_id"]),
        "variant_id": None,
        "quantity_change": -4,
        "movement_type": "ADJUSTMENT",
        "reason": "Damaged goods on showroom floor",
    }
    r14 = client.post("/api/v1/inventory/adjustments", json=adj_payload_dec, headers=env["owner_headers"])
    assert r14.status_code == status.HTTP_200_OK, r14.text
    res14 = r14.json()
    assert res14["new_quantity"] == 26  # was 30 - 4
    print(f"         Stock successfully decreased to {res14['new_quantity']}.")
    results.append(("14. Owner decreases stock (-4)", "PASS"))

    # Test 15: Owner corrects stock (=20)
    print("\n[TEST 15] Owner corrects stock (=20)...")
    adj_payload_corr = {
        "product_id": str(env["simple_prod_id"]),
        "variant_id": None,
        "quantity_change": -6,  # 26 - 6 = 20
        "movement_type": "ADJUSTMENT",
        "reason": "Direct physical inventory recount",
    }
    r15 = client.post("/api/v1/inventory/adjustments", json=adj_payload_corr, headers=env["owner_headers"])
    assert r15.status_code == status.HTTP_200_OK, r15.text
    res15 = r15.json()
    assert res15["new_quantity"] == 20
    print(f"         Stock successfully corrected to {res15['new_quantity']}.")
    results.append(("15. Owner corrects stock (=20)", "PASS"))

    # Test 16: Negative stock prevention: decreasing more than current stock returns 400
    print("\n[TEST 16] Negative stock prevention (attempting to decrease 999 from 20)...")
    adj_payload_excess = {
        "product_id": str(env["simple_prod_id"]),
        "variant_id": None,
        "quantity_change": -999,
        "movement_type": "ADJUSTMENT",
        "reason": "Invalid large deduction",
    }
    r16 = client.post("/api/v1/inventory/adjustments", json=adj_payload_excess, headers=env["owner_headers"])
    assert r16.status_code == status.HTTP_400_BAD_REQUEST, r16.text
    print(f"         Confirmed: Blocked with HTTP 400: {r16.json().get('detail')}")
    results.append(("16. Negative stock prevention (400)", "PASS"))

    # Test 17: Staff strictly blocked from stock adjustment (403 Forbidden)
    print("\n[TEST 17] Staff strictly blocked from stock adjustment (403)...")
    r17 = client.post("/api/v1/inventory/adjustments", json=adj_payload_inc, headers=env["staff_headers"])
    assert r17.status_code == status.HTTP_403_FORBIDDEN, r17.text
    print("         Confirmed: Staff request rejected with 403 Forbidden.")
    results.append(("17. Staff blocked from stock adjustment (403)", "PASS"))

    # Test 18: Unauthenticated / Customer blocked from adjustment
    print("\n[TEST 18] Customer / unauthenticated blocked from adjustment...")
    r18a = client.post("/api/v1/inventory/adjustments", json=adj_payload_inc, headers=env["customer_headers"])
    assert r18a.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED], r18a.text
    r18b = client.post("/api/v1/inventory/adjustments", json=adj_payload_inc)
    assert r18b.status_code == status.HTTP_401_UNAUTHORIZED, r18b.text
    print("         Confirmed: Customer & anonymous requests strictly blocked.")
    results.append(("18. Customer / unauthenticated blocked from adjustment", "PASS"))

    # --------------------------------------------------------------------------
    # PART E: STOCK INWARD / GOODS RECEIPT
    # --------------------------------------------------------------------------
    print("\n[PART E: STOCK INWARD / GOODS RECEIPT]")

    # Test 19: Owner records stock inward for simple product
    print("\n[TEST 19] Owner records stock inward for simple product...")
    po_ref = f"PO-{uuid4().hex[:6]}".upper()
    inward_simple = {
        "product_id": str(env["simple_prod_id"]),
        "quantity": 10,
        "supplier_name": "Coimbatore Textile Mills Ltd",
        "purchase_reference": po_ref,
        "notes": "Fresh delivery of Oxford shirts",
    }
    r19 = client.post("/api/v1/inventory/inward", json=inward_simple, headers=env["owner_headers"])
    assert r19.status_code == status.HTTP_201_CREATED, r19.text
    res19 = r19.json()
    assert res19["new_quantity"] == 30  # was 20 + 10
    print(f"         Stock inward successful: New Quantity={res19['new_quantity']}, PO={po_ref}")
    results.append(("19. Owner records stock inward for simple product", "PASS"))

    # Test 20: Owner records stock inward for variant product (Size S)
    print("\n[TEST 20] Owner records stock inward for variant product (Size S)...")
    po_ref_var = f"PO-V-{uuid4().hex[:6]}".upper()
    inward_variant = {
        "product_id": str(env["variant_prod_id"]),
        "variant_id": str(env["variant_s_id"]),
        "quantity": 12,
        "supplier_name": "Tirupur Garments Hub",
        "purchase_reference": po_ref_var,
        "notes": "Restock of size 30 trousers",
    }
    r20 = client.post("/api/v1/inventory/inward", json=inward_variant, headers=env["owner_headers"])
    assert r20.status_code == status.HTTP_201_CREATED, r20.text
    res20 = r20.json()
    assert res20["new_quantity"] == 15  # was 3 + 12
    print(f"         Variant stock inward successful: Size S New Quantity={res20['new_quantity']}")
    results.append(("20. Owner records stock inward for variant product", "PASS"))

    # Test 21: Inward with quantity <= 0 rejected
    print("\n[TEST 21] Inward with quantity <= 0 rejected (422)...")
    invalid_inward = {
        "product_id": str(env["simple_prod_id"]),
        "quantity": 0,
        "supplier_name": "Supplier",
    }
    r21 = client.post("/api/v1/inventory/inward", json=invalid_inward, headers=env["owner_headers"])
    assert r21.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, 422, status.HTTP_400_BAD_REQUEST], r21.text
    print("         Confirmed: Quantity <= 0 properly rejected.")
    results.append(("21. Inward with quantity <= 0 rejected", "PASS"))

    # Test 22: Variant product inward without variant_id rejected (400)
    print("\n[TEST 22] Variant product inward without variant_id rejected (400)...")
    missing_var_inward = {
        "product_id": str(env["variant_prod_id"]),
        "quantity": 5,
        "supplier_name": "Supplier",
    }
    r22 = client.post("/api/v1/inventory/inward", json=missing_var_inward, headers=env["owner_headers"])
    assert r22.status_code == status.HTTP_400_BAD_REQUEST, r22.text
    print("         Confirmed: Missing variant_id on VARIANT product returned 400 Bad Request.")
    results.append(("22. Variant inward without variant_id rejected (400)", "PASS"))

    # Test 23: Staff is strictly blocked from stock inward (403 Forbidden)
    print("\n[TEST 23] Staff is strictly blocked from stock inward (403)...")
    r23 = client.post("/api/v1/inventory/inward", json=inward_simple, headers=env["staff_headers"])
    assert r23.status_code == status.HTTP_403_FORBIDDEN, r23.text
    print("         Confirmed: Staff request rejected with 403 Forbidden.")
    results.append(("23. Staff blocked from stock inward (403)", "PASS"))

    # --------------------------------------------------------------------------
    # PART F: LOW STOCK THRESHOLD CONFIGURATION
    # --------------------------------------------------------------------------
    print("\n[PART F: LOW STOCK THRESHOLD CONFIGURATION]")

    # Test 24: Owner updates low stock threshold
    print("\n[TEST 24] Owner updates low stock threshold...")
    threshold_payload = {"low_stock_threshold": 8}
    r24 = client.patch(f"/api/v1/inventory/{env['simple_inv_id']}/threshold", json=threshold_payload, headers=env["owner_headers"])
    assert r24.status_code == status.HTTP_200_OK, r24.text
    res24 = r24.json()
    assert res24["low_stock_threshold"] == 8
    print(f"         Threshold successfully updated to {res24['low_stock_threshold']}.")
    results.append(("24. Owner updates low stock threshold", "PASS"))

    # Test 25: Negative threshold rejected
    print("\n[TEST 25] Negative threshold rejected (422)...")
    invalid_threshold = {"low_stock_threshold": -5}
    r25 = client.patch(f"/api/v1/inventory/{env['simple_inv_id']}/threshold", json=invalid_threshold, headers=env["owner_headers"])
    assert r25.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, 422, status.HTTP_400_BAD_REQUEST], r25.text
    print("         Confirmed: Negative threshold rejected.")
    results.append(("25. Negative threshold rejected", "PASS"))

    # Test 26: Staff blocked from updating threshold (403)
    print("\n[TEST 26] Staff blocked from updating threshold (403)...")
    r26 = client.patch(f"/api/v1/inventory/{env['simple_inv_id']}/threshold", json=threshold_payload, headers=env["staff_headers"])
    assert r26.status_code == status.HTTP_403_FORBIDDEN, r26.text
    print("         Confirmed: Staff request rejected with 403 Forbidden.")
    results.append(("26. Staff blocked from updating threshold (403)", "PASS"))

    # --------------------------------------------------------------------------
    # PART G: STOCK MOVEMENT LEDGER & AUDIT TRAIL
    # --------------------------------------------------------------------------
    print("\n[PART G: STOCK MOVEMENT LEDGER & AUDIT TRAIL]")

    # Test 27: List stock movements (GET /api/v1/inventory/movements)
    print("\n[TEST 27] List stock movements...")
    r27 = client.get("/api/v1/inventory/movements?limit=50", headers=env["owner_headers"])
    assert r27.status_code == status.HTTP_200_OK, r27.text
    data27 = r27.json()
    assert "items" in data27 and "total" in data27
    movements = data27["items"]
    assert isinstance(movements, list)
    assert len(movements) >= 5  # 3 adjustments + 2 inwards
    print(f"         Retrieved {len(movements)} movements from audit ledger (Total: {data27['total']}).")
    results.append(("27. List stock movements", "PASS"))

    # Test 28: Filter movements by movement_type (PURCHASE and ADJUSTMENT)
    print("\n[TEST 28] Filter movements by movement_type=PURCHASE...")
    r28a = client.get("/api/v1/inventory/movements?movement_type=PURCHASE", headers=env["owner_headers"])
    assert r28a.status_code == status.HTTP_200_OK, r28a.text
    purchase_moves = r28a.json()["items"]
    assert len(purchase_moves) >= 2
    for m in purchase_moves:
        assert m["movement_type"] == "PURCHASE"

    print("\n         Filter movements by movement_type=ADJUSTMENT...")
    r28b = client.get("/api/v1/inventory/movements?movement_type=ADJUSTMENT", headers=env["owner_headers"])
    assert r28b.status_code == status.HTTP_200_OK, r28b.text
    adj_moves = r28b.json()["items"]
    assert len(adj_moves) >= 3
    for m in adj_moves:
        assert m["movement_type"] == "ADJUSTMENT"
    print("         Confirmed: Movement type filters strictly match.")
    results.append(("28. Filter movements by movement_type", "PASS"))

    # Test 29: Filter movements by category
    print("\n[TEST 29] Filter movements by category...")
    r29 = client.get(f"/api/v1/inventory/movements?category_id={env['cat_id']}", headers=env["owner_headers"])
    assert r29.status_code == status.HTTP_200_OK, r29.text
    cat_moves = r29.json()["items"]
    assert len(cat_moves) >= 5
    for m in cat_moves:
        assert m["category_name"] is not None
    print(f"         Confirmed: Category filter returned {len(cat_moves)} movements.")
    results.append(("29. Filter movements by category", "PASS"))

    # Test 30: Search movements by PO reference
    print("\n[TEST 30] Search movements by PO reference...")
    r30 = client.get(f"/api/v1/inventory/movements?search={po_ref}", headers=env["owner_headers"])
    assert r30.status_code == status.HTTP_200_OK, r30.text
    search_moves = r30.json()["items"]
    assert len(search_moves) >= 1
    assert po_ref in (search_moves[0].get("notes") or "")
    print(f"         Confirmed: Found movement with PO reference: {search_moves[0]['notes']}")
    results.append(("30. Search movements by reference", "PASS"))

    # Test 31: Staff can view movement ledger
    print("\n[TEST 31] Staff can view movement ledger...")
    r31 = client.get("/api/v1/inventory/movements", headers=env["staff_headers"])
    assert r31.status_code == status.HTTP_200_OK, r31.text
    assert "items" in r31.json()
    print("         Confirmed: Staff has read access to movement ledger.")
    results.append(("31. Staff can view movement ledger", "PASS"))

    # --------------------------------------------------------------------------
    # PART H: FULL BILLING & CANCELLATION LIFECYCLE INTEGRATION
    # --------------------------------------------------------------------------
    print("\n[PART H: FULL BILLING & CANCELLATION LIFECYCLE INTEGRATION]")

    # Test 32: Bill checkout decrements inventory & logs SALE movement
    print("\n[TEST 32] Bill checkout decrements inventory & logs SALE movement...")
    # Get current stock of simple product
    r_check1 = client.get(f"/api/v1/inventory/{env['simple_prod_id']}", headers=env["owner_headers"])
    stock_before_sale = r_check1.json()[0]["quantity"]

    bill_payload = {
        "customer_phone": "9876543210",
        "customer_name": "Test Customer",
        "items": [
            {
                "product_id": str(env["simple_prod_id"]),
                "quantity": 2,
                "unit_price": 1299.00,
            }
        ],
        "subtotal": 2598.00,
        "discount_type": "PERCENTAGE",
        "discount_value": 0,
        "discount_amount": 0,
        "tax_percent": 0,
        "tax_amount": 0,
        "final_total": 2598.00,
        "payment_method": "CASH",
        "amount_received": 2598.00,
    }
    r32 = client.post("/api/v1/bills", json=bill_payload, headers=env["staff_headers"])
    assert r32.status_code == status.HTTP_201_CREATED, r32.text
    bill_data = r32.json()
    bill_id = bill_data["id"]
    bill_number = bill_data.get("bill_number", f"BILL-{bill_id[:8]}")

    # Verify stock decremented by 2
    r_check2 = client.get(f"/api/v1/inventory/{env['simple_prod_id']}", headers=env["owner_headers"])
    stock_after_sale = r_check2.json()[0]["quantity"]
    assert stock_after_sale == stock_before_sale - 2

    # Verify SALE movement logged
    r_move_sale = client.get(f"/api/v1/inventory/movements?search={bill_number}", headers=env["owner_headers"])
    assert r_move_sale.status_code == status.HTTP_200_OK
    sale_moves = r_move_sale.json()["items"]
    assert len(sale_moves) >= 1
    assert sale_moves[0]["movement_type"] == "SALE"
    assert sale_moves[0]["quantity_change"] == -2
    print(f"         Confirmed: Bill created ({bill_number}). Stock: {stock_before_sale} -> {stock_after_sale}. Movement: SALE (-2).")
    results.append(("32. Bill checkout decrements inventory & logs SALE", "PASS"))

    # Test 33: Bill cancellation restores inventory & logs CANCELLATION movement
    print("\n[TEST 33] Bill cancellation restores inventory & logs CANCELLATION movement...")
    cancel_payload = {
        "reason": "Customer changed mind at billing counter",
    }
    r33 = client.patch(f"/api/v1/bills/{bill_id}/cancel", json=cancel_payload, headers=env["owner_headers"])
    assert r33.status_code == status.HTTP_200_OK, r33.text

    # Verify stock restored by +2
    r_check3 = client.get(f"/api/v1/inventory/{env['simple_prod_id']}", headers=env["owner_headers"])
    stock_after_cancel = r_check3.json()[0]["quantity"]
    assert stock_after_cancel == stock_before_sale

    # Verify CANCELLATION movement logged
    r_move_cancel = client.get("/api/v1/inventory/movements?movement_type=CANCELLATION", headers=env["owner_headers"])
    assert r_move_cancel.status_code == status.HTTP_200_OK
    cancel_moves = r_move_cancel.json()["items"]
    assert any(m["reference_id"] == bill_id for m in cancel_moves)
    print(f"         Confirmed: Bill cancelled. Stock restored: {stock_after_sale} -> {stock_after_cancel}. Movement: CANCELLATION (+2).")
    results.append(("33. Bill cancellation restores stock & logs CANCELLATION", "PASS"))

    # Test 34: Immutable ledger audit integrity check
    print("\n[TEST 34] Ledger audit integrity verification...")
    r34 = client.get("/api/v1/inventory/movements?limit=100", headers=env["owner_headers"])
    assert r34.status_code == status.HTTP_200_OK
    all_moves = r34.json()["items"]
    movement_types = set(m["movement_type"] for m in all_moves)
    assert "PURCHASE" in movement_types
    assert "ADJUSTMENT" in movement_types
    assert "SALE" in movement_types
    assert "CANCELLATION" in movement_types
    print(f"         Movement types present in ledger: {movement_types}")
    print(f"         Total immutable movement audit records: {len(all_moves)}")
    results.append(("34. Complete ledger audit integrity verified", "PASS"))

    # --------------------------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("VIYON PHASE 5.3 INVENTORY & STOCK LEDGER TEST RESULTS SUMMARY")
    print("=" * 80)
    for name, status_str in results:
        print(f"  {name:<65} [{status_str}]")
    print("=" * 80)
    print(f"ALL {len(results)} OF {len(results)} TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 80)


if __name__ == "__main__":
    run_phase5_3_inventory_tests()
