"""VIYON Billing System - Phase 4.2 Automated Test Suite
Testing Payment Management, Cash Recording, UPI Verification, Split Payments & Concurrency.
Target Database: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh).
"""

import os
import sys
import threading
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
TEST_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/viyon_test_fresh"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["SECRET_KEY"] = "test-secret-key-phase4-2-secure-random-at-least-32-chars"
os.environ["ENVIRONMENT"] = "test"

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from alembic import command
from alembic.config import Config
from app.core.security import create_access_token, get_password_hash
from app.main import app


def setup_test_data() -> Tuple[Dict[str, str], Dict[str, str], UUID, UUID]:
    """Ensure database is migrated to head and seeded with test users and baseline store settings."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(cfg, "head")

    raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    owner_id = uuid4()
    staff_id = uuid4()
    cat_id = uuid4()
    prod_id = uuid4()

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            # Check or create store owner
            cur.execute("SELECT id FROM users WHERE role = 'OWNER' LIMIT 1;")
            row_owner = cur.fetchone()
            if row_owner:
                owner_id = row_owner[0]
            else:
                pw_hash = get_password_hash("OwnerSecurePass123!")
                cur.execute(
                    """
                    INSERT INTO users (id, full_name, email, password_hash, role, is_active)
                    VALUES (%s, 'Store Owner', 'owner@viyon.store', %s, 'OWNER', true);
                    """,
                    (owner_id, pw_hash),
                )

            # Check or create staff
            cur.execute("SELECT id FROM users WHERE role = 'STAFF' LIMIT 1;")
            row_staff = cur.fetchone()
            if row_staff:
                staff_id = row_staff[0]
            else:
                pw_hash = get_password_hash("StaffPass123!")
                cur.execute(
                    """
                    INSERT INTO users (id, full_name, email, password_hash, role, is_active)
                    VALUES (%s, 'Counter Staff', 'staff@viyon.store', %s, 'STAFF', true);
                    """,
                    (staff_id, pw_hash),
                )

            # Ensure store settings exist
            cur.execute("SELECT id FROM store_settings WHERE is_active_config = true LIMIT 1;")
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO store_settings (id, store_name, tagline, address, phone, currency_code, tax_enabled, default_tax_rate, receipt_width_mm, is_active_config)
                    VALUES (gen_random_uuid(), 'VIYON', 'MENS WEAR', 'Sathyamangalam', '082702 42681', 'INR', false, 0.00, 58, true);
                    """
                )

            # Ensure a product with stock exists for checkout
            cur.execute("SELECT id FROM categories LIMIT 1;")
            r_cat = cur.fetchone()
            if r_cat:
                cat_id = r_cat[0]
            else:
                cur.execute(
                    "INSERT INTO categories (id, name, is_active) VALUES (%s, 'Shirts', true);",
                    (cat_id,),
                )

            cur.execute("SELECT id FROM products WHERE product_type = 'SIMPLE' AND is_active = true LIMIT 1;")
            r_prod = cur.fetchone()
            if r_prod:
                prod_id = r_prod[0]
            else:
                cur.execute(
                    """
                    INSERT INTO products (id, category_id, product_name, product_type, base_price, sku, is_active, is_archived)
                    VALUES (%s, %s, 'Payment Test Shirt', 'SIMPLE', 1000.00, 'PAY-SHIRT-01', true, false);
                    """,
                    (prod_id, cat_id),
                )
                cur.execute(
                    """
                    INSERT INTO inventory (id, product_id, variant_id, quantity, low_stock_threshold)
                    VALUES (gen_random_uuid(), %s, NULL, 500, 10);
                    """,
                    (prod_id,),
                )

        conn.commit()

    owner_token = create_access_token(subject=str(owner_id), role="OWNER")
    staff_token = create_access_token(subject=str(staff_id), role="STAFF")

    owner_auth = {"Authorization": f"Bearer {owner_token}"}
    staff_auth = {"Authorization": f"Bearer {staff_token}"}

    return owner_auth, staff_auth, owner_id, staff_id


