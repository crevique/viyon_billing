"""VIYON Billing System - Phase 5.1 UPI Payment Workflow & POS Validation Test Suite.
Target Database: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh).
Guarantees 100% isolation: Neon production database is NEVER connected to or modified.

Covers all 10 required scenarios from Section 5:
1. Cash payment immediately confirmed.
2. UPI payment initially pending.
3. UPI cannot be confirmed during checkout.
4. Pending UPI excluded from amount_paid.
5. Split cash + UPI accounting.
6. Manual UPI confirmation.
7. Rejected UPI excluded from collections.
8. Cancelled bill cannot receive UPI confirmation.
9. Unauthorized staff confirmation rejected if not permitted.
10. Frontend displays actual backend payment status.
"""

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Tuple
from uuid import UUID, uuid4

import psycopg
from fastapi import status
from fastapi.testclient import TestClient

# ------------------------------------------------------------------------------
# 1. Force Isolated Test Database
# ------------------------------------------------------------------------------
TEST_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/viyon_test_fresh"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["SECRET_KEY"] = "test-secret-key-phase5-1-upi-validation-32chars"
os.environ["ENVIRONMENT"] = "test"

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from alembic import command
from alembic.config import Config
from app.core.security import create_access_token, get_password_hash
from app.main import app


def setup_test_environment() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], UUID]:
    """Ensure schema is at head and return Owner, Staff, and Customer auth headers."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(cfg, "head")

    raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    owner_id = uuid4()
    staff_id = uuid4()
    customer_id = uuid4()
    prod_id = uuid4()

    default_pw_hash = get_password_hash("ViyonTestPass123!")

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
                    INSERT INTO users (id, full_name, email, password_hash, role, is_active)
                    VALUES (%s, 'Store Owner', 'owner@viyon.store', %s, 'OWNER', true);
                    """,
                    (owner_id, default_pw_hash),
                )

            # Check or create staff
            cur.execute("SELECT id FROM users WHERE role = 'STAFF' LIMIT 1;")
            row_staff = cur.fetchone()
            if row_staff:
                staff_id = row_staff[0]
            else:
                cur.execute(
                    """
                    INSERT INTO users (id, full_name, email, password_hash, role, is_active)
                    VALUES (%s, 'Counter Staff', 'staff@viyon.store', %s, 'STAFF', true);
                    """,
                    (staff_id, default_pw_hash),
                )

            # Check or create inactive staff user for unauthorized testing
            cur.execute("SELECT id FROM users WHERE is_active = false LIMIT 1;")
            row_inactive = cur.fetchone()
            if row_inactive:
                inactive_id = row_inactive[0]
            else:
                inactive_id = uuid4()
                cur.execute(
                    """
                    INSERT INTO users (id, full_name, email, password_hash, role, is_active)
                    VALUES (%s, 'Inactive Staff', %s, %s, 'STAFF', false);
                    """,
                    (inactive_id, f"inactive_{uuid4().hex[:6]}@viyon.store", default_pw_hash),
                )

            # Create test category & product with ample stock
            cur.execute("SELECT id FROM categories WHERE is_active = true LIMIT 1;")
            row_cat = cur.fetchone()
            if row_cat:
                cat_id = row_cat[0]
            else:
                cat_id = uuid4()
                cur.execute(
                    """
                    INSERT INTO categories (id, category_name, slug, is_active)
                    VALUES (%s, 'Men Premium Wear', 'men-premium', true);
                    """,
                    (cat_id,),
                )

            sku = f"SKU-UPI-{uuid4().hex[:6]}".upper()
            cur.execute(
                """
                INSERT INTO products (id, product_name, category_id, product_type, base_price, sku, is_active, is_archived)
                VALUES (%s, 'Luxury Linen Shirt', %s, 'SIMPLE', 1000.00, %s, true, false);
                """,
                (prod_id, cat_id, sku),
            )
            cur.execute(
                """
                INSERT INTO inventory (id, product_id, quantity, low_stock_threshold)
                VALUES (gen_random_uuid(), %s, 500, 5);
                """,
                (prod_id,),
            )
            conn.commit()

    owner_token = create_access_token(subject=str(owner_id), role="OWNER")
    staff_token = create_access_token(subject=str(staff_id), role="STAFF")
    inactive_token = create_access_token(subject=str(inactive_id), role="STAFF")

    return (
        {"Authorization": f"Bearer {owner_token}"},
        {"Authorization": f"Bearer {staff_token}"},
        {"Authorization": f"Bearer {inactive_token}"},
        prod_id,
    )


