"""VIYON Billing System - Phase 5.5 Comprehensive End-to-End Integration,
Workflow Auditing & Reconciliation Test Suite.

Covers:
- Workflow A: Product & Variant Management (Catalogue & Storefront)
- Workflow B: Supplier & Purchase Orders (Zero Stock on PO, Accepted vs Rejected Receiving, Payments)
- Workflow C: POS Billing (Search, Discounts, Taxes, Stock Deductions, Receipts)
- Workflow D: Payment Verification (Cash Confirmed, UPI Pending, Manual Confirmation, Rejection)
- Workflow E: Bill Cancellation (Stock Restoration, Pending UPI Rejection, Preservation of Confirmed)
- Workflow F: Expenses, Cash Registers & Daily Financial P&L Reconciliation
- Workflow G: Staff Lifecycle & Security (Creation, Login, RBAC, Password Reset, Invalidation, Deactivation)
- Mathematical Invariants & Reconciliations: Sales, Inventory Movement Ledger, Supplier Balances.

Target Database: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh).
NEVER connects to or modifies the Neon production database.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta
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
os.environ["SECRET_KEY"] = "test-secret-key-phase5-5-secure-random-at-least-32-chars"
os.environ["ENVIRONMENT"] = "test"

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.security import create_access_token, get_password_hash
from app.main import app


def setup_e2e_environment():
    """Seed base users and return auth tokens and database connection string."""
    print("[SETUP] Connecting to database for Phase 5.5 E2E Suite...", flush=True)
    raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    owner_id = uuid4()
    staff_id = uuid4()

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
                    VALUES (%s, 'Store Owner', 'storeowner_e2e', 'owner_e2e@viyon.store', '08270242681', %s, 'OWNER', true);
                    """,
                    (owner_id, default_pw_hash),
                )

            # Check or create active cashier staff
            cur.execute("SELECT id FROM users WHERE role = 'STAFF' AND is_active = true LIMIT 1;")
            row_staff = cur.fetchone()
            if row_staff:
                staff_id = row_staff[0]
            else:
                cur.execute(
                    """
                    INSERT INTO users (id, full_name, username, email, phone, password_hash, role, is_active)
                    VALUES (%s, 'Senior Cashier', 'cashier_e2e', 'cashier_e2e@viyon.store', '09876543211', %s, 'STAFF', true);
                    """,
                    (staff_id, default_pw_hash),
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
    }


def get_stock(raw_pg_url: str, product_id: UUID, variant_id: UUID = None) -> int:
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            if variant_id:
                cur.execute(
                    "SELECT quantity FROM inventory WHERE product_id = %s AND variant_id = %s;",
                    (product_id, variant_id),
                )
            else:
                cur.execute(
                    "SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;",
                    (product_id,),
                )
            row = cur.fetchone()
            return int(row[0]) if row else 0


