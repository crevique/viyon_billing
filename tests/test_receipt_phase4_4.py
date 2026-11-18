"""VIYON Billing System - Phase 4.4 Automated Test Suite
Testing Receipt Generation, 58mm Thermal Layout, Historical Snapshots,
Payment Breakdown & SEZNIK Veer Compatibility.

Target Database: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh).
Guarantees 100% isolation: Neon production database is NEVER connected to or modified.

Covers all 24 required & extended scenarios:
1. Receipt data for a valid bill.
2. Unknown bill returns 404.
3. Historical product name is used (frozen snapshot immunity).
4. Historical unit price is used (frozen price immunity).
5. Historical discount is used.
6. Tax values are correct.
7. Confirmed cash payment is displayed.
8. Confirmed UPI payment is displayed.
9. Split payments are displayed correctly.
10. Pending UPI is not included in amount paid (shown separately).
11. Balance is correct.
12. Partially paid bill receipt.
13. Fully paid bill receipt.
14. Cancelled bill receipt.
15. Cancelled bill displays cancellation information & refund review.
16. Receipt by bill number (/api/v1/bills/receipt/by-number/{bill_number}).
17. Unauthorized access is blocked (401).
18. Receipt retrieval does not modify inventory (read-only verification).
19. Receipt retrieval does not modify payments.
20. Receipt retrieval does not modify bill totals.
21. Monospace 32-column formatting accuracy (SEZNIK Veer 58mm).
22. Receipt preview endpoint (/api/v1/bills/{bill_id}/receipt/preview).
23. Receipt print audit logging (RECEIPT_PRINTED & RECEIPT_REPRINTED).
24. Reprint indicator displayed on duplicate copy.
"""

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import psycopg
from fastapi import status
from fastapi.testclient import TestClient

# ------------------------------------------------------------------------------
# 1. Force Isolated Test Database (NEVER TOUCH PRODUCTION NEON!)
# ------------------------------------------------------------------------------
TEST_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/viyon_test_fresh"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["SECRET_KEY"] = "test-secret-key-phase4-4-secure-random-at-least-32-chars"
os.environ["ENVIRONMENT"] = "test"

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from alembic import command
from alembic.config import Config
from app.core.security import create_access_token, get_password_hash
from app.main import app