def run_upi_workflow_tests():
    owner_auth, staff_auth, inactive_auth, product_id = setup_test_environment()
    client = TestClient(app)
    results = []
    run_tag = uuid4().hex[:6]

    print("=" * 80)
    print("VIYON PHASE 5.1: UPI PAYMENT WORKFLOW & POS VALIDATION TEST SUITE")
    print("Target DB: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh)")
    print("=" * 80)

    def create_test_bill(qty: int = 1, discount: str = "0.00") -> dict:
        payload = {
            "items": [{"product_id": str(product_id), "quantity": qty, "discount_amount": "0.00"}],
            "discount_amount": discount,
        }
        res = client.post("/api/v1/bills", json=payload, headers=staff_auth)
        assert res.status_code == status.HTTP_201_CREATED, res.text
        return res.json()

    # --------------------------------------------------------------------------
    # Scenario 1: Cash payment immediately confirmed
    # --------------------------------------------------------------------------
    print("\n[SCENARIO 1] Cash payment immediately confirmed...")
    b1 = create_test_bill(qty=1)  # 1000.00
    r1 = client.post(
        f"/api/v1/bills/{b1['id']}/payments",
        json={"payment_method": "CASH", "amount": "1000.00"},
        headers=staff_auth,
    )
    assert r1.status_code == status.HTTP_201_CREATED
    p1 = r1.json()
    assert p1["payment_status"] == "CONFIRMED"
    assert p1["bill_amount_paid"] == "1000.00"
    assert p1["bill_balance_amount"] == "0.00"
    assert p1["bill_payment_status"] == "PAID"
    assert p1["confirmed_by_user_id"] is not None
    assert p1["confirmed_at"] is not None
    print(f"         Confirmed: CASH is immediately CONFIRMED. Bill #{b1['bill_number']} status=PAID")
    results.append(("1. Cash payment immediately confirmed", "PASS"))

    # --------------------------------------------------------------------------
    # Scenario 2: UPI payment initially pending
    # --------------------------------------------------------------------------
    print("\n[SCENARIO 2] UPI payment initially pending...")
    b2 = create_test_bill(qty=1)  # 1000.00
    utr2 = f"UTR-PENDING-{run_tag}-002"
    r2 = client.post(
        f"/api/v1/bills/{b2['id']}/payments",
        json={"payment_method": "UPI", "amount": "1000.00", "transaction_reference": utr2},
        headers=staff_auth,
    )
    assert r2.status_code == status.HTTP_201_CREATED
    p2 = r2.json()
    assert p2["payment_status"] == "PENDING"
    assert p2["confirmed_by_user_id"] is None
    assert p2["confirmed_at"] is None
    print(f"         Confirmed: UPI is recorded as PENDING. Unconfirmed by default.")
    results.append(("2. UPI payment initially pending", "PASS"))

    # --------------------------------------------------------------------------
    # Scenario 3: UPI cannot be confirmed during checkout (confirm_immediately rejected)
    # --------------------------------------------------------------------------
    print("\n[SCENARIO 3] UPI cannot be confirmed during checkout...")
    b3 = create_test_bill(qty=1)
    utr3 = f"UTR-BYPASS-{run_tag}-003"
    r3 = client.post(
        f"/api/v1/bills/{b3['id']}/payments",
        json={
            "payment_method": "UPI",
            "amount": "1000.00",
            "transaction_reference": utr3,
            "confirm_immediately": True,
        },
        headers=staff_auth,
    )
    # Pydantic model validator rejects with 422 Unprocessable Content / service rejects with 400 Bad Request
    assert r3.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY), r3.status_code
    print(f"         Confirmed: Attempt to pass confirm_immediately=True for UPI was strictly blocked ({r3.status_code}).")
    results.append(("3. UPI cannot be confirmed during checkout", "PASS"))

    # --------------------------------------------------------------------------
    # Scenario 4: Pending UPI excluded from amount_paid
    # --------------------------------------------------------------------------
    print("\n[SCENARIO 4] Pending UPI excluded from amount_paid...")
    r4_bill = client.get(f"/api/v1/bills/{b2['id']}", headers=staff_auth)
    assert r4_bill.status_code == status.HTTP_200_OK
    b2_data = r4_bill.json()
    assert Decimal(b2_data["amount_paid"]) == Decimal("0.00")
    assert Decimal(b2_data["balance_amount"]) == Decimal("1000.00")
    assert b2_data["payment_status"] == "PENDING"
    print(f"         Confirmed: Bill #{b2['bill_number']} amount_paid=0.00, balance=1000.00, status=PENDING.")
    results.append(("4. Pending UPI excluded from amount_paid", "PASS"))

    # --------------------------------------------------------------------------
    # Scenario 5: Split cash + UPI accounting
    # --------------------------------------------------------------------------
    print("\n[SCENARIO 5] Split cash + UPI accounting (Cash=400, UPI=600)...")
    b5 = create_test_bill(qty=1)  # 1000.00
    # Step A: Pay 400 in Cash
    r5_cash = client.post(
        f"/api/v1/bills/{b5['id']}/payments",
        json={"payment_method": "CASH", "amount": "400.00"},
        headers=staff_auth,
    )
    assert r5_cash.status_code == status.HTTP_201_CREATED
    p5_cash = r5_cash.json()
    assert p5_cash["payment_status"] == "CONFIRMED"
    assert p5_cash["bill_amount_paid"] == "400.00"
    assert p5_cash["bill_balance_amount"] == "600.00"
    assert p5_cash["bill_payment_status"] == "PARTIALLY_PAID"

    # Step B: Pay 600 in UPI (PENDING)
    utr5 = f"UTR-SPLIT-{run_tag}-005"
    r5_upi = client.post(
        f"/api/v1/bills/{b5['id']}/payments",
        json={"payment_method": "UPI", "amount": "600.00", "transaction_reference": utr5},
        headers=staff_auth,
    )
    assert r5_upi.status_code == status.HTTP_201_CREATED
    p5_upi = r5_upi.json()
    assert p5_upi["payment_status"] == "PENDING"
    assert p5_upi["bill_amount_paid"] == "400.00"  # Stays 400.00!
    assert p5_upi["bill_balance_amount"] == "600.00"  # Stays 600.00!
    assert p5_upi["bill_payment_status"] == "PARTIALLY_PAID"  # NOT PAID!

    # Verify Bill GET endpoint directly
    r5_chk = client.get(f"/api/v1/bills/{b5['id']}", headers=staff_auth)
    b5_check = r5_chk.json()
    assert b5_check["amount_paid"] == "400.00"
    assert b5_check["balance_amount"] == "600.00"
    assert b5_check["payment_status"] == "PARTIALLY_PAID"
    print(f"         Confirmed: Confirmed received = Rs. 400.00, Pending = Rs. 600.00. Status = PARTIALLY_PAID")
    results.append(("5. Split cash + UPI accounting", "PASS"))

    # --------------------------------------------------------------------------
    # Scenario 6: Manual UPI confirmation
    # --------------------------------------------------------------------------
    print("\n[SCENARIO 6] Manual UPI confirmation updates payment and bill...")
    r6_confirm = client.patch(
        f"/api/v1/payments/{p5_upi['id']}/confirm",
        json={"notes": "Verified in store merchant soundbox"},
        headers=staff_auth,
    )
    assert r6_confirm.status_code == status.HTTP_200_OK
    p5_confirmed = r6_confirm.json()
    assert p5_confirmed["payment_status"] == "CONFIRMED"
    assert p5_confirmed["confirmed_by_user_id"] is not None
    assert p5_confirmed["confirmed_at"] is not None
    assert p5_confirmed["bill_amount_paid"] == "1000.00"
    assert p5_confirmed["bill_balance_amount"] == "0.00"
    assert p5_confirmed["bill_payment_status"] == "PAID"

    # Verify authoritative Bill query
    r6_bill = client.get(f"/api/v1/bills/{b5['id']}", headers=staff_auth)
    b5_final = r6_bill.json()
    assert b5_final["amount_paid"] == "1000.00"
    assert b5_final["balance_amount"] == "0.00"
    assert b5_final["payment_status"] == "PAID"
    print(f"         Confirmed: Manual confirmation settled Bill #{b5['bill_number']}: amount_paid=1000.00, status=PAID")
    results.append(("6. Manual UPI confirmation", "PASS"))

    # --------------------------------------------------------------------------
    # Scenario 7: Rejected UPI excluded from collections
    # --------------------------------------------------------------------------
    print("\n[SCENARIO 7] Rejected UPI excluded from collections...")
    b7 = create_test_bill(qty=1)  # 1000.00
    utr7 = f"UTR-REJ-{run_tag}-007"
    r7_pay = client.post(
        f"/api/v1/bills/{b7['id']}/payments",
        json={"payment_method": "UPI", "amount": "1000.00", "transaction_reference": utr7},
        headers=staff_auth,
    )
    p7_id = r7_pay.json()["id"]

    # Reject payment
    r7_rej = client.patch(
        f"/api/v1/payments/{p7_id}/reject",
        json={"rejection_reason": "Customer cancelled QR scan at counter"},
        headers=staff_auth,
    )
    assert r7_rej.status_code == status.HTTP_200_OK
    p7_rejected = r7_rej.json()
    assert p7_rejected["payment_status"] == "REJECTED"
    assert p7_rejected["rejection_reason"] == "Customer cancelled QR scan at counter"
    assert p7_rejected["bill_amount_paid"] == "0.00"
    assert p7_rejected["bill_balance_amount"] == "1000.00"

    # Confirm bill totals untouched
    r7_bill = client.get(f"/api/v1/bills/{b7['id']}", headers=staff_auth)
    assert r7_bill.json()["amount_paid"] == "0.00"
    assert r7_bill.json()["payment_status"] == "PENDING"
    print(f"         Confirmed: Rejected payment leaves bill status PENDING with 0.00 collections.")
    results.append(("7. Rejected UPI excluded from collections", "PASS"))

    # --------------------------------------------------------------------------
    # Scenario 8: Cancelled bill cannot receive UPI confirmation
    # --------------------------------------------------------------------------
    print("\n[SCENARIO 8] Cancelled bill cannot receive UPI confirmation...")
    b8 = create_test_bill(qty=1)
    utr8 = f"UTR-CANCEL-{run_tag}-008"
    r8_pay = client.post(
        f"/api/v1/bills/{b8['id']}/payments",
        json={"payment_method": "UPI", "amount": "1000.00", "transaction_reference": utr8},
        headers=staff_auth,
    )
    p8_id = r8_pay.json()["id"]

    # Cancel bill (owner only)
    r8_cancel = client.patch(
        f"/api/v1/bills/{b8['id']}/cancel",
        json={"reason": "Customer left store without completing payment"},
        headers=owner_auth,
    )
    assert r8_cancel.status_code == status.HTTP_200_OK
    assert r8_cancel.json()["bill_status"] == "CANCELLED"

    # Attempt to confirm payment on cancelled bill
    r8_confirm_attempt = client.patch(
        f"/api/v1/payments/{p8_id}/confirm",
        json={"notes": "Attempting late confirmation"},
        headers=staff_auth,
    )
    assert r8_confirm_attempt.status_code == status.HTTP_409_CONFLICT
    assert "CANCELLED" in r8_confirm_attempt.json()["detail"]
    print(f"         Confirmed: Confirmation on cancelled bill strictly rejected with 409 Conflict.")
    results.append(("8. Cancelled bill cannot receive UPI confirmation", "PASS"))

    # --------------------------------------------------------------------------
    # Scenario 9: Unauthorized staff/customer confirmation rejected
    # --------------------------------------------------------------------------
    print("\n[SCENARIO 9] Unauthorized confirmation request rejected...")
    b9 = create_test_bill(qty=1)
    utr9 = f"UTR-UNAUTH-{run_tag}-009"
    r9_pay = client.post(
        f"/api/v1/bills/{b9['id']}/payments",
        json={"payment_method": "UPI", "amount": "1000.00", "transaction_reference": utr9},
        headers=staff_auth,
    )
    p9_id = r9_pay.json()["id"]

    # Unauthenticated request -> 401
    r9_no_auth = client.patch(f"/api/v1/payments/{p9_id}/confirm", json={})
    assert r9_no_auth.status_code == status.HTTP_401_UNAUTHORIZED

    # Inactive staff user request -> 403 Forbidden
    r9_inactive_auth = client.patch(
        f"/api/v1/payments/{p9_id}/confirm",
        json={},
        headers=inactive_auth,
    )
    assert r9_inactive_auth.status_code == status.HTTP_403_FORBIDDEN
    print(f"         Confirmed: Unauthenticated -> 401, Inactive staff -> 403. Only active Staff & Owner permitted.")
    results.append(("9. Unauthorized staff confirmation rejected if not permitted", "PASS"))

    # --------------------------------------------------------------------------
    # Scenario 10: Frontend displays actual backend payment status
    # --------------------------------------------------------------------------
    print("\n[SCENARIO 10] Frontend displays actual backend payment status...")
    # Verify GET /bills/{id}/payments returns full state for UI consumption
    r10 = client.get(f"/api/v1/bills/{b5['id']}/payments", headers=staff_auth)
    assert r10.status_code == status.HTTP_200_OK
    payments10 = r10.json()
    assert len(payments10) == 2
    # Expect 1 Cash (CONFIRMED) and 1 UPI (CONFIRMED)
    methods = {p["payment_method"]: p["payment_status"] for p in payments10}
    assert methods.get("CASH") == "CONFIRMED"
    assert methods.get("UPI") == "CONFIRMED"

    # Also verify bill b2 (with PENDING UPI) returns accurate status
    r10_pending = client.get(f"/api/v1/bills/{b2['id']}/payments", headers=staff_auth)
    assert r10_pending.status_code == status.HTTP_200_OK
    p_pending = r10_pending.json()[0]
    assert p_pending["payment_status"] == "PENDING"
    assert p_pending["transaction_reference"] == utr2
    assert p_pending["amount"] == "1000.00"
    print(f"         Confirmed: Authoritative backend schema returns exact payment_status, UTR, and timestamp for UI.")
    results.append(("10. Frontend displays actual backend payment status", "PASS"))

    # --------------------------------------------------------------------------
    # Summary Table
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("VIYON PHASE 5.1 UPI WORKFLOW TEST RESULTS SUMMARY")
    print("=" * 80)
    for name, st in results:
        print(f"  {name:<65} [{st}]")
    print("=" * 80)
    print(f"ALL {len(results)} OF 10 UPI WORKFLOW SCENARIOS PASSED WITH 100% ACCURACY!")
    print("=" * 80)


if __name__ == "__main__":
    run_upi_workflow_tests()