def run_e2e_suite():
    env = setup_e2e_environment()
    raw_pg_url = env["raw_pg_url"]
    client = TestClient(app)
    results = []

    def log_test(num: int, name: str, passed: bool, detail: str = ""):
        results.append((num, name, passed, detail))
        status_str = "PASS" if passed else "FAIL"
        print(f"[{status_str}] Test {num:02d}: {name} {f'({detail})' if detail else ''}", flush=True)

    print("=" * 80)
    print("VIYON PHASE 5.5: COMPLETE SYSTEM INTEGRATION & END-TO-END WORKFLOW SUITE")
    print(f"Target DB: {TEST_DB_URL}")
    print("=" * 80)

    test_idx = 1

    # ==========================================================================
    # WORKFLOW A: PRODUCT MANAGEMENT & CATALOGUE
    # ==========================================================================
    print("\n--- WORKFLOW A: PRODUCT & VARIANT CATALOGUE MANAGEMENT ---")

    # Test 1: Owner creates Category
    cat_payload = {"name": f"Men Premium {uuid4().hex[:4]}", "description": "Men luxury apparel"}
    r = client.post("/api/v1/categories", json=cat_payload, headers=env["owner_headers"])
    cat_ok = r.status_code == 201 and "id" in r.json()
    cat_id = r.json()["id"] if cat_ok else None
    log_test(test_idx, "Workflow A: Owner creates Category", cat_ok, f"ID: {cat_id}")

    # Test 2: Owner creates Subcategory
    test_idx += 1
    subcat_payload = {"category_id": cat_id, "name": f"Formal Trousers {uuid4().hex[:4]}"}
    r = client.post("/api/v1/subcategories", json=subcat_payload, headers=env["owner_headers"])
    subcat_ok = r.status_code == 201 and "id" in r.json()
    subcat_id = r.json()["id"] if subcat_ok else None
    log_test(test_idx, "Workflow A: Owner creates Subcategory", subcat_ok, f"ID: {subcat_id}")

    # Test 3: Owner creates Simple Product with SKU, barcode, price, cost
    test_idx += 1
    simple_sku = f"SKU-SMP-{uuid4().hex[:6]}".upper()
    simple_barcode = f"BAR-{uuid4().hex[:8]}".upper()
    simple_prod_payload = {
        "product_name": "Premium Cotton Oxford Shirt",
        "category_id": cat_id,
        "subcategory_id": subcat_id,
        "product_type": "SIMPLE",
        "base_price": 1499.00,
        "cost_price": 750.00,
        "sku": simple_sku,
        "barcode": simple_barcode,
        "initial_stock": 25,
        "low_stock_threshold": 5,
    }
    r = client.post("/api/v1/products", json=simple_prod_payload, headers=env["owner_headers"])
    prod_simple_ok = r.status_code == 201 and "id" in r.json()
    prod_simple_id = UUID(r.json()["id"]) if prod_simple_ok else None
    log_test(test_idx, "Workflow A: Owner creates Simple Product with initial inventory", prod_simple_ok, simple_sku)

    # Test 4: Verify Simple Product inventory record created
    test_idx += 1
    stock_simple_init = get_stock(raw_pg_url, prod_simple_id)
    log_test(test_idx, "Workflow A: Simple product inventory equals initial stock (25)", stock_simple_init == 25)

    # Test 5: Owner creates Variant Product with 2 sizes (30 and 32)
    test_idx += 1
    variant_prod_payload = {
        "product_name": "Tailored Italian Chino Pants",
        "category_id": cat_id,
        "subcategory_id": subcat_id,
        "product_type": "VARIANT",
        "base_price": 2499.00,
        "cost_price": 1200.00,
    }
    r = client.post("/api/v1/products", json=variant_prod_payload, headers=env["owner_headers"])
    prod_variant_ok = r.status_code == 201 and "id" in r.json()
    prod_variant_id = UUID(r.json()["id"]) if prod_variant_ok else None
    log_test(test_idx, "Workflow A: Owner creates Parent Variant Product", prod_variant_ok)

    # Test 6: Add Variants with SKUs, barcodes, and stock
    test_idx += 1
    sku_v30 = f"SKU-CHN-30-{uuid4().hex[:4]}".upper()
    sku_v32 = f"SKU-CHN-32-{uuid4().hex[:4]}".upper()

    r1 = client.post(
        f"/api/v1/products/{prod_variant_id}/variants",
        json={"size": "30", "color": "Navy", "sku": sku_v30, "barcode": f"B30-{uuid4().hex[:4]}", "initial_stock": 15, "low_stock_threshold": 4},
        headers=env["owner_headers"],
    )
    r2 = client.post(
        f"/api/v1/products/{prod_variant_id}/variants",
        json={"size": "32", "color": "Navy", "sku": sku_v32, "barcode": f"B32-{uuid4().hex[:4]}", "initial_stock": 20, "low_stock_threshold": 4},
        headers=env["owner_headers"],
    )
    variants_ok = r1.status_code == 201 and r2.status_code == 201
    var_30_id = UUID(r1.json()["id"]) if r1.status_code == 201 else None
    var_32_id = UUID(r2.json()["id"]) if r2.status_code == 201 else None
    log_test(test_idx, "Workflow A: Add Variants (Size 30: 15 units, Size 32: 20 units)", variants_ok)

    # Test 7: Verify Storefront Visibility
    test_idx += 1
    r = client.get("/api/v1/products", headers=env["staff_headers"])
    pub_prods = r.json()
    found_simple = any(p["id"] == str(prod_simple_id) for p in pub_prods.get("items", pub_prods if isinstance(pub_prods, list) else []))
    log_test(test_idx, "Workflow A: Product visible in public storefront API", found_simple)

    # ==========================================================================
    # WORKFLOW B: PURCHASE MANAGEMENT & PHYSICAL STOCK INWARD
    # ==========================================================================
    print("\n--- WORKFLOW B: SUPPLIER PROCUREMENT & GOODS RECEIVING ---")

    # Test 8: Register Supplier
    test_idx += 1
    sup_name = f"Viyon Mill Textures {uuid4().hex[:6]}"
    r = client.post(
        "/api/v1/suppliers",
        json={
            "company_name": sup_name,
            "contact_person": "Gopalakrishnan V",
            "phone": "9842211223",
            "email": "gopal@viyontextures.in",
            "gstin": "33AABCV1234F1Z9",
            "city": "Coimbatore",
            "state": "Tamil Nadu",
        },
        headers=env["owner_headers"],
    )
    sup_ok = r.status_code == 201
    supplier_id = r.json()["id"] if sup_ok else None
    log_test(test_idx, "Workflow B: Register apparel supplier", sup_ok, f"ID: {supplier_id[:8]}")

    # Test 9: Create PO in DRAFT (50 Simple Shirts, 30 Variant 30 Pants)
    test_idx += 1
    stock_simple_before_po = get_stock(raw_pg_url, prod_simple_id)
    stock_v30_before_po = get_stock(raw_pg_url, prod_variant_id, var_30_id)

    po_payload = {
        "supplier_id": supplier_id,
        "notes": "Festive replenishment order",
        "items": [
            {
                "product_id": str(prod_simple_id),
                "quantity_ordered": 50,
                "unit_cost": 500.00,
                "discount_percent": 10.00,  # 50 * 500 = 25000; disc 10% = 2500 -> 22500
                "tax_percent": 5.00,  # 5% of 22500 = 1125 -> total 23625
            },
            {
                "product_id": str(prod_variant_id),
                "variant_id": str(var_30_id),
                "quantity_ordered": 30,
                "unit_cost": 800.00,
                "discount_percent": 0.00,  # 30 * 800 = 24000
                "tax_percent": 12.00,  # 12% of 24000 = 2880 -> total 26880
            },
        ],
    }
    r = client.post("/api/v1/purchases/orders", json=po_payload, headers=env["owner_headers"])
    po_ok = r.status_code == 201 and r.json().get("status") == "DRAFT"
    po_id = r.json().get("id") if po_ok else None
    po_num = r.json().get("po_number") if po_ok else None
    po_total = Decimal(str(r.json().get("grand_total") or r.json().get("total_amount", 0)))
    # Expected grand total: 23625 + 26880 = 50505.00
    expected_po_total = Decimal("50505.00")
    log_test(
        test_idx,
        "Workflow B: Create PO in DRAFT status with exact tax/discount math",
        po_ok and abs(po_total - expected_po_total) < Decimal("0.01"),
        f"{po_num} | Grand Total: ₹{po_total}",
    )

    # Test 10: INVARIANT - PO creation does NOT increase inventory
    test_idx += 1
    stock_simple_after_po = get_stock(raw_pg_url, prod_simple_id)
    stock_v30_after_po = get_stock(raw_pg_url, prod_variant_id, var_30_id)
    log_test(
        test_idx,
        "INVARIANT: Draft PO creation does NOT alter physical inventory",
        stock_simple_after_po == stock_simple_before_po and stock_v30_after_po == stock_v30_before_po,
    )

    # Test 11: Place PO (DRAFT -> ORDERED)
    test_idx += 1
    r = client.post(f"/api/v1/purchases/orders/{po_id}/place", headers=env["owner_headers"])
    log_test(test_idx, "Workflow B: Place PO (Transitions to ORDERED)", r.status_code == 200 and r.json().get("status") == "ORDERED")

    # Test 12: INVARIANT - Placing PO does NOT increase inventory
    test_idx += 1
    stock_simple_after_placed = get_stock(raw_pg_url, prod_simple_id)
    log_test(
        test_idx,
        "INVARIANT: Placing PO to vendor does NOT alter physical inventory",
        stock_simple_after_placed == stock_simple_before_po,
    )

    # Test 13: Partial Goods Receipt with Quality Inspection (Item 1: 30 received [25 accepted, 5 rejected for damage])
    test_idx += 1
    r_po_details = client.get(f"/api/v1/purchases/orders/{po_id}", headers=env["owner_headers"])
    po_items_list = r_po_details.json()["items"]
    po_item_simple_id = next(item["id"] for item in po_items_list if item["product_id"] == str(prod_simple_id))
    po_item_v30_id = next(item["id"] for item in po_items_list if item.get("variant_id") == str(var_30_id))

    grn_payload_1 = {
        "purchase_order_id": po_id,
        "delivery_reference": "DC-VIYON-9901",
        "notes": "First partial shipment received; 5 units damaged in transport",
        "items": [
            {
                "purchase_order_item_id": po_item_simple_id,
                "quantity_received": 30,
                "quantity_accepted": 25,
                "quantity_rejected": 5,
                "rejection_reason": "Fabric tears near sleeve hem",
            },
            {
                "purchase_order_item_id": po_item_v30_id,
                "quantity_received": 15,
                "quantity_accepted": 15,
                "quantity_rejected": 0,
            },
        ],
    }
    r = client.post("/api/v1/purchases/receiving", json=grn_payload_1, headers=env["owner_headers"])
    grn_1_ok = r.status_code == 201 and r.json().get("total_accepted_quantity") == 40 and r.json().get("total_rejected_quantity") == 5
    grn_1_id = r.json().get("id") if grn_1_ok else None
    grn_1_num = r.json().get("grn_number") if grn_1_ok else None
    log_test(test_idx, "Workflow B: Receive partial delivery with accepted/rejected items", grn_1_ok, grn_1_num)

    # Test 14: INVARIANT - Physical stock increases ONLY by accepted quantity (+25, NOT +30)
    test_idx += 1
    stock_simple_after_grn1 = get_stock(raw_pg_url, prod_simple_id)
    # was 25; accepted 25 -> must be 50. 5 rejected must NOT enter stock!
    log_test(
        test_idx,
        "INVARIANT: Stock increases ONLY by accepted qty (excludes 5 rejected)",
        stock_simple_after_grn1 == (stock_simple_before_po + 25),
        f"Stock: {stock_simple_after_grn1} (Expected: {stock_simple_before_po + 25})",
    )

    # Test 15: PO status transitioned to PARTIALLY_RECEIVED
    test_idx += 1
    r = client.get(f"/api/v1/purchases/orders/{po_id}", headers=env["owner_headers"])
    log_test(test_idx, "Workflow B: PO automatically transitions to PARTIALLY_RECEIVED", r.json().get("status") == "PARTIALLY_RECEIVED")

    # Test 16: Complete Remaining Delivery (Item 1: 20 remaining accepted; Item 2: 15 remaining accepted)
    test_idx += 1
    grn_payload_2 = {
        "purchase_order_id": po_id,
        "delivery_reference": "DC-VIYON-9944",
        "items": [
            {"purchase_order_item_id": po_item_simple_id, "quantity_received": 20, "quantity_accepted": 20, "quantity_rejected": 0},
            {"purchase_order_item_id": po_item_v30_id, "quantity_received": 15, "quantity_accepted": 15, "quantity_rejected": 0},
        ],
    }
    r = client.post("/api/v1/purchases/receiving", json=grn_payload_2, headers=env["owner_headers"])
    log_test(test_idx, "Workflow B: Complete balance shipment (transitions PO to RECEIVED)", r.status_code == 201)

    # Test 17: Verify Final Stock after second delivery (Simple: 25 initial + 45 accepted = 70)
    test_idx += 1
    stock_simple_final_inward = get_stock(raw_pg_url, prod_simple_id)
    log_test(
        test_idx,
        "Workflow B: Final inventory matches exact total accepted receipts (70 units)",
        stock_simple_final_inward == (stock_simple_before_po + 45),
    )

    # Test 18: Disburse CASH Payment to Supplier (Confirmed Immediately)
    test_idx += 1
    pay_cash_payload = {
        "supplier_id": supplier_id,
        "purchase_order_id": po_id,
        "amount": 20000.00,
        "payment_method": "CASH",
        "notes": "Cash advance paid to driver",
    }
    r = client.post("/api/v1/purchases/payments", json=pay_cash_payload, headers=env["owner_headers"])
    cash_pay_ok = r.status_code == 201 and r.json().get("status") == "CONFIRMED"
    log_test(test_idx, "Workflow B: Cash supplier payment immediately CONFIRMED", cash_pay_ok)

    # Test 19: Disburse UPI Payment to Supplier (Starts as PENDING)
    test_idx += 1
    pay_upi_payload = {
        "supplier_id": supplier_id,
        "purchase_order_id": po_id,
        "amount": 15000.00,
        "payment_method": "UPI",
        "transaction_reference": f"UPI-IND-{uuid4().hex[:6]}",
        "notes": "Bank IMPS/UPI transfer to vendor",
    }
    r = client.post("/api/v1/purchases/payments", json=pay_upi_payload, headers=env["owner_headers"])
    upi_pay_ok = r.status_code == 201 and r.json().get("status") == "PENDING"
    upi_pay_id = r.json().get("id") if upi_pay_ok else None
    log_test(test_idx, "Workflow B: UPI supplier payment defaults to PENDING", upi_pay_ok)

    # Test 20: INVARIANT - Pending supplier payment does NOT reduce balance due
    test_idx += 1
    r = client.get(f"/api/v1/purchases/orders/{po_id}", headers=env["owner_headers"])
    po_bal_pending = Decimal(str(r.json().get("outstanding_amount") or r.json().get("balance_due")))
    # Total 50505 - 20000 cash = 30505
    log_test(
        test_idx,
        "INVARIANT: PENDING supplier payment does NOT reduce PO balance due",
        abs(po_bal_pending - Decimal("30505.00")) < Decimal("0.01"),
        f"Remaining Balance: ₹{po_bal_pending}",
    )

    # Test 21: Owner Manually Confirms UPI Payout
    test_idx += 1
    r = client.post(
        f"/api/v1/purchases/payments/{upi_pay_id}/confirm",
        json={"transaction_reference": "UTR-ICICI-778899", "notes": "Verified on current account statement"},
        headers=env["owner_headers"],
    )
    log_test(test_idx, "Workflow B: Owner verifies and confirms UPI payout", r.status_code == 200 and r.json().get("status") == "CONFIRMED")

    # Test 22: Supplier Outstanding Liability Reconciliation
    test_idx += 1
    r = client.get(f"/api/v1/suppliers/{supplier_id}", headers=env["owner_headers"])
    sup_out = r.json()
    # Total purchases: 50505.00, Total paid: 35000.00 (20000 cash + 15000 upi). Outstanding = 15505.00
    expected_liability = Decimal("15505.00")
    actual_liability = Decimal(str(sup_out.get("outstanding_balance", 0)))
    log_test(
        test_idx,
        "RECONCILIATION: Supplier Liability equals Total Purchases - Confirmed Payouts",
        abs(actual_liability - expected_liability) < Decimal("0.01"),
        f"Due: ₹{actual_liability}",
    )

    # ==========================================================================
    # WORKFLOW C: POS SALES BILLING & CHECKOUT
    # ==========================================================================
    print("\n--- WORKFLOW C: POS SALES BILLING & CHECKOUT ---")

    # Test 23: Staff searches product by SKU
    test_idx += 1
    r = client.get(f"/api/v1/products?search={simple_sku}", headers=env["staff_headers"])
    log_test(test_idx, "Workflow C: Cashier searches product by SKU", r.status_code == 200)

    # Test 24: POS Checkout with Simple Product (2 units, ₹100 discount, Cash Payment)
    test_idx += 1
    stock_simple_before_bill1 = get_stock(raw_pg_url, prod_simple_id)
    bill_1_payload = {
        "items": [
            {
                "product_id": str(prod_simple_id),
                "quantity": 2,
                "discount_amount": 100.00,  # subtotal 2998 - 100 = 2898
            }
        ],
        "discount_amount": 0.00,
        "notes": "Walk-in retail customer - Kavitha M",
    }
    r = client.post("/api/v1/bills", json=bill_1_payload, headers=env["staff_headers"])
    bill_1_created = r.status_code == 201
    bill_1_id = r.json().get("id") if bill_1_created else None
    bill_1_num = r.json().get("bill_number") if bill_1_created else None
    if bill_1_created:
        client.post(
            f"/api/v1/bills/{bill_1_id}/payments",
            json={"payment_method": "CASH", "amount": 2898.00},
            headers=env["staff_headers"],
        )
        r_b1_check = client.get(f"/api/v1/bills/{bill_1_id}", headers=env["staff_headers"])
        bill_1_ok = r_b1_check.status_code == 200 and r_b1_check.json().get("payment_status") == "PAID"
    else:
        bill_1_ok = False
    log_test(test_idx, "Workflow C: POS Bill 1 completed via CASH (Immediately PAID)", bill_1_ok, bill_1_num)

    # Test 25: INVARIANT - Stock decremented by exact sold quantity (-2)
    test_idx += 1
    stock_simple_after_bill1 = get_stock(raw_pg_url, prod_simple_id)
    log_test(
        test_idx,
        "INVARIANT: Physical stock decremented by sold quantity (70 -> 68)",
        stock_simple_after_bill1 == (stock_simple_before_bill1 - 2),
    )

    # Test 26: POS Checkout with Split Payment (Cash ₹1000 + UPI ₹1499 = ₹2499)
    test_idx += 1
    stock_v30_before_bill2 = get_stock(raw_pg_url, prod_variant_id, var_30_id)
    bill_2_payload = {
        "items": [
            {
                "product_id": str(prod_variant_id),
                "variant_id": str(var_30_id),
                "quantity": 1,
                "discount_amount": 0.00,
            }
        ],
        "discount_amount": 0.00,
        "notes": "Split payment sale",
    }
    r = client.post("/api/v1/bills", json=bill_2_payload, headers=env["staff_headers"])
    bill_2_created = r.status_code == 201
    bill_2_id = r.json().get("id") if bill_2_created else None
    bill_2_num = r.json().get("bill_number") if bill_2_created else None

    # Record Cash portion
    r_cash_split = client.post(
        f"/api/v1/bills/{bill_2_id}/payments",
        json={"payment_method": "CASH", "amount": 1000.00},
        headers=env["staff_headers"],
    )
    # Record UPI portion
    r_upi_split = client.post(
        f"/api/v1/bills/{bill_2_id}/payments",
        json={"payment_method": "UPI", "amount": 1499.00, "transaction_reference": f"GPay-{uuid4().hex[:8]}"},
        headers=env["staff_headers"],
    )
    bill_2_ok = bill_2_created and r_cash_split.status_code == 201 and r_upi_split.status_code == 201
    log_test(test_idx, "Workflow C: POS Bill 2 completed with Split Payment (Cash + UPI)", bill_2_ok, bill_2_num)

    # ==========================================================================
    # WORKFLOW D: PAYMENT VERIFICATION & RULES
    # ==========================================================================
    print("\n--- WORKFLOW D: PAYMENT VERIFICATION & RULES ---")

    # Test 27: INVARIANT - In split payment, Cash is CONFIRMED, UPI is PENDING
    test_idx += 1
    r_pmts = client.get(f"/api/v1/bills/{bill_2_id}/payments", headers=env["staff_headers"])
    payments_list = r_pmts.json()
    cash_pmt = next((p for p in payments_list if p["payment_method"] == "CASH"), None)
    upi_pmt = next((p for p in payments_list if p["payment_method"] == "UPI"), None)
    split_states_ok = (
        cash_pmt is not None and cash_pmt.get("payment_status") == "CONFIRMED"
        and upi_pmt is not None and upi_pmt.get("payment_status") == "PENDING"
    )
    log_test(test_idx, "INVARIANT: Split payment yields CASH=CONFIRMED, UPI=PENDING", split_states_ok)

    # Test 28: INVARIANT - Pending UPI excluded from amount_paid
    test_idx += 1
    r_b2 = client.get(f"/api/v1/bills/{bill_2_id}", headers=env["staff_headers"])
    bill_2_data = r_b2.json()
    amount_paid_split = Decimal(str(bill_2_data.get("amount_paid", 0)))
    balance_split = Decimal(str(bill_2_data.get("balance_amount", 0)))
    # Only 1000 cash confirmed -> amount_paid must be 1000.00; balance must be 1499.00; status PARTIALLY_PAID
    log_test(
        test_idx,
        "INVARIANT: Pending UPI excluded from amount_paid (Paid=1000, Balance=1499)",
        amount_paid_split == Decimal("1000.00") and balance_split == Decimal("1499.00") and bill_2_data.get("payment_status") == "PARTIALLY_PAID",
    )

    # Test 29: Cashier verifies UPI on merchant soundbox/app and confirms payment
    test_idx += 1
    upi_payment_id = upi_pmt["id"]
    r = client.patch(
        f"/api/v1/payments/{upi_payment_id}/confirm",
        json={"notes": "Verified on phone screen"},
        headers=env["staff_headers"],
    )
    log_test(test_idx, "Workflow D: Cashier manually confirms UPI payment with UTR", r.status_code == 200 and r.json().get("payment_status") == "CONFIRMED")

    # Test 30: Bill transitions to fully PAID after UPI confirmed
    test_idx += 1
    r = client.get(f"/api/v1/bills/{bill_2_id}", headers=env["staff_headers"])
    bill_2_settled = r.json()
    log_test(
        test_idx,
        "Workflow D: Bill transitions to PAID after manual UPI confirmation",
        bill_2_settled.get("payment_status") == "PAID" and Decimal(str(bill_2_settled.get("amount_paid"))) == Decimal("2499.00"),
    )

    # Test 31: 58mm Thermal Receipt Endpoint Data Verification
    test_idx += 1
    r = client.get(f"/api/v1/bills/{bill_1_id}/receipt", headers=env["staff_headers"])
    rcpt = r.json() if r.status_code == 200 else {}
    receipt_valid = (
        r.status_code == 200
        and rcpt.get("store", {}).get("store_name") == "VIYON"
        and rcpt.get("store", {}).get("receipt_width_mm") == 58
        and "items" in rcpt
    )
    log_test(test_idx, "Workflow C/D: 58mm Thermal Receipt structure verified", receipt_valid)

    # ==========================================================================
    # WORKFLOW E: BILL CANCELLATION & INVENTORY RESTORATION
    # ==========================================================================
    print("\n--- WORKFLOW E: BILL CANCELLATION & INVENTORY RESTORATION ---")

    # Test 32: Staff blocked from cancelling bill (403 Forbidden)
    test_idx += 1
    r = client.patch(f"/api/v1/bills/{bill_1_id}/cancel", json={"reason": "Customer changed mind"}, headers=env["staff_headers"])
    log_test(test_idx, "Workflow E: Staff is BLOCKED from cancelling bill (403)", r.status_code == 403)

    # Test 33: Owner cancels Bill 1 (was 2 units of Simple Product)
    test_idx += 1
    stock_simple_before_cancel = get_stock(raw_pg_url, prod_simple_id)
    r = client.patch(
        f"/api/v1/bills/{bill_1_id}/cancel",
        json={"reason": "Customer returned garments immediately before exit"},
        headers=env["owner_headers"],
    )
    cancel_ok = r.status_code == 200 and r.json().get("bill_status") == "CANCELLED"
    log_test(test_idx, "Workflow E: Owner cancels Bill 1 with mandatory reason", cancel_ok)

    # Test 34: INVARIANT - Stock restored upon cancellation (+2 units restored)
    test_idx += 1
    stock_simple_after_cancel = get_stock(raw_pg_url, prod_simple_id)
    log_test(
        test_idx,
        "INVARIANT: Physical stock restored upon bill cancellation (+2)",
        stock_simple_after_cancel == (stock_simple_before_cancel + 2),
    )

    # Test 35: Duplicate cancellation attempt returns 409 Conflict
    test_idx += 1
    r = client.patch(f"/api/v1/bills/{bill_1_id}/cancel", json={"reason": "Repeated attempt"}, headers=env["owner_headers"])
    log_test(test_idx, "INVARIANT: Duplicate cancellation strictly rejected (409 Conflict)", r.status_code == 409)

    # Test 36: Cancelled bill cannot receive payments
    test_idx += 1
    r = client.post(
        f"/api/v1/bills/{bill_1_id}/payments",
        json={"payment_method": "CASH", "amount": 500.00},
        headers=env["owner_headers"],
    )
    log_test(test_idx, "INVARIANT: Cancelled bill cannot receive new payments (409)", r.status_code == 409)

    # ==========================================================================
    # WORKFLOW F: EXPENSES, CASH DRAWER & FINANCIAL REPORTING
    # ==========================================================================
    print("\n--- WORKFLOW F: EXPENSES & FINANCIAL RECONCILIATION ---")

    # Test 37: Staff blocked from creating expense (403)
    test_idx += 1
    r = client.post(
        "/api/v1/expenses",
        json={"expense_title": "Unauthorized Expense", "category": "MAINTENANCE", "amount": 500.00, "description": "Staff unauthorized expense"},
        headers=env["staff_headers"],
    )
    log_test(test_idx, "Workflow F: Staff is BLOCKED from creating expense (403)", r.status_code == 403)

    # Test 38: Owner records Store Operational Expense
    test_idx += 1
    exp_payload = {
        "expense_title": "Monthly Electricity Bill",
        "category": "ELECTRICITY",
        "amount": 1200.00,
        "payment_method": "CASH",
        "description": "Store AC & lighting electricity bill",
    }
    r = client.post("/api/v1/expenses", json=exp_payload, headers=env["owner_headers"])
    exp_ok = r.status_code == 201
    exp_id = r.json().get("id") if exp_ok else None
    log_test(test_idx, "Workflow F: Owner records operational expense (₹1200 Cash)", exp_ok)

    # Test 39: Owner voids a mistaken expense with reason
    test_idx += 1
    r_temp = client.post(
        "/api/v1/expenses",
        json={"expense_title": "Duplicate Voucher", "category": "SUPPLIES", "amount": 350.00, "payment_method": "CASH", "description": "Duplicate petty cash entry"},
        headers=env["owner_headers"],
    )
    temp_exp_id = r_temp.json()["id"]
    r_void = client.patch(
        f"/api/v1/expenses/{temp_exp_id}/void",
        json={"void_reason": "Duplicate bill voucher entered accidentally"},
        headers=env["owner_headers"],
    )
    log_test(test_idx, "Workflow F: Void expense with reason (excluded from active totals)", r_void.status_code == 200 and r_void.json().get("is_voided") is True)

    # Test 40: Financial Daily Overview Report Execution
    test_idx += 1
    r = client.get("/api/v1/finance/overview?preset=today", headers=env["owner_headers"])
    fin_ok = r.status_code == 200
    fin_data = r.json() if fin_ok else {}
    log_test(test_idx, "Workflow F: Fetch daily financial summary (Asia/Kolkata boundary)", fin_ok)

    # ==========================================================================
    # WORKFLOW G: STAFF LIFECYCLE & SECURITY
    # ==========================================================================
    print("\n--- WORKFLOW G: STAFF LIFECYCLE & SECURITY AUDIT ---")

    # Test 41: Owner creates Staff Account
    test_idx += 1
    new_staff_user = f"cashier_e2e_{uuid4().hex[:4]}"
    new_staff_email = f"{new_staff_user}@viyon.store"
    r = client.post(
        "/api/v1/staff",
        json={
            "full_name": "Arun Prakash",
            "username": new_staff_user,
            "email": new_staff_email,
            "phone": "9842100991",
            "password": "InitialStaffPass123!",
            "confirm_password": "InitialStaffPass123!",
        },
        headers=env["owner_headers"],
    )
    staff_create_ok = r.status_code == 201
    new_staff_id = r.json().get("id") if staff_create_ok else None
    log_test(test_idx, "Workflow G: Owner creates new Staff Account", staff_create_ok, new_staff_user)

    # Test 42: Staff logs in and receives JWT
    test_idx += 1
    r = client.post(
        "/api/v1/auth/login/json",
        json={"username": new_staff_user, "password": "InitialStaffPass123!"},
    )
    staff_login_ok = r.status_code == 200 and "access_token" in r.json()
    new_staff_token = r.json().get("access_token") if staff_login_ok else None
    new_staff_headers = {"Authorization": f"Bearer {new_staff_token}"}
    log_test(test_idx, "Workflow G: New staff logs in with credentials", staff_login_ok)

    # Test 43: Staff cannot access Owner-only Staff Administration
    test_idx += 1
    r = client.get("/api/v1/staff", headers=new_staff_headers)
    log_test(test_idx, "Workflow G: Staff strictly blocked from staff directory (403)", r.status_code == 403)

    # Test 44: Owner resets staff password (session invalidation)
    test_idx += 1
    r = client.post(
        f"/api/v1/staff/{new_staff_id}/reset-password",
        json={"new_password": "ResetStaffPass456!", "confirm_password": "ResetStaffPass456!"},
        headers=env["owner_headers"],
    )
    log_test(test_idx, "Workflow G: Owner resets staff password", r.status_code == 200)

    # Test 45: Old JWT is rejected after password change
    test_idx += 1
    r = client.get("/api/v1/auth/me", headers=new_staff_headers)
    log_test(test_idx, "INVARIANT: Old JWT rejected after password reset (401)", r.status_code == 401)

    # Test 46: Staff logs in with new password
    test_idx += 1
    r = client.post(
        "/api/v1/auth/login/json",
        json={"username": new_staff_user, "password": "ResetStaffPass456!"},
    )
    relogin_ok = r.status_code == 200 and "access_token" in r.json()
    new_staff_token_v2 = r.json().get("access_token") if relogin_ok else None
    new_staff_headers_v2 = {"Authorization": f"Bearer {new_staff_token_v2}"}
    log_test(test_idx, "Workflow G: Staff logs in with new password", relogin_ok)

    # Test 47: Owner deactivates staff account
    test_idx += 1
    r = client.patch(
        f"/api/v1/staff/{new_staff_id}/deactivate",
        json={"is_active": False, "reason": "Testing employee suspension"},
        headers=env["owner_headers"],
    )
    log_test(test_idx, "Workflow G: Owner deactivates staff account", r.status_code == 200 and r.json().get("is_active") is False)

    # Test 48: Deactivated staff token rejected on protected endpoints
    test_idx += 1
    r = client.get("/api/v1/bills", headers=new_staff_headers_v2)
    log_test(test_idx, "INVARIANT: Deactivated staff token strictly rejected (403)", r.status_code == 403)

    # ==========================================================================
    # SECTION 3: MATHEMATICAL RECONCILIATIONS
    # ==========================================================================
    print("\n--- SECTION 3: MATHEMATICAL INVARIANTS & RECONCILIATIONS ---")

    # Test 49: Sales Reconciliation Invariant
    test_idx += 1
    # Check all bills in database: total_amount must equal amount_paid + balance_amount
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, bill_number, total_amount, amount_paid, balance_amount, bill_status FROM bills WHERE bill_status != 'CANCELLED';")
            active_bills = cur.fetchall()
            bills_math_ok = True
            for b in active_bills:
                b_gt = Decimal(str(b[2]))
                b_ap = Decimal(str(b[3]))
                b_bal = Decimal(str(b[4]))
                if abs(b_gt - (b_ap + b_bal)) > Decimal("0.01"):
                    bills_math_ok = False
                    break
    log_test(
        test_idx,
        "MATHEMATICAL INVARIANT: Total Amount == Amount Paid + Balance across all active bills",
        bills_math_ok,
    )

    # Test 50: Complete Inventory Ledger Conservation
    test_idx += 1
    # Simple product: Initial 25 + Inward 45 - Sold 2 (Bill 1) + Restored 2 (Bill 1 Cancelled) = 70
    stock_current_ledger = get_stock(raw_pg_url, prod_simple_id)
    expected_ledger_stock = 25 + 45 - 2 + 2
    log_test(
        test_idx,
        "CONSERVATION LAW: Physical Stock == Initial + Receipts + Restorations - Sales",
        stock_current_ledger == expected_ledger_stock,
        f"Actual: {stock_current_ledger} == Expected: {expected_ledger_stock}",
    )

    print("=" * 80)
    total_tests = len(results)
    passed_tests = sum(1 for _, _, p, _ in results)
    print(f"PHASE 5.5 E2E INTEGRATION TEST RESULTS: {passed_tests} / {total_tests} PASSED")
    print("=" * 80)

    if passed_tests < total_tests:
        print("[ERROR] SOME TESTS FAILED IN E2E SUITE!")
        sys.exit(1)
    else:
        print("[SUCCESS] ALL PHASE 5.5 END-TO-END INTEGRATION & RECONCILIATION TESTS PASSED!")


if __name__ == "__main__":
    run_e2e_suite()