def run_phase4_2_payment_tests():
    client = TestClient(app)
    owner_auth, staff_auth, owner_id, staff_id = setup_test_data()
    run_tag = uuid4().hex[:6]

    print("=" * 80)
    print("VIYON PHASE 4.2: PAYMENT MANAGEMENT & SPLIT PAYMENTS TEST SUITE")
    print(f"Target DB: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh)")
    print("=" * 80)

    results: List[Tuple[str, str]] = []

    # Helper function to create a test bill of a specific total
    def create_test_bill(qty: int = 2) -> Dict:
        """Create a fresh bill for payment testing."""
        # Find available product
        raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(raw_pg_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, base_price FROM products WHERE product_type = 'SIMPLE' AND is_active = true LIMIT 1;"
                )
                row = cur.fetchone()
                assert row is not None
                p_id, price = row[0], row[1]
                # Ensure plenty of stock
                cur.execute(
                    "UPDATE inventory SET quantity = 1000 WHERE product_id = %s AND variant_id IS NULL;",
                    (p_id,),
                )
            conn.commit()

        resp = client.post(
            "/api/v1/bills",
            json={"items": [{"product_id": str(p_id), "quantity": qty}]},
            headers=staff_auth,
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.text
        return resp.json()

    # --------------------------------------------------------------------------
    # Test 1: Successful CASH payment
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Successful cash payment...")
    b1 = create_test_bill(qty=2)  # Total 2000.00
    bill1_id = b1["id"]
    r1 = client.post(
        f"/api/v1/bills/{bill1_id}/payments",
        json={
            "payment_method": "CASH",
            "amount": "2000.00",
            "notes": "Exact cash received at counter",
        },
        headers=staff_auth,
    )
    assert r1.status_code == status.HTTP_201_CREATED, r1.text
    p1 = r1.json()
    assert p1["payment_status"] == "CONFIRMED"
    assert p1["payment_method"] == "CASH"
    assert p1["amount"] == "2000.00"
    assert p1["bill_amount_paid"] == "2000.00"
    assert p1["bill_balance_amount"] == "0.00"
    assert p1["bill_payment_status"] == "PAID"
    assert p1["confirmed_by_user_id"] == str(staff_id)
    print(f"         Cash payment recorded: ID={p1['id']} Status={p1['payment_status']} BillStatus={p1['bill_payment_status']}")
    results.append(("1. Successful cash payment", "PASS"))

    # --------------------------------------------------------------------------
    # Test 2: Successful UPI payment after manual confirmation
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Successful UPI payment after manual confirmation...")
    b2 = create_test_bill(qty=2)  # Total 2000.00
    bill2_id = b2["id"]
    r2_create = client.post(
        f"/api/v1/bills/{bill2_id}/payments",
        json={
            "payment_method": "UPI",
            "amount": "2000.00",
            "transaction_reference": f"UPI-TEST-{run_tag}-002",
            "notes": "Awaiting customer screenshot verification",
        },
        headers=staff_auth,
    )
    assert r2_create.status_code == status.HTTP_201_CREATED, r2_create.text
    p2_created = r2_create.json()
    assert p2_created["payment_status"] == "PENDING"
    assert p2_created["confirmed_by_user_id"] is None
    payment2_id = p2_created["id"]

    # Confirm it
    r2_confirm = client.patch(
        f"/api/v1/payments/{payment2_id}/confirm",
        json={"notes": "Checked store soundbox/notification"},
        headers=staff_auth,
    )
    assert r2_confirm.status_code == status.HTTP_200_OK, r2_confirm.text
    p2_conf = r2_confirm.json()
    assert p2_conf["payment_status"] == "CONFIRMED"
    assert p2_conf["confirmed_by_user_id"] == str(staff_id)
    assert p2_conf["bill_amount_paid"] == "2000.00"
    assert p2_conf["bill_balance_amount"] == "0.00"
    assert p2_conf["bill_payment_status"] == "PAID"
    print(f"         UPI payment confirmed: ID={payment2_id} BillStatus={p2_conf['bill_payment_status']}")
    results.append(("2. Successful UPI payment after manual confirmation", "PASS"))

    # --------------------------------------------------------------------------
    # Test 3: Pending UPI payment does not update amount_paid
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Pending UPI payment does not update amount_paid...")
    b3 = create_test_bill(qty=3)  # Total 3000.00
    bill3_id = b3["id"]
    r3 = client.post(
        f"/api/v1/bills/{bill3_id}/payments",
        json={
            "payment_method": "UPI",
            "amount": "1500.00",
            "transaction_reference": f"UPI-PENDING-{run_tag}-003",
        },
        headers=staff_auth,
    )
    assert r3.status_code == status.HTTP_201_CREATED, r3.text
    # Verify the bill itself still has 0 amount paid
    r3_bill = client.get(f"/api/v1/bills/{bill3_id}", headers=staff_auth)
    assert r3_bill.status_code == status.HTTP_200_OK
    b3_fetched = r3_bill.json()
    assert b3_fetched["amount_paid"] == "0.00"
    assert b3_fetched["balance_amount"] == "3000.00"
    assert b3_fetched["payment_status"] == "PENDING"
    print(f"         Confirmed: Pending payment left amount_paid=0.00, balance={b3_fetched['balance_amount']}")
    results.append(("3. Pending UPI payment does not update amount_paid", "PASS"))

    # --------------------------------------------------------------------------
    # Test 4: Successful split payment (CASH + confirmed UPI)
    # --------------------------------------------------------------------------
    print("\n[TEST 4] Successful split payment (CASH + UPI)...")
    b4 = create_test_bill(qty=3)  # Total 3000.00
    bill4_id = b4["id"]

    # 1. Pay 1000 in Cash
    r4_cash = client.post(
        f"/api/v1/bills/{bill4_id}/payments",
        json={"payment_method": "CASH", "amount": "1000.00"},
        headers=staff_auth,
    )
    assert r4_cash.status_code == status.HTTP_201_CREATED
    assert r4_cash.json()["bill_amount_paid"] == "1000.00"
    assert r4_cash.json()["bill_balance_amount"] == "2000.00"
    assert r4_cash.json()["bill_payment_status"] == "PARTIALLY_PAID"

    # 2. Pay remaining 2000 via UPI (always recorded as PENDING initially)
    r4_upi = client.post(
        f"/api/v1/bills/{bill4_id}/payments",
        json={
            "payment_method": "UPI",
            "amount": "2000.00",
            "transaction_reference": f"UPI-SPLIT-{run_tag}-004",
        },
        headers=staff_auth,
    )
    assert r4_upi.status_code == status.HTTP_201_CREATED
    p4_upi = r4_upi.json()
    assert p4_upi["payment_status"] == "PENDING"
    assert p4_upi["bill_amount_paid"] == "1000.00"
    assert p4_upi["bill_balance_amount"] == "2000.00"
    assert p4_upi["bill_payment_status"] == "PARTIALLY_PAID"

    # 3. Staff manually confirms UPI receipt via authorized endpoint
    r4_confirm = client.patch(
        f"/api/v1/payments/{p4_upi['id']}/confirm",
        json={"notes": "Store soundbox confirmed"},
        headers=staff_auth,
    )
    assert r4_confirm.status_code == status.HTTP_200_OK
    p4_confirmed = r4_confirm.json()
    assert p4_confirmed["payment_status"] == "CONFIRMED"
    assert p4_confirmed["bill_amount_paid"] == "3000.00"
    assert p4_confirmed["bill_balance_amount"] == "0.00"
    assert p4_confirmed["bill_payment_status"] == "PAID"
    print(f"         Split payment complete: Rs. 1000 CASH + Rs. 2000 UPI (confirmed) -> PAID")
    results.append(("4. Successful split payment", "PASS"))

    # --------------------------------------------------------------------------
    # Test 5: Partial payment updates outstanding balance
    # --------------------------------------------------------------------------
    print("\n[TEST 5] Partial payment updates outstanding balance...")
    b5 = create_test_bill(qty=2)  # Total 2000.00
    bill5_id = b5["id"]
    r5 = client.post(
        f"/api/v1/bills/{bill5_id}/payments",
        json={"payment_method": "CASH", "amount": "750.00"},
        headers=staff_auth,
    )
    assert r5.status_code == status.HTTP_201_CREATED
    p5 = r5.json()
    assert p5["bill_amount_paid"] == "750.00"
    assert p5["bill_balance_amount"] == "1250.00"
    assert p5["bill_payment_status"] == "PARTIALLY_PAID"
    print(f"         Partial payment verified: Balance updated to Rs. 1250.00 (PARTIALLY_PAID)")
    results.append(("5. Partial payment updates outstanding balance", "PASS"))

    # --------------------------------------------------------------------------
    # Test 6: Full payment changes status to PAID
    # --------------------------------------------------------------------------
    print("\n[TEST 6] Full payment changes status to PAID...")
    r6_pay2 = client.post(
        f"/api/v1/bills/{bill5_id}/payments",
        json={"payment_method": "CASH", "amount": "1250.00"},
        headers=staff_auth,
    )
    assert r6_pay2.status_code == status.HTTP_201_CREATED
    assert r6_pay2.json()["bill_balance_amount"] == "0.00"
    assert r6_pay2.json()["bill_payment_status"] == "PAID"
    print(f"         Bill {bill5_id} successfully settled: status=PAID")
    results.append(("6. Full payment changes status to PAID", "PASS"))

    # --------------------------------------------------------------------------
    # Test 7: Multiple payments for one bill
    # --------------------------------------------------------------------------
    print("\n[TEST 7] Multiple payments for one bill (3 installments)...")
    b7 = create_test_bill(qty=3)  # Total 3000.00
    bill7_id = b7["id"]
    client.post(f"/api/v1/bills/{bill7_id}/payments", json={"payment_method": "CASH", "amount": "1000.00"}, headers=staff_auth)
    client.post(f"/api/v1/bills/{bill7_id}/payments", json={"payment_method": "CASH", "amount": "1000.00"}, headers=staff_auth)
    client.post(f"/api/v1/bills/{bill7_id}/payments", json={"payment_method": "CASH", "amount": "1000.00"}, headers=staff_auth)

    r7_list = client.get(f"/api/v1/bills/{bill7_id}/payments", headers=staff_auth)
    assert r7_list.status_code == status.HTTP_200_OK
    payments7 = r7_list.json()
    assert len(payments7) == 3
    assert all(p["payment_status"] == "CONFIRMED" for p in payments7)
    print(f"         Verified 3 sequential payments recorded on Bill {bill7_id}")
    results.append(("7. Multiple payments for one bill", "PASS"))

    # --------------------------------------------------------------------------
    # Test 8: Zero payment rejected
    # --------------------------------------------------------------------------
    print("\n[TEST 8] Zero payment rejection (400/422)...")
    b8 = create_test_bill(qty=1)
    r8 = client.post(
        f"/api/v1/bills/{b8['id']}/payments",
        json={"payment_method": "CASH", "amount": "0.00"},
        headers=staff_auth,
    )
    assert r8.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)
    print("         Zero payment correctly rejected.")
    results.append(("8. Zero payment rejected", "PASS"))

    # --------------------------------------------------------------------------
    # Test 9: Negative payment rejected
    # --------------------------------------------------------------------------
    print("\n[TEST 9] Negative payment rejection (400/422)...")
    r9 = client.post(
        f"/api/v1/bills/{b8['id']}/payments",
        json={"payment_method": "CASH", "amount": "-500.00"},
        headers=staff_auth,
    )
    assert r9.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)
    print("         Negative payment correctly rejected.")
    results.append(("9. Negative payment rejected", "PASS"))

    # --------------------------------------------------------------------------
    # Test 10: Payment exceeding balance rejected (409)
    # --------------------------------------------------------------------------
    print("\n[TEST 10] Payment exceeding balance rejection (409)...")
    # b8 total is 1000.00. Attempt to pay 1000.01
    r10 = client.post(
        f"/api/v1/bills/{b8['id']}/payments",
        json={"payment_method": "CASH", "amount": "1000.01"},
        headers=staff_auth,
    )
    assert r10.status_code == status.HTTP_409_CONFLICT
    assert "exceeds outstanding bill balance" in r10.json()["detail"]
    print(f"         Overpayment blocked: {r10.json()['detail']}")
    results.append(("10. Payment exceeding balance rejected", "PASS"))

    # --------------------------------------------------------------------------
    # Test 11: Duplicate UPI confirmation rejected (409)
    # --------------------------------------------------------------------------
    print("\n[TEST 11] Duplicate UPI confirmation rejection (409)...")
    # Re-confirming payment2 from Test 2 should fail with 409
    r11 = client.patch(
        f"/api/v1/payments/{payment2_id}/confirm",
        json={"notes": "Duplicate confirm attempt"},
        headers=staff_auth,
    )
    assert r11.status_code == status.HTTP_409_CONFLICT
    assert "already been confirmed" in r11.json()["detail"]
    print("         Duplicate confirmation blocked with 409 Conflict.")
    results.append(("11. Duplicate UPI confirmation rejected", "PASS"))

    # --------------------------------------------------------------------------
    # Test 12: Rejected UPI payment does not affect amount_paid
    # --------------------------------------------------------------------------
    print("\n[TEST 12] Rejected UPI payment does not affect amount_paid...")
    b12 = create_test_bill(qty=1)  # Total 1000.00
    r12_create = client.post(
        f"/api/v1/bills/{b12['id']}/payments",
        json={
            "payment_method": "UPI",
            "amount": "1000.00",
            "transaction_reference": f"UPI-REJECT-{run_tag}-012",
        },
        headers=staff_auth,
    )
    p12_id = r12_create.json()["id"]

    # Reject with mandatory reason
    r12_reject = client.patch(
        f"/api/v1/payments/{p12_id}/reject",
        json={"rejection_reason": "UTR did not match store bank records"},
        headers=staff_auth,
    )
    assert r12_reject.status_code == status.HTTP_200_OK
    assert r12_reject.json()["payment_status"] == "REJECTED"
    assert r12_reject.json()["rejection_reason"] == "UTR did not match store bank records"

    # Confirm bill still has 0 paid
    b12_check = client.get(f"/api/v1/bills/{b12['id']}", headers=staff_auth).json()
    assert b12_check["amount_paid"] == "0.00"
    assert b12_check["balance_amount"] == "1000.00"
    assert b12_check["payment_status"] == "PENDING"
    print("         Rejected payment leaves bill balance and status untouched.")
    results.append(("12. Rejected UPI payment does not affect amount_paid", "PASS"))

    # --------------------------------------------------------------------------
    # Test 13: Invalid bill rejected (404)
    # --------------------------------------------------------------------------
    print("\n[TEST 13] Invalid bill UUID rejection (404)...")
    fake_bid = uuid4()
    r13 = client.post(
        f"/api/v1/bills/{fake_bid}/payments",
        json={"payment_method": "CASH", "amount": "100.00"},
        headers=staff_auth,
    )
    assert r13.status_code == status.HTTP_404_NOT_FOUND
    print("         Payment on non-existent bill rejected with 404.")
    results.append(("13. Invalid bill rejected", "PASS"))

    # --------------------------------------------------------------------------
    # Test 14: Cancelled bill payment rejected (409)
    # --------------------------------------------------------------------------
    print("\n[TEST 14] Cancelled bill payment rejection (409)...")
    b14 = create_test_bill(qty=1)
    # Mark bill as CANCELLED directly in DB
    raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE bills
                SET bill_status = 'CANCELLED',
                    cancelled_at = now(),
                    cancelled_by_user_id = %s,
                    cancellation_reason = 'Test cancellation'
                WHERE id = %s;
                """,
                (owner_id, b14["id"]),
            )
        conn.commit()

    r14 = client.post(
        f"/api/v1/bills/{b14['id']}/payments",
        json={"payment_method": "CASH", "amount": "100.00"},
        headers=staff_auth,
    )
    assert r14.status_code == status.HTTP_409_CONFLICT
    assert "CANCELLED" in r14.json()["detail"]
    print("         Payment on cancelled bill rejected with 409.")
    results.append(("14. Cancelled bill payment rejected", "PASS"))

    # --------------------------------------------------------------------------
    # Test 15: Duplicate UTR validation (409)
    # --------------------------------------------------------------------------
    print("\n[TEST 15] Duplicate UTR validation (409)...")
    b15a = create_test_bill(qty=1)
    b15b = create_test_bill(qty=1)
    utr_unique = f"UPI-GLOBAL-UTR-{run_tag}-123456"

    # Register first with this UTR
    r15a = client.post(
        f"/api/v1/bills/{b15a['id']}/payments",
        json={"payment_method": "UPI", "amount": "500.00", "transaction_reference": utr_unique},
        headers=staff_auth,
    )
    assert r15a.status_code == status.HTTP_201_CREATED

    # Attempt to register second with the same UTR
    r15b = client.post(
        f"/api/v1/bills/{b15b['id']}/payments",
        json={"payment_method": "UPI", "amount": "500.00", "transaction_reference": utr_unique},
        headers=staff_auth,
    )
    assert r15b.status_code == status.HTTP_409_CONFLICT
    assert "already associated" in r15b.json()["detail"] or "duplicate" in r15b.json()["detail"].lower()
    print("         Duplicate non-empty UTR blocked with 409 Conflict.")
    results.append(("15. Duplicate UTR validation", "PASS"))

    # --------------------------------------------------------------------------
    # Test 16: Unauthenticated payment request rejected (401)
    # --------------------------------------------------------------------------
    print("\n[TEST 16] Unauthenticated payment rejection (401)...")
    r16 = client.post(
        f"/api/v1/bills/{b1['id']}/payments",
        json={"payment_method": "CASH", "amount": "100.00"},
    )
    assert r16.status_code == status.HTTP_401_UNAUTHORIZED
    print("         Unauthenticated request blocked with 401.")
    results.append(("16. Unauthenticated payment request rejected", "PASS"))

    # --------------------------------------------------------------------------
    # Test 17: Owner payment permissions
    # --------------------------------------------------------------------------
    print("\n[TEST 17] Owner payment permissions...")
    b17 = create_test_bill(qty=1)
    r17 = client.post(
        f"/api/v1/bills/{b17['id']}/payments",
        json={"payment_method": "CASH", "amount": "500.00"},
        headers=owner_auth,
    )
    assert r17.status_code == status.HTTP_201_CREATED
    assert r17.json()["confirmed_by_user_id"] == str(owner_id)
    print("         Owner authorized to record payments.")
    results.append(("17. Owner payment permissions", "PASS"))

    # --------------------------------------------------------------------------
    # Test 18: Staff payment permissions
    # --------------------------------------------------------------------------
    print("\n[TEST 18] Staff payment permissions...")
    r18 = client.post(
        f"/api/v1/bills/{b17['id']}/payments",
        json={"payment_method": "CASH", "amount": "500.00"},
        headers=staff_auth,
    )
    assert r18.status_code == status.HTTP_201_CREATED
    assert r18.json()["confirmed_by_user_id"] == str(staff_id)
    print("         Staff authorized to record payments.")
    results.append(("18. Staff payment permissions", "PASS"))

    # --------------------------------------------------------------------------
    # Test 19: Payment history retrieval
    # --------------------------------------------------------------------------
    print("\n[TEST 19] Payment history retrieval...")
    r19_single = client.get(f"/api/v1/payments/{p1['id']}", headers=staff_auth)
    assert r19_single.status_code == status.HTTP_200_OK
    assert r19_single.json()["id"] == p1["id"]

    r19_bill = client.get(f"/api/v1/bills/{bill1_id}/payments", headers=staff_auth)
    assert r19_bill.status_code == status.HTTP_200_OK
    assert len(r19_bill.json()) >= 1
    print("         Individual payment and bill payment history retrieved.")
    results.append(("19. Payment history retrieval", "PASS"))

    # --------------------------------------------------------------------------
    # Test 20: Payment listing filters and pagination
    # --------------------------------------------------------------------------
    print("\n[TEST 20] Payment listing filters and pagination...")
    r20_all = client.get("/api/v1/payments?limit=10&offset=0", headers=staff_auth)
    assert r20_all.status_code == status.HTTP_200_OK
    p_data = r20_all.json()
    assert "total" in p_data
    assert "items" in p_data
    assert len(p_data["items"]) <= 10

    # Filter by CASH
    r20_cash = client.get("/api/v1/payments?payment_method=CASH", headers=staff_auth)
    assert r20_cash.status_code == status.HTTP_200_OK
    assert all(item["payment_method"] == "CASH" for item in r20_cash.json()["items"])

    # Filter by CONFIRMED
    r20_conf = client.get("/api/v1/payments?payment_status=CONFIRMED", headers=staff_auth)
    assert r20_conf.status_code == status.HTTP_200_OK
    assert all(item["payment_status"] == "CONFIRMED" for item in r20_conf.json()["items"])
    print("         Payment filters (method, status, pagination) verified.")
    results.append(("20. Payment listing filters and pagination", "PASS"))

    # --------------------------------------------------------------------------
    # Test 21: Concurrent payments cannot cause overpayment
    # --------------------------------------------------------------------------
    print("\n[TEST 21] Concurrency test: Prevent overpayment race conditions...")
    # Create a bill with exactly 1000.00 balance
    b21 = create_test_bill(qty=1)  # Total 1000.00
    bill21_id = b21["id"]

    # 5 concurrent threads all try to pay the full 1000.00
    # Exactly ONE must succeed (201) and 4 must fail with 409 Overpayment!
    thread_results: List[int] = []
    barrier = threading.Barrier(5)

    def payment_worker():
        barrier.wait()
        res = client.post(
            f"/api/v1/bills/{bill21_id}/payments",
            json={"payment_method": "CASH", "amount": "1000.00"},
            headers=staff_auth,
        )
        thread_results.append(res.status_code)

    threads = [threading.Thread(target=payment_worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = thread_results.count(status.HTTP_201_CREATED)
    conflicts = thread_results.count(status.HTTP_409_CONFLICT)
    print(f"         5 Concurrent full payments: {successes} Succeeded, {conflicts} Rejected with 409")
    assert successes == 1
    assert conflicts == 4

    # Verify final bill balance is exactly 0.00 and amount_paid is 1000.00
    b21_final = client.get(f"/api/v1/bills/{bill21_id}", headers=staff_auth).json()
    assert b21_final["amount_paid"] == "1000.00"
    assert b21_final["balance_amount"] == "0.00"
    assert b21_final["payment_status"] == "PAID"
    print("         Confirmed: Zero overpayment under high concurrency!")
    results.append(("21. Concurrent payments cannot cause overpayment", "PASS"))

    # --------------------------------------------------------------------------
    # Test 22: Payment totals remain consistent after transaction rollback
    # --------------------------------------------------------------------------
    print("\n[TEST 22] Rollback consistency on failed payment...")
    b22 = create_test_bill(qty=1)  # Total 1000.00
    bill22_id = b22["id"]

    # Attempt payment exceeding balance
    client.post(
        f"/api/v1/bills/{bill22_id}/payments",
        json={"payment_method": "CASH", "amount": "5000.00"},
        headers=staff_auth,
    )

    # Verify bill is completely untouched
    b22_check = client.get(f"/api/v1/bills/{bill22_id}", headers=staff_auth).json()
    assert b22_check["amount_paid"] == "0.00"
    assert b22_check["balance_amount"] == "1000.00"
    assert b22_check["payment_status"] == "PENDING"

    # Verify 0 payments recorded
    p22_list = client.get(f"/api/v1/bills/{bill22_id}/payments", headers=staff_auth).json()
    assert len(p22_list) == 0
    print("         Atomic rollback verified: 0 orphan payment records, bill untouched.")
    results.append(("22. Payment totals remain consistent after transaction rollback", "PASS"))

    # --------------------------------------------------------------------------
    # Test 23: Confirmed payment cannot be silently deleted or modified
    # --------------------------------------------------------------------------
    print("\n[TEST 23] Confirmed payment immutability...")
    # Attempt to reject a confirmed payment
    r23 = client.patch(
        f"/api/v1/payments/{p1['id']}/reject",
        json={"rejection_reason": "Attempting to reverse confirmed cash"},
        headers=staff_auth,
    )
    assert r23.status_code == status.HTTP_409_CONFLICT
    assert "already CONFIRMED" in r23.json()["detail"] or "reversal" in r23.json()["detail"].lower()
    print("         Confirmed payments cannot be rejected or mutated.")
    results.append(("23. Confirmed payment cannot be silently deleted or modified", "PASS"))

    # --------------------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("VIYON PHASE 4.2 PAYMENT & SPLIT PAYMENTS TEST RESULTS SUMMARY")
    print("=" * 80)
    for name, res in results:
        print(f"  {name:<65} [{res}]")
    print("=" * 80)
    print(f"ALL {len(results)} OF {len(results)} TESTS PASSED PERFECTLY WITH 100% ACCURACY!")
    print("=" * 80)


if __name__ == "__main__":
    run_phase4_2_payment_tests()
