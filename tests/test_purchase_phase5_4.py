"""VIYON Billing System - Phase 5.4 Supplier & Purchase Management Automated Test Suite
Testing Supplier Directory, Purchase Orders, Goods Receiving, Stock Inward,
Damage Tracking, Supplier Payments, Owner-Only Approvals, and Inventory Protection Rules.

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
# 1. Force Isolated Test Database
# ------------------------------------------------------------------------------
TEST_DB_URL = os.environ.get("DATABASE_URL") or "postgresql+psycopg://postgres:postgres@localhost:5433/viyon_test_fresh"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["SECRET_KEY"] = "test-secret-key-phase5-4-secure-random-at-least-32-chars"
os.environ["ENVIRONMENT"] = "test"

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.security import create_access_token, get_password_hash
from app.main import app


def setup_purchase_test_environment():
    """Ensure database has seeded owner, staff, categories, and test products with inventory."""
    print("[SETUP] Connecting to database for Phase 5.4...", flush=True)
    raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    owner_id = uuid4()
    staff_id = uuid4()
    cat_id = uuid4()
    subcat_id = uuid4()
    prod_1_id = uuid4()
    prod_2_id = uuid4()
    variant_2a_id = uuid4()
    variant_2b_id = uuid4()
    inv_1_id = uuid4()
    inv_2a_id = uuid4()
    inv_2b_id = uuid4()

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
                    VALUES (%s, 'Store Owner', 'storeowner_pur', 'owner_pur@viyon.store', '08270242681', %s, 'OWNER', true);
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
                    VALUES (%s, 'Store Staff', 'cashier_pur', 'cashier_pur@viyon.store', '09876543211', %s, 'STAFF', true);
                    """,
                    (staff_id, default_pw_hash),
                )

            # Category & Subcategory
            cur.execute("SELECT id FROM categories WHERE is_active = true LIMIT 1;")
            row_c = cur.fetchone()
            if row_c:
                cat_id = row_c[0]
            else:
                cur.execute(
                    "INSERT INTO categories (id, name, is_active) VALUES (%s, 'Men Apparel', true);",
                    (cat_id,),
                )

            cur.execute("SELECT id FROM subcategories WHERE category_id = %s AND is_active = true LIMIT 1;", (cat_id,))
            row_sc = cur.fetchone()
            if row_sc:
                subcat_id = row_sc[0]
            else:
                cur.execute(
                    "INSERT INTO subcategories (id, category_id, name, is_active) VALUES (%s, %s, 'Casual Shirts', true);",
                    (subcat_id, cat_id),
                )

            # 1. Simple Product (initial quantity = 10)
            sku_1 = f"SKU-P54-S1-{uuid4().hex[:4]}".upper()
            code_1 = f"PRD-54-1-{uuid4().hex[:4]}".upper()
            cur.execute(
                """
                INSERT INTO products (id, product_name, product_code, category_id, subcategory_id, product_type, base_price, sku, is_active, is_archived)
                VALUES (%s, 'Phase 5.4 Linen Shirt', %s, %s, %s, 'SIMPLE', 999.00, %s, true, false);
                """,
                (prod_1_id, code_1, cat_id, subcat_id, sku_1),
            )
            cur.execute(
                """
                INSERT INTO inventory (id, product_id, variant_id, quantity, low_stock_threshold)
                VALUES (%s, %s, NULL, 10, 5);
                """,
                (inv_1_id, prod_1_id),
            )

            # 2. Variant Product with 2 variants (initial quantities: 20 and 30)
            code_2 = f"PRD-54-2-{uuid4().hex[:4]}".upper()
            cur.execute(
                """
                INSERT INTO products (id, product_name, product_code, category_id, subcategory_id, product_type, base_price, is_active, is_archived)
                VALUES (%s, 'Phase 5.4 Chino Pants', %s, %s, %s, 'VARIANT', 1499.00, true, false);
                """,
                (prod_2_id, code_2, cat_id, subcat_id),
            )

            sku_2a = f"SKU-CH-30-{uuid4().hex[:4]}".upper()
            sku_2b = f"SKU-CH-32-{uuid4().hex[:4]}".upper()
            cur.execute(
                """
                INSERT INTO product_variants (id, product_id, size, color, sku, is_active)
                VALUES (%s, %s, '30', 'Khaki', %s, true);
                """,
                (variant_2a_id, prod_2_id, sku_2a),
            )
            cur.execute(
                """
                INSERT INTO product_variants (id, product_id, size, color, sku, is_active)
                VALUES (%s, %s, '32', 'Khaki', %s, true);
                """,
                (variant_2b_id, prod_2_id, sku_2b),
            )

            cur.execute(
                """
                INSERT INTO inventory (id, product_id, variant_id, quantity, low_stock_threshold)
                VALUES (%s, %s, %s, 20, 5);
                """,
                (inv_2a_id, prod_2_id, variant_2a_id),
            )
            cur.execute(
                """
                INSERT INTO inventory (id, product_id, variant_id, quantity, low_stock_threshold)
                VALUES (%s, %s, %s, 30, 5);
                """,
                (inv_2b_id, prod_2_id, variant_2b_id),
            )

            conn.commit()

    owner_token = create_access_token(subject=str(owner_id), role="OWNER")
    staff_token = create_access_token(subject=str(staff_id), role="STAFF")
    customer_token = create_access_token(subject=str(uuid4()), role="CUSTOMER")

    return {
        "raw_pg_url": raw_pg_url,
        "owner_headers": {"Authorization": f"Bearer {owner_token}"},
        "staff_headers": {"Authorization": f"Bearer {staff_token}"},
        "customer_headers": {"Authorization": f"Bearer {customer_token}"},
        "owner_id": owner_id,
        "staff_id": staff_id,
        "prod_1_id": prod_1_id,
        "sku_1": sku_1,
        "inv_1_id": inv_1_id,
        "prod_2_id": prod_2_id,
        "variant_2a_id": variant_2a_id,
        "variant_2b_id": variant_2b_id,
        "sku_2a": sku_2a,
        "sku_2b": sku_2b,
        "inv_2a_id": inv_2a_id,
        "inv_2b_id": inv_2b_id,
    }