def setup_test_data() -> Tuple[Dict[str, str], Dict[str, str], UUID, UUID, UUID, UUID, UUID, UUID]:
    """Ensure database is migrated to head and seeded with test catalogue, inventory, and users."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(cfg, "head")

    raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    owner_id = uuid4()
    staff_id = uuid4()
    cat_id = uuid4()
    simple_prod_id = uuid4()
    variant_prod_id = uuid4()
    variant_id = uuid4()
    cust_id = uuid4()

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            # 1. Owner & Staff
            cur.execute("SELECT id FROM users WHERE role = 'OWNER' LIMIT 1;")
            r_owner = cur.fetchone()
            if r_owner:
                owner_id = r_owner[0]
            else:
                pw_hash = get_password_hash("OwnerPass123!")
                cur.execute(
                    "INSERT INTO users (id, full_name, email, password_hash, role, is_active) "
                    "VALUES (%s, 'Store Owner', 'owner_p44@viyon.store', %s, 'OWNER', true);",
                    (owner_id, pw_hash),
                )

            cur.execute("SELECT id FROM users WHERE role = 'STAFF' LIMIT 1;")
            r_staff = cur.fetchone()
            if r_staff:
                staff_id = r_staff[0]
            else:
                pw_hash = get_password_hash("StaffPass123!")
                cur.execute(
                    "INSERT INTO users (id, full_name, email, password_hash, role, is_active) "
                    "VALUES (%s, 'Cashier Staff', 'staff_p44@viyon.store', %s, 'STAFF', true);",
                    (staff_id, pw_hash),
                )

            # 2. Store Settings
            cur.execute(
                """
                INSERT INTO store_settings (
                    id, store_name, tagline, address, phone, receipt_footer,
                    currency_code, tax_enabled, default_tax_rate, receipt_width_mm, is_active_config
                ) VALUES (
                    gen_random_uuid(), 'VIYON', 'MEN''S | KID''S WEAR',
                    'F6WR+R8W, South Rangasamuthram, North Rangasamuthram, Sathyamangalam, Tamil Nadu 638402',
                    '082702 42681', 'Thank you for shopping at VIYON! Visit again.',
                    'INR', false, 0.00, 58, true
                ) ON CONFLICT DO NOTHING;
                """
            )

            # 3. Category
            cur.execute("SELECT id FROM categories WHERE name = 'Receipt Test Apparel' LIMIT 1;")
            r_cat = cur.fetchone()
            if r_cat:
                cat_id = r_cat[0]
            else:
                cur.execute(
                    "INSERT INTO categories (id, name, is_active) VALUES (%s, 'Receipt Test Apparel', true);",
                    (cat_id,),
                )

            # 4. Simple Product (Price: 1000.00, Stock: 50)
            tag = uuid4().hex[:6]
            sku_simple = f"SKU-SIMPLE-{tag}".upper()
            cur.execute(
                "INSERT INTO products (id, category_id, product_name, product_type, base_price, sku, is_active, is_archived) "
                "VALUES (%s, %s, 'Premium Linen Shirt', 'SIMPLE', 1000.00, %s, true, false);",
                (simple_prod_id, cat_id, sku_simple),
            )
            cur.execute(
                "INSERT INTO inventory (id, product_id, variant_id, quantity, low_stock_threshold) "
                "VALUES (gen_random_uuid(), %s, NULL, 50, 5);",
                (simple_prod_id,),
            )

            # 5. Variant Product (Base: 1500.00, Variant Price Override: 1600.00, Stock: 30)
            sku_var = f"SKU-CHINO-{tag}".upper()
            cur.execute(
                "INSERT INTO products (id, category_id, product_name, product_type, base_price, is_active, is_archived) "
                "VALUES (%s, %s, 'Cotton Chino Pants', 'VARIANT', 1500.00, true, false);",
                (variant_prod_id, cat_id),
            )
            cur.execute(
                "INSERT INTO product_variants (id, product_id, size, color, sku, price_override, is_active) "
                "VALUES (%s, %s, '32', 'NAVY', %s, 1600.00, true);",
                (variant_id, variant_prod_id, sku_var),
            )
            cur.execute(
                "INSERT INTO inventory (id, product_id, variant_id, quantity, low_stock_threshold) "
                "VALUES (gen_random_uuid(), %s, %s, 30, 5);",
                (variant_prod_id, variant_id),
            )

            # 6. Customer
            cur.execute(
                "INSERT INTO customers (id, customer_name, phone) VALUES (%s, 'Karthik Raman', '9876543210');",
                (cust_id,),
            )
            conn.commit()

    owner_token = create_access_token(subject=str(owner_id), role="OWNER")
    staff_token = create_access_token(subject=str(staff_id), role="STAFF")

    return (
        {"Authorization": f"Bearer {owner_token}"},
        {"Authorization": f"Bearer {staff_token}"},
        owner_id,
        staff_id,
        simple_prod_id,
        variant_prod_id,
        variant_id,
        cust_id,
    )


def run_phase4_4_receipt_tests():
    """Execute all Phase 4.4 receipt generation, printing, and audit tests."""
    print("=" * 80)
    print("VIYON PHASE 4.4: 58mm THERMAL RECEIPT GENERATION & PRINTING TEST SUITE")
    print(f"Target DB: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh)")
    print("=" * 80)

    client = TestClient(app)
    (
        owner_auth,
        staff_auth,
        owner_id,
        staff_id,
        simple_prod_id,
        variant_prod_id,
        variant_id,
        cust_id,
    ) = setup_test_data()

    results: List[Tuple[str, str]] = []

    # Helper: Create Bill
    def create_bill(items: List[Dict], customer: Optional[UUID] = None, discount: float = 0.0) -> Dict:
        payload = {
            "customer_id": str(customer) if customer else None,
            "items": items,
            "discount_amount": str(discount),
        }
        res = client.post("/api/v1/bills", json=payload, headers=staff_auth)
        assert res.status_code == status.HTTP_201_CREATED, res.text
        return res.json()

    # --------------------------------------------------------------------------
    # Test 1: Receipt data for a valid bill
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Receipt data for a valid bill...")
    b1 = create_bill(
        items=[{"product_id": str(simple_prod_id), "quantity": 2, "discount_amount": "50.00"}],
        customer=cust_id,
        discount=100.0,
    )
    # Gross: 2 * 1000 = 2000. Item disc: 50. Bill disc: 100. Total disc: 150. Total: 1850.
    r1 = client.get(f"/api/v1/bills/{b1['id']}/receipt", headers=staff_auth)
    assert r1.status_code == status.HTTP_200_OK, r1.text
    rec1 = r1.json()

    assert rec1["bill_id"] == b1["id"]
    assert rec1["bill_number"] == b1["bill_number"]
    assert rec1["store"]["store_name"] == "VIYON"
    assert rec1["store"]["phone"] == "082702 42681"
    assert rec1["customer"]["full_name"] == "Karthik Raman"
    assert rec1["customer"]["phone_number"] == "9876543210"
    assert len(rec1["items"]) == 1
    assert rec1["items"][0]["product_name"] == "Premium Linen Shirt"
    assert rec1["subtotal"] == "2000.00"
    assert rec1["item_discount_total"] == "50.00"
    assert rec1["bill_discount_amount"] == "100.00"
    assert rec1["discount_amount"] == "150.00"
    assert rec1["grand_total"] == "1850.00"
    assert rec1["amount_paid"] == "0.00"
    assert rec1["balance"] == "1850.00"
    assert rec1["is_cancelled"] is False
    assert len(rec1["raw_text"]) > 0
    print(f"         Receipt generated: Bill No {rec1['bill_number']} | Grand Total: Rs. {rec1['grand_total']}")
    results.append(("1. Receipt data for a valid bill", "PASS"))

    # --------------------------------------------------------------------------
    # Test 2: Unknown bill returns 404
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Unknown bill returns 404...")
    fake_id = uuid4()
    r2 = client.get(f"/api/v1/bills/{fake_id}/receipt", headers=staff_auth)
    assert r2.status_code == status.HTTP_404_NOT_FOUND
    assert f"Bill with ID '{fake_id}' was not found" in r2.json()["detail"]
    print("         404 accurately returned for non-existent bill UUID.")
    results.append(("2. Unknown bill returns 404", "PASS"))

    # --------------------------------------------------------------------------
    # Test 3: Historical product name is preserved (frozen snapshot immunity)
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Historical product name is preserved...")
    # Change product name in database catalog directly
    raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE products SET product_name = 'MODIFIED Linen Shirt v2' WHERE id = %s;",
                (simple_prod_id,),
            )
            conn.commit()

    # Re-fetch receipt for bill b1: must still show original frozen snapshot 'Premium Linen Shirt'
    r3 = client.get(f"/api/v1/bills/{b1['id']}/receipt", headers=staff_auth)
    assert r3.status_code == status.HTTP_200_OK
    assert r3.json()["items"][0]["product_name"] == "Premium Linen Shirt"
    print("         Confirmed: Catalog product renaming does not affect historical receipt snapshot.")
    results.append(("3. Historical product name is preserved", "PASS"))

    # Restore product name
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE products SET product_name = 'Premium Linen Shirt' WHERE id = %s;",
                (simple_prod_id,),
            )
            conn.commit()

    # --------------------------------------------------------------------------
    # Test 4: Historical unit price is preserved
    # --------------------------------------------------------------------------
    print("\n[TEST 4] Historical unit price is preserved...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE products SET base_price = 9999.00 WHERE id = %s;",
                (simple_prod_id,),
            )
            conn.commit()

    r4 = client.get(f"/api/v1/bills/{b1['id']}/receipt", headers=staff_auth)
    assert r4.status_code == status.HTTP_200_OK
    assert r4.json()["items"][0]["unit_price"] == "1000.00"
    assert r4.json()["subtotal"] == "2000.00"
    print("         Confirmed: Catalog base price modification does not affect historical receipt unit price.")
    results.append(("4. Historical unit price is preserved", "PASS"))

    # Restore base price
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE products SET base_price = 1000.00 WHERE id = %s;",
                (simple_prod_id,),
            )
            conn.commit()

    # --------------------------------------------------------------------------
    # Test 5: Historical discount is used
    # --------------------------------------------------------------------------
    print("\n[TEST 5] Historical discount is used...")
    rec5 = r4.json()
    assert rec5["item_discount_total"] == "50.00"
    assert rec5["bill_discount_amount"] == "100.00"
    assert rec5["discount_amount"] == "150.00"
    print("         Confirmed: Both item discount and bill discount accurately reflected.")
    results.append(("5. Historical discount is used", "PASS"))

    # --------------------------------------------------------------------------
    # Test 6: Tax values are correct
    # --------------------------------------------------------------------------
    print("\n[TEST 6] Tax values are correct...")
    # Store settings has tax_enabled = False -> tax is 0.00
    assert rec5["tax_amount"] == "0.00"
    assert rec5["items"][0]["tax_amount"] == "0.00"
    print("         Confirmed: Tax amounts accurately reflect stored financial values.")
    results.append(("6. Tax values are correct", "PASS"))

    # --------------------------------------------------------------------------
    # Test 7: Confirmed cash payment is displayed
    # --------------------------------------------------------------------------
    print("\n[TEST 7] Confirmed cash payment is displayed...")
    b7 = create_bill(items=[{"product_id": str(simple_prod_id), "quantity": 1}])  # Total: 1000.00
    p7_pay = client.post(
        f"/api/v1/bills/{b7['id']}/payments",
        json={"payment_method": "CASH", "amount": 1000.00},
        headers=staff_auth,
    )
    assert p7_pay.status_code == status.HTTP_201_CREATED

    r7 = client.get(f"/api/v1/bills/{b7['id']}/receipt", headers=staff_auth)
    assert r7.status_code == status.HTTP_200_OK
    rec7 = r7.json()
    assert rec7["payment_method"] == "CASH"
    assert rec7["payment_breakdown"]["confirmed_cash"] == "1000.00"
    assert rec7["payment_breakdown"]["confirmed_upi"] == "0.00"
    assert rec7["amount_paid"] == "1000.00"
    assert rec7["balance"] == "0.00"
    print("         Confirmed: Full cash payment accurately reflected on receipt.")
    results.append(("7. Confirmed cash payment is displayed", "PASS"))

    # --------------------------------------------------------------------------
    # Test 8: Confirmed UPI payment is displayed
    # --------------------------------------------------------------------------
    print("\n[TEST 8] Confirmed UPI payment is displayed...")
    b8 = create_bill(items=[{"product_id": str(simple_prod_id), "quantity": 1}])
    utr8 = f"UPI-REC-{uuid4().hex[:6]}".upper()
    p8_pay = client.post(
        f"/api/v1/bills/{b8['id']}/payments",
        json={"payment_method": "UPI", "amount": 1000.00, "transaction_reference": utr8},
        headers=staff_auth,
    )
    assert p8_pay.status_code == status.HTTP_201_CREATED
    client.patch(f"/api/v1/payments/{p8_pay.json()['id']}/confirm", json={}, headers=staff_auth)

    r8 = client.get(f"/api/v1/bills/{b8['id']}/receipt", headers=staff_auth)
    assert r8.status_code == status.HTTP_200_OK
    rec8 = r8.json()
    assert rec8["payment_method"] == "UPI"
    assert rec8["payment_breakdown"]["confirmed_upi"] == "1000.00"
    assert rec8["payment_breakdown"]["confirmed_cash"] == "0.00"
    assert rec8["amount_paid"] == "1000.00"
    assert rec8["balance"] == "0.00"
    print("         Confirmed: Full UPI payment accurately reflected on receipt.")
    results.append(("8. Confirmed UPI payment is displayed", "PASS"))

    # --------------------------------------------------------------------------
    # Test 9: Split payments are displayed correctly
    # --------------------------------------------------------------------------
    print("\n[TEST 9] Split payments are displayed correctly...")
    # Bill total 2000: Pay 1200 CASH + 800 UPI
    b9 = create_bill(items=[{"product_id": str(simple_prod_id), "quantity": 2}])
    p9_cash = client.post(
        f"/api/v1/bills/{b9['id']}/payments",
        json={"payment_method": "CASH", "amount": 1200.00},
        headers=staff_auth,
    )
    assert p9_cash.status_code == status.HTTP_201_CREATED
    utr9 = f"UPI-SPLIT-{uuid4().hex[:6]}".upper()
    p9_upi = client.post(
        f"/api/v1/bills/{b9['id']}/payments",
        json={"payment_method": "UPI", "amount": 800.00, "transaction_reference": utr9},
        headers=staff_auth,
    )
    assert p9_upi.status_code == status.HTTP_201_CREATED
    client.patch(f"/api/v1/payments/{p9_upi.json()['id']}/confirm", json={}, headers=staff_auth)

    r9 = client.get(f"/api/v1/bills/{b9['id']}/receipt", headers=staff_auth)
    assert r9.status_code == status.HTTP_200_OK
    rec9 = r9.json()
    assert rec9["payment_method"] == "SPLIT (CASH + UPI)"
    assert rec9["payment_breakdown"]["confirmed_cash"] == "1200.00"
    assert rec9["payment_breakdown"]["confirmed_upi"] == "800.00"
    assert rec9["amount_paid"] == "2000.00"
    assert rec9["balance"] == "0.00"
    print("         Confirmed: Split payment breakdown matches cash and UPI parts.")
    results.append(("9. Split payments are displayed correctly", "PASS"))

    # --------------------------------------------------------------------------
    # Test 10: Pending UPI is not included in amount paid
    # --------------------------------------------------------------------------
    print("\n[TEST 10] Pending UPI is not included in amount paid...")
    b10 = create_bill(items=[{"product_id": str(simple_prod_id), "quantity": 1}])  # Total: 1000.00
    utr10 = f"UPI-PEND-{uuid4().hex[:6]}".upper()
    p10_pay = client.post(
        f"/api/v1/bills/{b10['id']}/payments",
        json={"payment_method": "UPI", "amount": 1000.00, "transaction_reference": utr10, "confirm_immediately": False},
        headers=staff_auth,
    )
    assert p10_pay.status_code == status.HTTP_201_CREATED

    r10 = client.get(f"/api/v1/bills/{b10['id']}/receipt", headers=staff_auth)
    assert r10.status_code == status.HTTP_200_OK
    rec10 = r10.json()
    assert rec10["payment_breakdown"]["has_pending_upi"] is True
    assert rec10["payment_breakdown"]["pending_upi"] == "1000.00"
    assert rec10["payment_breakdown"]["confirmed_upi"] == "0.00"
    assert rec10["amount_paid"] == "0.00"  # MUST BE 0.00!
    assert rec10["balance"] == "1000.00"
    assert "*** UPI PAYMENT PENDING ***" in rec10["raw_text"]
    print("         Confirmed: Pending UPI is isolated and NOT added to amount_paid.")
    results.append(("10. Pending UPI is not included in amount paid", "PASS"))

    # --------------------------------------------------------------------------
    # Test 11: Balance is correct
    # --------------------------------------------------------------------------
    print("\n[TEST 11] Balance calculation accuracy...")
    b11 = create_bill(items=[{"product_id": str(simple_prod_id), "quantity": 2}])  # Total: 2000.00
    client.post(
        f"/api/v1/bills/{b11['id']}/payments",
        json={"payment_method": "CASH", "amount": 750.00},
        headers=staff_auth,
    )
    r11 = client.get(f"/api/v1/bills/{b11['id']}/receipt", headers=staff_auth)
    assert r11.status_code == status.HTTP_200_OK
    rec11 = r11.json()
    assert rec11["amount_paid"] == "750.00"
    assert rec11["balance"] == "1250.00"
    print("         Confirmed: Outstanding balance (1250.00) matches total - amount_paid.")
    results.append(("11. Balance is correct", "PASS"))

    # --------------------------------------------------------------------------
    # Test 12: Partially paid bill receipt
    # --------------------------------------------------------------------------
    print("\n[TEST 12] Partially paid bill receipt...")
    assert rec11["payment_status"] == "PARTIALLY_PAID"
    assert "Balance Due:               Rs. 1250.00" in rec11["raw_text"] or "1250.00" in rec11["raw_text"]
    print("         Confirmed: PARTIALLY_PAID status and remaining balance printed.")
    results.append(("12. Partially paid bill receipt", "PASS"))

    # --------------------------------------------------------------------------
    # Test 13: Fully paid bill receipt
    # --------------------------------------------------------------------------
    print("\n[TEST 13] Fully paid bill receipt...")
    assert rec7["payment_status"] == "PAID"
    assert rec7["balance"] == "0.00"
    print("         Confirmed: Fully paid bill shows PAID status and zero balance.")
    results.append(("13. Fully paid bill receipt", "PASS"))

    # --------------------------------------------------------------------------
    # Test 14: Cancelled bill receipt
    # --------------------------------------------------------------------------
    print("\n[TEST 14] Cancelled bill receipt...")
    b14 = create_bill(items=[{"product_id": str(simple_prod_id), "quantity": 1}])
    cancel_res = client.patch(
        f"/api/v1/bills/{b14['id']}/cancel",
        json={"reason": "Customer cancelled order before packing"},
        headers=owner_auth,
    )
    assert cancel_res.status_code == status.HTTP_200_OK

    r14 = client.get(f"/api/v1/bills/{b14['id']}/receipt", headers=staff_auth)
    assert r14.status_code == status.HTTP_200_OK
    rec14 = r14.json()
    assert rec14["is_cancelled"] is True
    assert rec14["bill_status"] == "CANCELLED"
    assert "*** BILL CANCELLED ***" in rec14["raw_text"]
    print("         Confirmed: Cancelled bill flagged with is_cancelled=True and warning banner.")
    results.append(("14. Cancelled bill receipt", "PASS"))

    # --------------------------------------------------------------------------
    # Test 15: Cancelled bill displays cancellation information & refund review
    # --------------------------------------------------------------------------
    print("\n[TEST 15] Cancelled bill displays cancellation information & refund review...")
    # Bill with confirmed payment, then cancelled
    b15 = create_bill(items=[{"product_id": str(simple_prod_id), "quantity": 1}])
    client.post(
        f"/api/v1/bills/{b15['id']}/payments",
        json={"payment_method": "CASH", "amount": 1000.00},
        headers=staff_auth,
    )
    client.patch(
        f"/api/v1/bills/{b15['id']}/cancel",
        json={"reason": "Fabric defect discovered by customer"},
        headers=owner_auth,
    )

    r15 = client.get(f"/api/v1/bills/{b15['id']}/receipt", headers=staff_auth)
    assert r15.status_code == status.HTTP_200_OK
    rec15 = r15.json()
    assert rec15["cancellation_details"] is not None
    assert rec15["cancellation_details"]["cancellation_reason"] == "Fabric defect discovered by customer"
    assert rec15["cancellation_details"]["refund_review_amount"] == "1000.00"
    assert "Fabric defect discovered" in rec15["raw_text"]
    assert "Refund Review:" in rec15["raw_text"]
    print("         Confirmed: Cancellation reason and refund review amount clearly printed.")
    results.append(("15. Cancelled bill displays cancellation info & refund review", "PASS"))

    # --------------------------------------------------------------------------
    # Test 16: Receipt by bill number
    # --------------------------------------------------------------------------
    print("\n[TEST 16] Receipt by bill number...")
    r16 = client.get(f"/api/v1/bills/receipt/by-number/{b1['bill_number']}", headers=staff_auth)
    assert r16.status_code == status.HTTP_200_OK
    assert r16.json()["bill_number"] == b1["bill_number"]

    # Non-existent bill number returns 404
    r16_fake = client.get("/api/v1/bills/receipt/by-number/VIYON-NONEXISTENT-999", headers=staff_auth)
    assert r16_fake.status_code == status.HTTP_404_NOT_FOUND
    print("         Confirmed: /receipt/by-number/{bill_number} retrieved valid receipt and 404 on missing.")
    results.append(("16. Receipt by bill number", "PASS"))

    # --------------------------------------------------------------------------
    # Test 17: Unauthorized access is blocked
    # --------------------------------------------------------------------------
    print("\n[TEST 17] Unauthorized access is blocked...")
    r17 = client.get(f"/api/v1/bills/{b1['id']}/receipt")
    assert r17.status_code == status.HTTP_401_UNAUTHORIZED
    print("         401 accurately returned for unauthenticated request.")
    results.append(("17. Unauthorized access is blocked", "PASS"))

    # --------------------------------------------------------------------------
    # Test 18: Receipt retrieval does not modify inventory
    # --------------------------------------------------------------------------
    print("\n[TEST 18] Receipt retrieval does not modify inventory...")
    # Check inventory before
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_prod_id,))
            r_ib = cur.fetchone()
            inv_before = r_ib[0] if r_ib else 0

    # Call receipt endpoint multiple times
    for _ in range(5):
        client.get(f"/api/v1/bills/{b1['id']}/receipt", headers=staff_auth)

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_prod_id,))
            r_ia = cur.fetchone()
            inv_after = r_ia[0] if r_ia else 0

    assert inv_before == inv_after
    print(f"         Confirmed: Inventory quantity strictly unchanged ({inv_before} == {inv_after}).")
    results.append(("18. Receipt retrieval does not modify inventory", "PASS"))

    # --------------------------------------------------------------------------
    # Test 19: Receipt retrieval does not modify payments
    # --------------------------------------------------------------------------
    print("\n[TEST 19] Receipt retrieval does not modify payments...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*), coalesce(sum(amount), 0) FROM payments WHERE bill_id = %s;", (UUID(b7['id']),))
            pay_before = cur.fetchone()

    for _ in range(5):
        client.get(f"/api/v1/bills/{b7['id']}/receipt", headers=staff_auth)

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*), coalesce(sum(amount), 0) FROM payments WHERE bill_id = %s;", (UUID(b7['id']),))
            pay_after = cur.fetchone()

    assert pay_before == pay_after
    print(f"         Confirmed: Payment records strictly unchanged.")
    results.append(("19. Receipt retrieval does not modify payments", "PASS"))

    # --------------------------------------------------------------------------
    # Test 20: Receipt retrieval does not modify bill totals
    # --------------------------------------------------------------------------
    print("\n[TEST 20] Receipt retrieval does not modify bill totals...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT subtotal, discount_amount, tax_amount, total_amount, amount_paid, balance_amount "
                "FROM bills WHERE id = %s;",
                (UUID(b1['id']),),
            )
            bill_before = cur.fetchone()

    for _ in range(5):
        client.get(f"/api/v1/bills/{b1['id']}/receipt", headers=staff_auth)

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT subtotal, discount_amount, tax_amount, total_amount, amount_paid, balance_amount "
                "FROM bills WHERE id = %s;",
                (UUID(b1['id']),),
            )
            bill_after = cur.fetchone()

    assert bill_before == bill_after
    print(f"         Confirmed: Bill totals strictly unchanged.")
    results.append(("20. Receipt retrieval does not modify bill totals", "PASS"))

    # --------------------------------------------------------------------------
    # Test 21: Monospace 32-column formatting accuracy (SEZNIK Veer 58mm)
    # --------------------------------------------------------------------------
    print("\n[TEST 21] Monospace 32-column formatting accuracy...")
    raw_lines = rec1["raw_text"].split("\n")
    max_len = max(len(line) for line in raw_lines)
    assert max_len <= 32, f"Line exceeded 32 columns: {max_len}"
    print(f"         Confirmed: All receipt lines fit strictly within 32 columns (max line = {max_len}).")
    results.append(("21. Monospace 32-column formatting accuracy", "PASS"))

    # --------------------------------------------------------------------------
    # Test 22: Receipt preview endpoint
    # --------------------------------------------------------------------------
    print("\n[TEST 22] Receipt preview endpoint (/preview)...")
    r22 = client.get(f"/api/v1/bills/{b1['id']}/receipt/preview", headers=staff_auth)
    assert r22.status_code == status.HTTP_200_OK
    prev22 = r22.json()
    assert "receipt_data" in prev22
    assert "formatted_text" in prev22
    assert "html_preview" in prev22
    assert "@page" in prev22["html_preview"]
    assert "58mm" in prev22["html_preview"]
    print("         Confirmed: Preview returns structured data, formatted text, and 58mm HTML.")
    results.append(("22. Receipt preview endpoint", "PASS"))

    # --------------------------------------------------------------------------
    # Test 23: Receipt print audit logging (RECEIPT_PRINTED & RECEIPT_REPRINTED)
    # --------------------------------------------------------------------------
    print("\n[TEST 23] Receipt print audit logging...")
    # Initial print
    r23_print = client.post(
        f"/api/v1/bills/{b1['id']}/receipt/print-audit",
        json={"is_reprint": False},
        headers=staff_auth,
    )
    assert r23_print.status_code == status.HTTP_201_CREATED
    assert r23_print.json()["action"] == "RECEIPT_PRINTED"

    # Reprint
    r23_reprint = client.post(
        f"/api/v1/bills/{b1['id']}/receipt/print-audit",
        json={"is_reprint": True},
        headers=staff_auth,
    )
    assert r23_reprint.status_code == status.HTTP_201_CREATED
    assert r23_reprint.json()["action"] == "RECEIPT_REPRINTED"

    # Verify audit log in DB
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT action, entity_type FROM audit_logs WHERE entity_id = %s ORDER BY created_at DESC LIMIT 2;",
                (UUID(b1['id']),),
            )
            logs = cur.fetchall()
            assert len(logs) == 2
            assert logs[0][0] == "RECEIPT_REPRINTED"
            assert logs[1][0] == "RECEIPT_PRINTED"

    print("         Confirmed: Both RECEIPT_PRINTED and RECEIPT_REPRINTED logged to audit trail.")
    results.append(("23. Receipt print audit logging", "PASS"))

    # --------------------------------------------------------------------------
    # Test 24: Reprint indicator displayed on duplicate copy
    # --------------------------------------------------------------------------
    print("\n[TEST 24] Reprint indicator displayed on duplicate copy...")
    r24_normal = client.get(f"/api/v1/bills/{b1['id']}/receipt?is_reprint=false", headers=staff_auth)
    assert r24_normal.status_code == status.HTTP_200_OK
    assert "*** DUPLICATE / REPRINT ***" not in r24_normal.json()["raw_text"]

    r24_reprint = client.get(f"/api/v1/bills/{b1['id']}/receipt?is_reprint=true", headers=staff_auth)
    assert r24_reprint.status_code == status.HTTP_200_OK
    assert r24_reprint.json()["is_reprint"] is True
    assert "*** DUPLICATE / REPRINT ***" in r24_reprint.json()["raw_text"]
    print("         Confirmed: *** DUPLICATE / REPRINT *** watermark printed only on reprint copies.")
    results.append(("24. Reprint indicator displayed on duplicate copy", "PASS"))

    # --------------------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("VIYON PHASE 4.4 RECEIPT GENERATION & PRINTING TEST RESULTS SUMMARY")
    print("=" * 80)
    for name, status_res in results:
        print(f"  {name:<65} [{status_res}]")
    print("=" * 80)
    print(f"ALL {len(results)} OF {len(results)} TESTS PASSED PERFECTLY WITH 100% ACCURACY!")
    print("=" * 80)


if __name__ == "__main__":
    run_phase4_4_receipt_tests()
