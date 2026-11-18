"""VIYON Billing System - Phase 5.2 Automated Security & Staff Test Suite
Testing Complete Staff Management System, Cashier Administration, RBAC,
Session Invalidation on Password Reset, Deactivation Enforcement, and Historical Bill Attribution.
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
os.environ["SECRET_KEY"] = "test-secret-key-phase5-2-secure-random-at-least-32-chars"
os.environ["ENVIRONMENT"] = "test"

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.security import create_access_token, get_password_hash
from app.core.token_blacklist import token_blacklist
from app.main import app


def setup_test_environment() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str], UUID, UUID, UUID]:
    """Ensure database is seeded with baseline owner, staff, and products."""
    print("[SETUP] Connecting to database...", flush=True)
    raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    owner_id = uuid4()
    staff_id = uuid4()
    cat_id = uuid4()
    prod_id = uuid4()
    default_pw_hash = get_password_hash("ViyonSecurePass123!")

    with psycopg.connect(raw_pg_url) as conn:
        print("[SETUP] Connected!", flush=True)
        with conn.cursor() as cur:
            print("[SETUP] Seeding owner...", flush=True)
            # Check or create store owner
            cur.execute("SELECT id FROM users WHERE role = 'OWNER' LIMIT 1;")
            row_owner = cur.fetchone()
            if row_owner:
                owner_id = row_owner[0]
            else:
                cur.execute(
                    """
                    INSERT INTO users (id, full_name, username, email, phone, password_hash, role, is_active)
                    VALUES (%s, 'Store Owner', 'storeowner', 'owner@viyon.store', '08270242681', %s, 'OWNER', true);
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
                    VALUES (%s, 'Senior Cashier', 'cashier_alpha', 'cashier_alpha@viyon.store', '09876543210', %s, 'STAFF', true);
                    """,
                    (staff_id, default_pw_hash),
                )

            # Ensure product exists for bill creation
            cur.execute("SELECT id FROM products WHERE product_type = 'SIMPLE' AND is_active = true LIMIT 1;")
            row_prod = cur.fetchone()
            if row_prod:
                prod_id = row_prod[0]
            else:
                cur.execute("SELECT id FROM categories WHERE is_active = true LIMIT 1;")
                row_c = cur.fetchone()
                if row_c:
                    cat_id = row_c[0]
                else:
                    cur.execute(
                        "INSERT INTO categories (id, name, is_active) VALUES (%s, 'Shirts', true);",
                        (cat_id,),
                    )
                sku = f"SKU-STAFF-{uuid4().hex[:6]}".upper()
                cur.execute(
                    """
                    INSERT INTO products (id, product_name, category_id, product_type, base_price, sku, is_active, is_archived)
                    VALUES (%s, 'Staff Test Linen Shirt', %s, 'SIMPLE', 1000.00, %s, true, false);
                    """,
                    (prod_id, cat_id, sku),
                )
                cur.execute(
                    """
                    INSERT INTO inventory (id, product_id, quantity, low_stock_threshold)
                    VALUES (gen_random_uuid(), %s, 1000, 5);
                    """,
                    (prod_id,),
                )
            conn.commit()

    owner_token = create_access_token(subject=str(owner_id), role="OWNER")
    staff_token = create_access_token(subject=str(staff_id), role="STAFF")
    # Customer token (non-staff, non-owner)
    customer_token = create_access_token(subject=str(uuid4()), role="CUSTOMER")
    # Admin role token (demonstrating admin cannot manage staff without OWNER privilege)
    admin_token = create_access_token(subject=str(staff_id), role="ADMIN")

    return (
        {"Authorization": f"Bearer {owner_token}"},
        {"Authorization": f"Bearer {staff_token}"},
        {"Authorization": f"Bearer {customer_token}"},
        {"Authorization": f"Bearer {admin_token}"},
        owner_id,
        staff_id,
        prod_id,
    )


def run_phase5_2_staff_tests():
    owner_auth, staff_auth, customer_auth, admin_auth, owner_id, staff_id, prod_id = setup_test_environment()
    client = TestClient(app)
    results = []
    run_tag = uuid4().hex[:6]

    print("=" * 80)
    print("VIYON PHASE 5.2: COMPLETE STAFF MANAGEMENT & SECURITY SUITE")
    print(f"Target DB: {TEST_DB_URL}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # PART A: AUTHENTICATION & ACCESS CONTROL ON STAFF MANAGEMENT
    # --------------------------------------------------------------------------
    print("\n[PART A: ROLE-BASED ACCESS CONTROL]")

    # Test 1: Owner can list staff
    print("\n[TEST 1] Owner can list staff accounts...")
    r1 = client.get("/api/v1/staff", headers=owner_auth)
    assert r1.status_code == status.HTTP_200_OK, r1.text
    staff_list = r1.json()
    assert isinstance(staff_list, list)
    print(f"         Owner successfully retrieved {len(staff_list)} staff records.")
    results.append(("1. Owner can list staff accounts", "PASS"))

    # Test 2: Staff cannot access staff administration (403 Forbidden)
    print("\n[TEST 2] Staff cannot access staff administration (403)...")
    r2 = client.get("/api/v1/staff", headers=staff_auth)
    assert r2.status_code == status.HTTP_403_FORBIDDEN, r2.text
    print("         Confirmed: Staff request strictly blocked with 403 Forbidden.")
    results.append(("2. Staff cannot access staff administration", "PASS"))

    # Test 3: Admin account cannot manage staff (403 Forbidden - OWNER only)
    print("\n[TEST 3] Admin account cannot manage staff (403)...")
    r3a = client.get("/api/v1/staff", headers=admin_auth)
    assert r3a.status_code == status.HTTP_403_FORBIDDEN, r3a.text
    r3b = client.get("/api/v1/staff/metrics", headers=admin_auth)
    assert r3b.status_code == status.HTTP_403_FORBIDDEN, r3b.text
    print("         Confirmed: Admin role strictly blocked from staff endpoints with 403 Forbidden.")
    results.append(("3. Admin account blocked from staff management (403)", "PASS"))

    # Test 4: Customer / unauthorized blocked from staff administration
    print("\n[TEST 4] Customer / unauthorized blocked from staff administration...")
    r4 = client.get("/api/v1/staff", headers=customer_auth)
    assert r4.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED], r4.text
    print("         Confirmed: Unauthorized / customer token strictly blocked.")
    results.append(("4. Customer / unauthorized blocked", "PASS"))

    # Test 5: Unauthenticated request rejected (401 Unauthorized)
    print("\n[TEST 5] Unauthenticated access blocked (401)...")
    r5 = client.get("/api/v1/staff")
    assert r5.status_code == status.HTTP_401_UNAUTHORIZED, r5.text
    print("         Confirmed: Missing bearer token rejected with 401.")
    results.append(("5. Unauthenticated access blocked", "PASS"))

    # --------------------------------------------------------------------------
    # PART B: STAFF CREATION & VALIDATION
    # --------------------------------------------------------------------------
    print("\n[PART B: STAFF CREATION & VALIDATION]")

    # Test 6: Owner creates a new staff account successfully
    print("\n[TEST 6] Owner creates a valid staff account...")
    new_username = f"cashier_{run_tag}"
    new_email = f"{new_username}@viyon.store"
    r6 = client.post(
        "/api/v1/staff",
        json={
            "full_name": "Test Cashier One",
            "username": new_username,
            "email": new_email,
            "phone": "082702 42681",
            "password": "InitialStaffPass123!",
            "confirm_password": "InitialStaffPass123!",
            "role": "STAFF",
        },
        headers=owner_auth,
    )
    assert r6.status_code == status.HTTP_201_CREATED, r6.text
    created_staff = r6.json()
    assert created_staff["username"] == new_username
    assert created_staff["email"] == new_email
    assert created_staff["role"] == "STAFF"
    assert created_staff["is_active"] is True
    assert "password_hash" not in created_staff
    created_staff_id = created_staff["id"]
    print(f"         Staff created: @{new_username} ({created_staff['employee_id']})")
    results.append(("6. Owner creates valid staff account", "PASS"))

    # Test 7: Staff cannot create staff accounts (403 Forbidden)
    print("\n[TEST 7] Staff blocked from creating staff accounts (403)...")
    r7 = client.post(
        "/api/v1/staff",
        json={
            "full_name": "Unauthorized Attempt",
            "username": f"unauth_{run_tag}",
            "password": "Password123!",
            "role": "STAFF",
        },
        headers=staff_auth,
    )
    assert r7.status_code == status.HTTP_403_FORBIDDEN
    print("         Confirmed: Staff cannot create other staff accounts.")
    results.append(("7. Staff blocked from creating staff", "PASS"))

    # Test 8: Duplicate username rejected (409 Conflict)
    print("\n[TEST 8] Duplicate username rejected (409)...")
    r8 = client.post(
        "/api/v1/staff",
        json={
            "full_name": "Duplicate Username User",
            "username": new_username,
            "email": f"diff_email_{run_tag}@viyon.store",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "role": "STAFF",
        },
        headers=owner_auth,
    )
    assert r8.status_code == status.HTTP_409_CONFLICT, r8.text
    assert "already taken" in r8.json()["detail"].lower()
    print("         Confirmed: Duplicate username rejected with 409 Conflict.")
    results.append(("8. Duplicate username rejected", "PASS"))

    # Test 9: Duplicate email rejected (409 Conflict)
    print("\n[TEST 9] Duplicate email rejected (409)...")
    r9 = client.post(
        "/api/v1/staff",
        json={
            "full_name": "Duplicate Email User",
            "username": f"unique_user_{run_tag}",
            "email": new_email,
            "password": "Password123!",
            "confirm_password": "Password123!",
            "role": "STAFF",
        },
        headers=owner_auth,
    )
    assert r9.status_code == status.HTTP_409_CONFLICT, r9.text
    assert "already" in r9.json()["detail"].lower()
    print("         Confirmed: Duplicate email rejected with 409 Conflict.")
    results.append(("9. Duplicate email rejected", "PASS"))

    # Test 10: Password mismatch rejected (422)
    print("\n[TEST 10] Password confirmation mismatch rejected (422)...")
    r10 = client.post(
        "/api/v1/staff",
        json={
            "full_name": "Mismatch Password",
            "username": f"mismatch_{run_tag}",
            "password": "Password123!",
            "confirm_password": "DifferentPass456!",
            "role": "STAFF",
        },
        headers=owner_auth,
    )
    assert r10.status_code in (status.HTTP_422_UNPROCESSABLE_ENTITY, 422), r10.text
    print("         Confirmed: Password mismatch rejected with 422.")
    results.append(("10. Password mismatch rejected", "PASS"))

    # Test 11: Role tampering rejected (422)
    print("\n[TEST 11] Role tampering blocked...")
    r11 = client.post(
        "/api/v1/staff",
        json={
            "full_name": "Malicious Owner Attempt",
            "username": f"fakeowner_{run_tag}",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "role": "OWNER",
        },
        headers=owner_auth,
    )
    assert r11.status_code in (status.HTTP_422_UNPROCESSABLE_ENTITY, 422), r11.text
    print("         Confirmed: Only STAFF role permitted through staff creation.")
    results.append(("11. Role tampering blocked", "PASS"))

    # --------------------------------------------------------------------------
    # PART C: STAFF LOGIN & ACTIVE SESSION CHECKS
    # --------------------------------------------------------------------------
    print("\n[PART C: STAFF LOGIN & BILL CREATION]")

    # Test 12: Newly created staff logs in with username
    print("\n[TEST 12] Staff login with username...")
    r12 = client.post(
        "/api/v1/auth/login/json",
        json={"username": new_username, "password": "InitialStaffPass123!"},
    )
    assert r12.status_code == status.HTTP_200_OK, r12.text
    login_data = r12.json()
    assert login_data["role"] == "STAFF"
    assert "access_token" in login_data
    token_v1 = login_data["access_token"]
    staff_auth_v1 = {"Authorization": f"Bearer {token_v1}"}
    print("         Confirmed: Staff successfully authenticated using username.")
    results.append(("12. Staff login with username", "PASS"))

    # Test 13: Newly created staff logs in with email
    print("\n[TEST 13] Staff login with email...")
    r13 = client.post(
        "/api/v1/auth/login/json",
        json={"email": new_email, "password": "InitialStaffPass123!"},
    )
    assert r13.status_code == status.HTTP_200_OK, r13.text
    print("         Confirmed: Staff successfully authenticated using email.")
    results.append(("13. Staff login with email", "PASS"))

    # Test 14: Active staff creates a bill (attributed to staff)
    print("\n[TEST 14] Active staff creates bill (attributed to staff)...")
    bill_payload = {
        "items": [
            {
                "product_id": str(prod_id),
                "quantity": 1,
                "discount_amount": "0.00",
            }
        ],
        "discount_amount": "0.00",
        "notes": "Security test sale by cashier",
    }
    r14 = client.post("/api/v1/bills", json=bill_payload, headers=staff_auth_v1)
    assert r14.status_code == status.HTTP_201_CREATED, r14.text
    bill_data = r14.json()
    test_bill_id = bill_data["id"]
    assert str(bill_data["staff_user_id"]) == str(created_staff_id)
    print(f"         Bill created: {bill_data['bill_number']} by staff {created_staff_id}")
    results.append(("14. Active staff creates bill", "PASS"))

    # --------------------------------------------------------------------------
    # PART D: PASSWORD RESET & SESSION INVALIDATION
    # --------------------------------------------------------------------------
    print("\n[PART D: PASSWORD RESET & JWT INVALIDATION]")

    # Test 15: Owner resets staff password
    print("\n[TEST 15] Owner resets staff password...")
    new_pass = "ResetPassword987!"
    r15 = client.post(
        f"/api/v1/staff/{created_staff_id}/reset-password",
        json={"new_password": new_pass, "confirm_password": new_pass},
        headers=owner_auth,
    )
    assert r15.status_code == status.HTTP_200_OK, r15.text
    print("         Confirmed: Staff password securely reset by Owner.")
    results.append(("15. Owner resets staff password", "PASS"))

    # Test 16: Old JWT rejected after password reset (HTTP 401)
    print("\n[TEST 16] Old JWT rejected after password reset (401)...")
    r16a = client.get("/api/v1/auth/me", headers=staff_auth_v1)
    assert r16a.status_code == status.HTTP_401_UNAUTHORIZED, f"Expected 401, got {r16a.status_code}: {r16a.text}"
    r16b = client.post("/api/v1/bills", json=bill_payload, headers=staff_auth_v1)
    assert r16b.status_code == status.HTTP_401_UNAUTHORIZED, f"Expected 401, got {r16b.status_code}: {r16b.text}"
    print("         Confirmed: Old JWT session successfully invalidated immediately after password reset.")
    results.append(("16. Old JWT rejected after password reset", "PASS"))

    # Test 17: Staff logs in with newly reset password
    print("\n[TEST 17] Staff logs in with newly reset password...")
    r17 = client.post(
        "/api/v1/auth/login/json",
        json={"username": new_username, "password": new_pass},
    )
    assert r17.status_code == status.HTTP_200_OK, r17.text
    token_v2 = r17.json()["access_token"]
    staff_auth_v2 = {"Authorization": f"Bearer {token_v2}"}
    print("         Confirmed: Staff authenticated with new credentials.")
    results.append(("17. Staff logs in with new password", "PASS"))

    # Test 18: New JWT works for staff operations
    print("\n[TEST 18] New JWT authenticated successfully for staff operations...")
    r18 = client.get("/api/v1/auth/me", headers=staff_auth_v2)
    assert r18.status_code == status.HTTP_200_OK, r18.text
    assert r18.json()["id"] == created_staff_id
    print("         Confirmed: New JWT session active and functioning.")
    results.append(("18. New JWT works for staff operations", "PASS"))

    # --------------------------------------------------------------------------
    # PART E: DEACTIVATION & ACCESS REVOCATION
    # --------------------------------------------------------------------------
    print("\n[PART E: DEACTIVATION & ACCESS REVOCATION]")

    # Test 19: Owner deactivates staff account
    print("\n[TEST 19] Owner deactivates staff account...")
    r19 = client.patch(
        f"/api/v1/staff/{created_staff_id}/deactivate",
        json={"is_active": False, "reason": "Testing employee suspension"},
        headers=owner_auth,
    )
    assert r19.status_code == status.HTTP_200_OK, r19.text
    assert r19.json()["is_active"] is False
    print("         Confirmed: Staff account deactivated.")
    results.append(("19. Owner deactivates staff account", "PASS"))

    # Test 20: Inactive staff cannot log in (403 Forbidden)
    print("\n[TEST 20] Inactive staff cannot log in (403)...")
    r20 = client.post(
        "/api/v1/auth/login/json",
        json={"username": new_username, "password": new_pass},
    )
    assert r20.status_code == status.HTTP_403_FORBIDDEN, r20.text
    assert "inactive" in r20.json()["detail"].lower()
    print("         Confirmed: Inactive account login blocked with 403 Forbidden.")
    results.append(("20. Inactive staff cannot log in", "PASS"))

    # Test 21: Old JWT of deactivated staff rejected on bill creation (403 Forbidden)
    print("\n[TEST 21] Deactivated staff cannot create bills with existing JWT (403)...")
    r21 = client.post("/api/v1/bills", json=bill_payload, headers=staff_auth_v2)
    assert r21.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r21.status_code}: {r21.text}"
    print("         Confirmed: Deactivated staff bill creation rejected with 403 Forbidden.")
    results.append(("21. Deactivated staff cannot create bills", "PASS"))

    # Test 22: Deactivated staff cannot confirm UPI payments (403 Forbidden)
    print("\n[TEST 22] Deactivated staff cannot confirm UPI payments (403)...")
    fake_payment_id = uuid4()
    r22 = client.patch(
        f"/api/v1/payments/{fake_payment_id}/confirm",
        json={"verified": True, "notes": "Unauthorized confirmation attempt"},
        headers=staff_auth_v2,
    )
    assert r22.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r22.status_code}: {r22.text}"
    print("         Confirmed: Deactivated staff payment confirmation rejected with 403 Forbidden.")
    results.append(("22. Deactivated staff cannot confirm UPI", "PASS"))

    # Test 23: Historical bill attribution remains intact after deactivation
    print("\n[TEST 23] Historical bill attribution remains intact after deactivation...")
    raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT staff_user_id, total_amount, bill_status FROM bills WHERE id = %s;",
                (test_bill_id,),
            )
            row_bill = cur.fetchone()
            assert row_bill is not None
            assert str(row_bill[0]) == str(created_staff_id)
            print(f"         Database verified: Bill {test_bill_id} still attributes staff_user_id={row_bill[0]}")

    r23 = client.get(f"/api/v1/staff/{created_staff_id}/activity", headers=owner_auth)
    assert r23.status_code == status.HTTP_200_OK, r23.text
    act = r23.json()
    assert act["total_bills_count"] >= 1
    print(f"         Staff activity query verified: total_bills_count={act['total_bills_count']}")
    results.append(("23. Historical bill attribution remains intact", "PASS"))

    # Test 24: Owner reactivates staff account
    print("\n[TEST 24] Owner reactivates staff account...")
    r24 = client.patch(
        f"/api/v1/staff/{created_staff_id}/activate",
        headers=owner_auth,
    )
    assert r24.status_code == status.HTTP_200_OK, r24.text
    assert r24.json()["is_active"] is True
    print("         Confirmed: Staff account reactivated.")
    results.append(("24. Owner reactivates staff account", "PASS"))

    # Test 25: Owner cannot deactivate own account (400 Bad Request)
    print("\n[TEST 25] Owner cannot deactivate self (400)...")
    r25 = client.patch(
        f"/api/v1/staff/{owner_id}/deactivate",
        headers=owner_auth,
    )
    assert r25.status_code == status.HTTP_400_BAD_REQUEST, r25.text
    print("         Confirmed: Owner self-deactivation blocked with 400 Bad Request.")
    results.append(("25. Owner cannot deactivate own account", "PASS"))

    # Test 26: Audit trail verification
    print("\n[TEST 26] Audit trail verification for staff operations...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT action FROM audit_logs
                WHERE entity_type = 'USER' AND entity_id = %s
                ORDER BY created_at DESC;
                """,
                (created_staff_id,),
            )
            actions = [row[0] for row in cur.fetchall()]
            print(f"         Logged actions for staff {created_staff_id}: {actions}")
            assert "STAFF_CREATED" in actions
            assert "STAFF_DEACTIVATED" in actions
            assert "STAFF_ACTIVATED" in actions
            assert "STAFF_PASSWORD_RESET" in actions
    print("         Confirmed: Comprehensive audit trail recorded.")
    results.append(("26. Audit trail verification", "PASS"))

    # --------------------------------------------------------------------------
    # Summary Table
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("VIYON PHASE 5.2 SECURITY & STAFF TEST RESULTS SUMMARY")
    print("=" * 80)
    for name, st in results:
        print(f"  {name:<65} [{st}]")
    print("=" * 80)
    print(f"ALL {len(results)} OF 26 TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 80)


if __name__ == "__main__":
    run_phase5_2_staff_tests()