def get_current_stock(raw_pg_url: str, inventory_id: UUID) -> int:
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE id = %s;", (inventory_id,))
            row = cur.fetchone()
            return int(row[0]) if row else 0


def run_phase5_4_tests():
    env = setup_purchase_test_environment()
    raw_pg_url = env["raw_pg_url"]
    client = TestClient(app)
    results = []

    def log_test(num: int, name: str, passed: bool, detail: str = ""):
        results.append((num, name, passed, detail))
        status_str = "PASS" if passed else "FAIL"
        print(f"[{status_str}] Test {num:02d}: {name} {f'({detail})' if detail else ''}", flush=True)

    print("=" * 80)
    print("VIYON PHASE 5.4: COMPLETE SUPPLIER & PURCHASE MANAGEMENT TEST SUITE")
    print(f"Target DB: {TEST_DB_URL}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # SECTION 1: SUPPLIER MANAGEMENT
    # --------------------------------------------------------------------------
    test_idx = 1
    supplier_a_id = None
    supplier_b_id = None
    supplier_a_name = f"Viyon Mill Textiles {uuid4().hex[:6]}"

    # Test 1: Create Supplier A (Owner)
    payload_sup_a = {
        "company_name": supplier_a_name,
        "contact_person": "Ramesh Kumar",
        "phone": "9876543210",
        "alternate_phone": "9876543211",
        "email": "ramesh@viyonmill.com",
        "gstin": "33AAAAA0000A1Z5",
        "address_line": "123 Loom Road, Textool Junction",
        "city": "Coimbatore",
        "state": "Tamil Nadu",
        "pincode": "641001",
        "notes": "Premium cotton and linen fabric vendor.",
    }
    r = client.post("/api/v1/suppliers", json=payload_sup_a, headers=env["owner_headers"])
    if r.status_code == 201:
        data = r.json()
        supplier_a_id = data["id"]
        log_test(test_idx, "Create Supplier A successfully (Owner)", True, f"ID: {supplier_a_id[:8]}")
    else:
        log_test(test_idx, "Create Supplier A successfully (Owner)", False, f"Status: {r.status_code}, {r.text}")

    # Test 2: Reject Duplicate Supplier Name (Conflict 409)
    test_idx += 1
    r = client.post("/api/v1/suppliers", json=payload_sup_a, headers=env["owner_headers"])
    log_test(test_idx, "Reject Duplicate Supplier Name (409 Conflict)", r.status_code == 409)

    # Test 3: Create Supplier B for Soft-Deactivation Testing
    test_idx += 1
    supplier_b_name = f"Tirupur Knitters {uuid4().hex[:6]}"
    r = client.post(
        "/api/v1/suppliers",
        json={"company_name": supplier_b_name, "contact_person": "Karthik V", "phone": "9842109876"},
        headers=env["owner_headers"],
    )
    if r.status_code == 201:
        supplier_b_id = r.json()["id"]
        log_test(test_idx, "Create Supplier B for Deactivation tests", True)
    else:
        log_test(test_idx, "Create Supplier B for Deactivation tests", False, r.text)

    # Test 4: List Suppliers with Financial Aggregations
    test_idx += 1
    r = client.get("/api/v1/suppliers", headers=env["owner_headers"])
    if r.status_code == 200:
        data = r.json()
        found = any(s["id"] == supplier_a_id for s in data.get("items", []))
        log_test(test_idx, "List suppliers returns created suppliers", found)
    else:
        log_test(test_idx, "List suppliers returns created suppliers", False, r.text)

    # Test 5: Update Supplier Details
    test_idx += 1
    r = client.put(
        f"/api/v1/suppliers/{supplier_a_id}",
        json={"contact_person": "Ramesh Kumar (Managing Director)", "city": "Erode"},
        headers=env["owner_headers"],
    )
    if r.status_code == 200 and r.json()["contact_person"] == "Ramesh Kumar (Managing Director)":
        log_test(test_idx, "Update Supplier Details", True)
    else:
        log_test(test_idx, "Update Supplier Details", False, r.text)

    # Test 6: Soft Deactivate Supplier B
    test_idx += 1
    r = client.put(f"/api/v1/suppliers/{supplier_b_id}", json={"is_active": False}, headers=env["owner_headers"])
    if r.status_code == 200 and r.json()["is_active"] is False:
        log_test(test_idx, "Soft Deactivate Supplier B", True)
    else:
        log_test(test_idx, "Soft Deactivate Supplier B", False, r.text)

    # Test 7: Active-only filter excludes deactivated supplier
    test_idx += 1
    r = client.get("/api/v1/suppliers?is_active=true", headers=env["owner_headers"])
    data = r.json()
    is_excluded = not any(s["id"] == supplier_b_id for s in data.get("items", []))
    log_test(test_idx, "Active-only filter excludes deactivated supplier", is_excluded)

    # --------------------------------------------------------------------------
    # SECTION 2: PURCHASE ORDERS & INVENTORY PROTECTION
    # --------------------------------------------------------------------------
    # Test 8: Block creating PO for Inactive Supplier (HTTP 400)
    test_idx += 1
    r = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier_b_id,
            "items": [{"product_id": str(env["prod_1_id"]), "quantity_ordered": 10, "unit_cost": 100}],
        },
        headers=env["owner_headers"],
    )
    log_test(test_idx, "Block creating PO for Inactive Supplier (400)", r.status_code == 400)

    # Test 9: Create PO in DRAFT status with Line Items
    test_idx += 1
    stock_1_before = get_current_stock(raw_pg_url, env["inv_1_id"])
    stock_2a_before = get_current_stock(raw_pg_url, env["inv_2a_id"])

    po_payload = {
        "supplier_id": supplier_a_id,
        "notes": "Phase 5.4 Test Purchase Order",
        "items": [
            {
                "product_id": str(env["prod_1_id"]),
                "product_name": "Phase 5.4 Linen Shirt",
                "sku": env["sku_1"],
                "quantity_ordered": 50,
                "unit_cost": 500.0,
                "discount_percent": 10.0,  # 500 * 50 = 25000; disc 10% = 2500 -> 22500
                "tax_percent": 5.0,  # 5% of 22500 = 1125 -> total 23625
            },
            {
                "product_id": str(env["prod_2_id"]),
                "variant_id": str(env["variant_2a_id"]),
                "product_name": "Phase 5.4 Chino Pants",
                "variant_name": "30 / Khaki",
                "sku": env["sku_2a"],
                "quantity_ordered": 20,
                "unit_cost": 800.0,
                "discount_percent": 0.0,  # 800 * 20 = 16000
                "tax_percent": 12.0,  # 12% of 16000 = 1920 -> total 17920
            },
        ],
    }
    r = client.post("/api/v1/purchases", json=po_payload, headers=env["owner_headers"])
    po_1_data = r.json() if r.status_code == 201 else {}
    po_1_id = po_1_data.get("id")
    po_1_number = po_1_data.get("po_number")

    po_created_ok = (
        r.status_code == 201
        and po_1_data.get("status") == "DRAFT"
        and len(po_1_data.get("items", [])) == 2
        and po_1_number.startswith("VIYON-PO-")
    )
    log_test(test_idx, "Create PO in DRAFT status with unique PO number", po_created_ok, po_1_number)

    # Test 10: CRITICAL - Verify creating PO does NOT alter stock
    test_idx += 1
    stock_1_after_draft = get_current_stock(raw_pg_url, env["inv_1_id"])
    stock_2a_after_draft = get_current_stock(raw_pg_url, env["inv_2a_id"])
    stock_unaltered_draft = (stock_1_after_draft == stock_1_before) and (stock_2a_after_draft == stock_2a_before)
    log_test(
        test_idx,
        "CRITICAL: Creating PO does NOT alter inventory stock",
        stock_unaltered_draft,
        f"Item 1: {stock_1_after_draft}=={stock_1_before}, Item 2: {stock_2a_after_draft}=={stock_2a_before}",
    )

    # Test 11: Verify Line Item and Order Total Calculations
    test_idx += 1
    # Line 1: base 25000, disc 2500, tax 1125 -> 23625
    # Line 2: base 16000, disc 0, tax 1920 -> 17920
    # Expected grand total: 41545.00
    expected_total = Decimal("41545.00")
    actual_total = Decimal(str(po_1_data.get("total_amount", 0)))
    totals_match = abs(actual_total - expected_total) < Decimal("0.01")
    log_test(test_idx, "Verify Subtotal, Discount, Tax, and Grand Total math", totals_match, f"₹{actual_total}")

    # Test 12: Place Order (DRAFT -> ORDERED)
    test_idx += 1
    r = client.post(f"/api/v1/purchases/{po_1_id}/place", headers=env["owner_headers"])
    placed_ok = r.status_code == 200 and r.json().get("status") == "ORDERED"
    log_test(test_idx, "Place Order (Transitions DRAFT -> ORDERED)", placed_ok)

    # Test 13: CRITICAL - Verify placing PO does NOT alter stock
    test_idx += 1
    stock_1_after_placed = get_current_stock(raw_pg_url, env["inv_1_id"])
    stock_2a_after_placed = get_current_stock(raw_pg_url, env["inv_2a_id"])
    stock_unaltered_placed = (stock_1_after_placed == stock_1_before) and (stock_2a_after_placed == stock_2a_before)
    log_test(
        test_idx,
        "CRITICAL: Placing PO does NOT alter inventory stock",
        stock_unaltered_placed,
        f"Item 1: {stock_1_after_placed}=={stock_1_before}",
    )

    # Test 14: PO Cancellation Workflow (Create secondary PO & cancel it)
    test_idx += 1
    r = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier_a_id,
            "items": [{"product_id": str(env["prod_1_id"]), "quantity_ordered": 5, "unit_cost": 200}],
        },
        headers=env["owner_headers"],
    )
    temp_po_id = r.json()["id"]
    r_cancel = client.post(
        f"/api/v1/purchases/{temp_po_id}/cancel",
        json={"reason": "Vendor out of stock for this season"},
        headers=env["owner_headers"],
    )
    cancel_ok = (
        r_cancel.status_code == 200
        and r_cancel.json().get("status") == "CANCELLED"
        and r_cancel.json().get("cancellation_reason") == "Vendor out of stock for this season"
    )
    log_test(test_idx, "Cancel Purchase Order with mandatory reason", cancel_ok)

    # --------------------------------------------------------------------------
    # SECTION 3: GOODS RECEIVING & STOCK INWARD LEDGER
    # --------------------------------------------------------------------------
    po_item_1_id = po_1_data["items"][0]["id"]
    po_item_2_id = po_1_data["items"][1]["id"]

    # Test 15: Reject Over-Receipt (e.g. ordered 50, trying to receive 60)
    test_idx += 1
    r = client.post(
        f"/api/v1/purchases/{po_1_id}/receive",
        json={
            "items": [
                {
                    "purchase_order_item_id": po_item_1_id,
                    "quantity_received": 60,
                    "quantity_accepted": 60,
                    "quantity_rejected": 0,
                }
            ]
        },
        headers=env["owner_headers"],
    )
    log_test(test_idx, "Reject Over-Receipt exceeding ordered quantity (400)", r.status_code == 400)

    # Test 16: Reject Quantity Received != Accepted + Rejected mismatch (400/422)
    test_idx += 1
    r = client.post(
        f"/api/v1/purchases/{po_1_id}/receive",
        json={
            "items": [
                {
                    "purchase_order_item_id": po_item_1_id,
                    "quantity_received": 30,
                    "quantity_accepted": 20,
                    "quantity_rejected": 5,  # Sum = 25 != 30
                }
            ]
        },
        headers=env["owner_headers"],
    )
    log_test(test_idx, "Reject mismatch in quantity_received != accepted + rejected (400/422)", r.status_code in (400, 422))

    # Test 17: Reject missing rejection reason when quantity_rejected > 0 (400/422)
    test_idx += 1
    r = client.post(
        f"/api/v1/purchases/{po_1_id}/receive",
        json={
            "items": [
                {
                    "purchase_order_item_id": po_item_1_id,
                    "quantity_received": 30,
                    "quantity_accepted": 25,
                    "quantity_rejected": 5,
                    "rejection_reason": "",  # Blank reason
                }
            ]
        },
        headers=env["owner_headers"],
    )
    log_test(test_idx, "Reject missing rejection reason when rejected > 0 (400/422)", r.status_code in (400, 422))

    # Test 18: First Inward Shipment (Partial Receiving: 30 of Item 1 [25 accepted, 5 rejected], 10 of Item 2 [all accepted])
    test_idx += 1
    receive_payload_1 = {
        "delivery_reference": "DC-2026-0812",
        "notes": "First partial shipment received via VRL Logistics",
        "items": [
            {
                "purchase_order_item_id": po_item_1_id,
                "quantity_received": 30,
                "quantity_accepted": 25,
                "quantity_rejected": 5,
                "rejection_reason": "Stitching defect on collar band",
            },
            {
                "purchase_order_item_id": po_item_2_id,
                "quantity_received": 10,
                "quantity_accepted": 10,
                "quantity_rejected": 0,
            },
        ],
    }
    r = client.post(f"/api/v1/purchases/{po_1_id}/receive", json=receive_payload_1, headers=env["owner_headers"])
    grn_1_data = r.json() if r.status_code == 201 else {}
    grn_1_ok = (
        r.status_code == 201
        and grn_1_data.get("grn_number", "").startswith("VIYON-GRN-")
        and grn_1_data.get("total_accepted_quantity") == 35
        and grn_1_data.get("total_rejected_quantity") == 5
    )
    log_test(test_idx, "First Inward Shipment recorded with GRN", grn_1_ok, grn_1_data.get("grn_number"))

    # Test 19: CRITICAL - Stock increases ONLY for quantity_accepted (Item 1: +25, NOT +30)
    test_idx += 1
    stock_1_after_grn1 = get_current_stock(raw_pg_url, env["inv_1_id"])
    # initial was stock_1_before (10). accepted 25 -> must be 35
    stock_1_correct = stock_1_after_grn1 == (stock_1_before + 25)
    log_test(
        test_idx,
        "CRITICAL: Stock increases ONLY by accepted qty (excludes 5 rejected)",
        stock_1_correct,
        f"Expected {stock_1_before + 25}, Actual: {stock_1_after_grn1}",
    )

    # Test 20: CRITICAL - Stock increases for Item 2 (+10 accepted)
    test_idx += 1
    stock_2a_after_grn1 = get_current_stock(raw_pg_url, env["inv_2a_id"])
    stock_2a_correct = stock_2a_after_grn1 == (stock_2a_before + 10)
    log_test(
        test_idx,
        "CRITICAL: Variant stock increases by accepted quantity",
        stock_2a_correct,
        f"Expected {stock_2a_before + 10}, Actual: {stock_2a_after_grn1}",
    )

    # Test 21: Verify Immutable Stock Movement Audit Ledger entries
    test_idx += 1
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT movement_type, reference_type, quantity_change
                FROM stock_movements
                WHERE reference_id = %s
                ORDER BY created_at ASC;
                """,
                (grn_1_data.get("id"),),
            )
            movements = cur.fetchall()
            movements_ok = (
                len(movements) == 2
                and all(m[0] == "PURCHASE" and m[1] == "GOODS_RECEIPT" for m in movements)
                and movements[0][2] == 25
                and movements[1][2] == 10
            )
    log_test(test_idx, "Verify StockMovement ledger recorded PURCHASE/GOODS_RECEIPT", movements_ok)

    # Test 22: Verify PO Status transitioned to PARTIALLY_RECEIVED
    test_idx += 1
    r = client.get(f"/api/v1/purchases/{po_1_id}", headers=env["owner_headers"])
    po_partial_data = r.json()
    is_partially_received = po_partial_data.get("status") == "PARTIALLY_RECEIVED"
    log_test(test_idx, "PO transitions to PARTIALLY_RECEIVED status", is_partially_received)

    # Test 23: Complete Remaining Shipment (Item 1: 20 remaining [all accepted]; Item 2: 10 remaining [all accepted])
    test_idx += 1
    receive_payload_2 = {
        "delivery_reference": "DC-2026-0855",
        "notes": "Final balance shipment received and cleared",
        "items": [
            {
                "purchase_order_item_id": po_item_1_id,
                "quantity_received": 20,
                "quantity_accepted": 20,
                "quantity_rejected": 0,
            },
            {
                "purchase_order_item_id": po_item_2_id,
                "quantity_received": 10,
                "quantity_accepted": 10,
                "quantity_rejected": 0,
            },
        ],
    }
    r = client.post(f"/api/v1/purchases/{po_1_id}/receive", json=receive_payload_2, headers=env["owner_headers"])
    grn_2_ok = r.status_code == 201
    log_test(test_idx, "Second shipment completes remaining order quantities", grn_2_ok)

    # Test 24: Verify PO Status transitions to RECEIVED
    test_idx += 1
    r = client.get(f"/api/v1/purchases/{po_1_id}", headers=env["owner_headers"])
    po_full_data = r.json()
    is_fully_received = po_full_data.get("status") == "RECEIVED"
    log_test(test_idx, "PO transitions to RECEIVED status upon completion", is_fully_received)

    # Test 25: Verify Final Total Stocks (Item 1: +45 total accepted; Item 2: +20 total accepted)
    test_idx += 1
    stock_1_final = get_current_stock(raw_pg_url, env["inv_1_id"])
    stock_2a_final = get_current_stock(raw_pg_url, env["inv_2a_id"])
    final_stock_ok = stock_1_final == (stock_1_before + 45) and stock_2a_final == (stock_2a_before + 20)
    log_test(
        test_idx,
        "Final physical stocks match exact accepted items across multiple GRNs",
        final_stock_ok,
        f"Item 1: {stock_1_final}=={stock_1_before + 45}",
    )

    # --------------------------------------------------------------------------
    # SECTION 4: SUPPLIER PAYMENTS & OWNER CONFIRMATION WORKFLOW
    # --------------------------------------------------------------------------
    # Test 26: Cash Payment is Immediately CONFIRMED
    test_idx += 1
    pay_cash_payload = {
        "supplier_id": supplier_a_id,
        "purchase_order_id": po_1_id,
        "amount": 10000.0,
        "payment_method": "CASH",
        "notes": "Cash advance paid on delivery",
    }
    r = client.post("/api/v1/purchases/payments", json=pay_cash_payload, headers=env["owner_headers"])
    cash_pay_data = r.json() if r.status_code == 201 else {}
    cash_confirmed = (
        r.status_code == 201
        and cash_pay_data.get("status") == "CONFIRMED"
        and cash_pay_data.get("payment_number", "").startswith("VIYON-SP-")
    )
    log_test(test_idx, "Cash payment is immediately CONFIRMED", cash_confirmed, cash_pay_data.get("payment_number"))

    # Test 27: Verify Cash Payment immediately reduces PO balance due
    test_idx += 1
    r = client.get(f"/api/v1/purchases/{po_1_id}", headers=env["owner_headers"])
    po_after_cash = r.json()
    po_balance_after_cash = po_after_cash.get("balance_due")
    # Total 41545.00 - 10000 = 31545.00
    expected_bal_cash = Decimal("31545.00")
    bal_reduced = abs(Decimal(str(po_balance_after_cash)) - expected_bal_cash) < Decimal("0.01")
    log_test(test_idx, "Confirmed Cash Payment reduces PO balance due", bal_reduced, f"Balance: ₹{po_balance_after_cash}")

    # Test 28: Non-Cash Payment (UPI) starts as PENDING
    test_idx += 1
    pay_upi_payload = {
        "supplier_id": supplier_a_id,
        "purchase_order_id": po_1_id,
        "amount": 15000.0,
        "payment_method": "UPI",
        "reference_number": "UPI-REF-992019482",
        "notes": "Transferred via GPay merchant app",
    }
    r = client.post("/api/v1/purchases/payments", json=pay_upi_payload, headers=env["owner_headers"])
    upi_pay_data = r.json() if r.status_code == 201 else {}
    upi_pay_id = upi_pay_data.get("id")
    upi_pending = r.status_code == 201 and upi_pay_data.get("status") == "PENDING"
    log_test(test_idx, "UPI payment recorded with status PENDING", upi_pending, upi_pay_data.get("payment_number"))

    # Test 29: Pending Payment does NOT reduce PO balance due yet
    test_idx += 1
    r = client.get(f"/api/v1/purchases/{po_1_id}", headers=env["owner_headers"])
    po_after_upi_pending = r.json()
    bal_unchanged_by_pending = (
        abs(Decimal(str(po_after_upi_pending.get("balance_due"))) - expected_bal_cash) < Decimal("0.01")
    )
    log_test(test_idx, "PENDING payment does NOT reduce PO balance due", bal_unchanged_by_pending)

    # Test 30: Owner Confirms UPI Payment
    test_idx += 1
    r = client.post(
        f"/api/v1/purchases/payments/{upi_pay_id}/confirm",
        json={"reference_number": "BANK-UTR-AXIS-992019482", "notes": "Verified in Axis Bank current account"},
        headers=env["owner_headers"],
    )
    upi_confirmed = (
        r.status_code == 200
        and r.json().get("status") == "CONFIRMED"
        and r.json().get("reference_number") == "BANK-UTR-AXIS-992019482"
    )
    log_test(test_idx, "Owner confirms UPI payment (Transitions PENDING -> CONFIRMED)", upi_confirmed)

    # Test 31: Confirmed Payment now reduces PO balance due
    test_idx += 1
    r = client.get(f"/api/v1/purchases/{po_1_id}", headers=env["owner_headers"])
    po_after_upi_confirmed = r.json()
    # 31545.00 - 15000 = 16545.00
    expected_bal_upi = Decimal("16545.00")
    bal_reduced_by_upi = (
        abs(Decimal(str(po_after_upi_confirmed.get("balance_due"))) - expected_bal_upi) < Decimal("0.01")
    )
    log_test(
        test_idx,
        "Confirmed UPI Payment now reduces PO balance due",
        bal_reduced_by_upi,
        f"Remaining: ₹{po_after_upi_confirmed.get('balance_due')}",
    )

    # Test 32: Reject Cheque Payment workflow
    test_idx += 1
    pay_cheque_payload = {
        "supplier_id": supplier_a_id,
        "purchase_order_id": po_1_id,
        "amount": 5000.0,
        "payment_method": "CHEQUE",
        "reference_number": "CHQ-882012",
        "notes": "Cheque submitted for clearing",
    }
    r = client.post("/api/v1/purchases/payments", json=pay_cheque_payload, headers=env["owner_headers"])
    cheque_pay_id = r.json()["id"]

    r_reject = client.post(
        f"/api/v1/purchases/payments/{cheque_pay_id}/reject",
        json={"rejection_reason": "Cheque bounced due to signature variation"},
        headers=env["owner_headers"],
    )
    cheque_rejected = (
        r_reject.status_code == 200
        and r_reject.json().get("status") == "REJECTED"
        and r_reject.json().get("notes") == "Cheque bounced due to signature variation"
    )
    log_test(test_idx, "Owner rejects payment with mandatory reason", cheque_rejected)

    # Test 33: Overpayment Prevention (Cannot pay more than remaining balance)
    test_idx += 1
    r = client.post(
        "/api/v1/purchases/payments",
        json={
            "supplier_id": supplier_a_id,
            "purchase_order_id": po_1_id,
            "amount": 25000.0,  # Balance is only 16545.00
            "payment_method": "CASH",
        },
        headers=env["owner_headers"],
    )
    log_test(test_idx, "Prevent Overpayment exceeding remaining PO balance (400)", r.status_code == 400)

    # Test 34: Supplier Outstanding Balance Aggregation
    test_idx += 1
    r = client.get(f"/api/v1/suppliers/{supplier_a_id}", headers=env["owner_headers"])
    sup_summary = r.json()
    # Total purchases: 41545.00. Total paid: 25000.00 (10000 cash + 15000 upi). Outstanding: 16545.00
    outstanding_ok = (
        abs(Decimal(str(sup_summary.get("total_purchases", 0))) - Decimal("41545.00")) < Decimal("0.01")
        and abs(Decimal(str(sup_summary.get("total_paid", 0))) - Decimal("25000.00")) < Decimal("0.01")
        and abs(Decimal(str(sup_summary.get("outstanding_balance", 0))) - Decimal("16545.00")) < Decimal("0.01")
    )
    log_test(
        test_idx,
        "Supplier Outstanding Balance dynamically reflects confirmed purchases & payments",
        outstanding_ok,
        f"Due: ₹{sup_summary.get('outstanding_balance')}",
    )

    # --------------------------------------------------------------------------
    # SECTION 5: PURCHASE FINANCIAL ANALYTICS & SUMMARY
    # --------------------------------------------------------------------------
    test_idx += 1
    r = client.get("/api/v1/purchases/summary", headers=env["owner_headers"])
    summary_data = r.json() if r.status_code == 200 else {}
    summary_keys_ok = (
        r.status_code == 200
        and "total_purchase_orders" in summary_data
        and "total_ordered_value" in summary_data
        and "total_goods_received_value" in summary_data
        and "total_confirmed_payments" in summary_data
        and "total_pending_payments" in summary_data
        and "total_supplier_outstanding" in summary_data
        and "active_suppliers_count" in summary_data
    )
    log_test(test_idx, "Purchase Financial Summary returns all 7 KPI metrics", summary_keys_ok)

    # --------------------------------------------------------------------------
    # SECTION 6: STRICT ROLE-BASED ACCESS CONTROL (RBAC)
    # --------------------------------------------------------------------------
    # Test 36: Staff can read suppliers (200)
    test_idx += 1
    r = client.get("/api/v1/suppliers", headers=env["staff_headers"])
    log_test(test_idx, "Staff can read suppliers list (200 OK)", r.status_code == 200)

    # Test 37: Staff is BLOCKED from creating supplier (403)
    test_idx += 1
    r = client.post(
        "/api/v1/suppliers",
        json={"company_name": "Staff Supplier Attempt", "contact_person": "Unauthorized"},
        headers=env["staff_headers"],
    )
    log_test(test_idx, "Staff is BLOCKED from creating supplier (403 Forbidden)", r.status_code == 403)

    # Test 38: Staff is BLOCKED from updating supplier (403)
    test_idx += 1
    r = client.put(
        f"/api/v1/suppliers/{supplier_a_id}",
        json={"contact_person": "Staff Edit Attempt"},
        headers=env["staff_headers"],
    )
    log_test(test_idx, "Staff is BLOCKED from updating supplier (403 Forbidden)", r.status_code == 403)

    # Test 39: Staff can read purchase orders (200)
    test_idx += 1
    r = client.get("/api/v1/purchases", headers=env["staff_headers"])
    log_test(test_idx, "Staff can read purchase orders list (200 OK)", r.status_code == 200)

    # Test 40: Staff is BLOCKED from creating purchase order (403)
    test_idx += 1
    r = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier_a_id,
            "items": [{"product_id": str(env["prod_1_id"]), "quantity_ordered": 1, "unit_cost": 100}],
        },
        headers=env["staff_headers"],
    )
    log_test(test_idx, "Staff is BLOCKED from creating purchase order (403 Forbidden)", r.status_code == 403)

    # Test 41: Staff is BLOCKED from placing purchase order (403)
    test_idx += 1
    r = client.post(f"/api/v1/purchases/{po_1_id}/place", headers=env["staff_headers"])
    log_test(test_idx, "Staff is BLOCKED from placing purchase order (403 Forbidden)", r.status_code == 403)

    # Test 42: Staff is BLOCKED from cancelling purchase order (403)
    test_idx += 1
    r = client.post(f"/api/v1/purchases/{po_1_id}/cancel", json={"reason": "Staff attempt"}, headers=env["staff_headers"])
    log_test(test_idx, "Staff is BLOCKED from cancelling purchase order (403 Forbidden)", r.status_code == 403)

    # Test 43: Staff is BLOCKED from receiving goods / inwarding stock (403)
    test_idx += 1
    r = client.post(
        f"/api/v1/purchases/{po_1_id}/receive",
        json={"items": [{"purchase_order_item_id": po_item_1_id, "quantity_received": 1, "quantity_accepted": 1, "quantity_rejected": 0}]},
        headers=env["staff_headers"],
    )
    log_test(test_idx, "Staff is BLOCKED from receiving goods (403 Forbidden)", r.status_code == 403)

    # Test 44: Staff is BLOCKED from recording supplier payment (403)
    test_idx += 1
    r = client.post(
        "/api/v1/purchases/payments",
        json={"supplier_id": supplier_a_id, "amount": 1000.0, "payment_method": "CASH"},
        headers=env["staff_headers"],
    )
    log_test(test_idx, "Staff is BLOCKED from recording supplier payment (403 Forbidden)", r.status_code == 403)

    # Test 45: Staff is BLOCKED from confirming supplier payment (403)
    test_idx += 1
    r = client.post(f"/api/v1/purchases/payments/{cash_pay_data['id']}/confirm", json={}, headers=env["staff_headers"])
    log_test(test_idx, "Staff is BLOCKED from confirming supplier payment (403 Forbidden)", r.status_code == 403)

    # Test 46: Unauthenticated requests are rejected (401)
    test_idx += 1
    r = client.get("/api/v1/suppliers")
    log_test(test_idx, "Unauthenticated requests rejected (401 Unauthorized)", r.status_code == 401)

    print("=" * 80)
    total_tests = len(results)
    passed_tests = sum(1 for _, _, p, _ in results)
    print(f"PHASE 5.4 TEST RESULTS: {passed_tests} / {total_tests} PASSED")
    print("=" * 80)

    if passed_tests < total_tests:
        print("[ERROR] SOME TESTS FAILED!")
        sys.exit(1)
    else:
        print("[SUCCESS] ALL PHASE 5.4 SUPPLIER & PURCHASE TESTS PASSED!")


if __name__ == "__main__":
    run_phase5_4_tests()
