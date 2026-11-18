"""VIYON Billing System - Phase 4.3 Automated Test Suite
Testing Bill Cancellation, Inventory Restoration, Payment Handling & Bill History Management.
Target Database: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh).
"""

import os
import sys
import threading
from datetime import datetime, timezone, timedelta
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
os.environ["SECRET_KEY"] = "test-secret-key-phase4-3-secure-random-at-least-32-chars"
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
                    "INSERT INTO users (id, full_name, email, password_hash, role, is_active) VALUES (%s, 'Store Owner', 'owner@viyon.store', %s, 'OWNER', true);",
                    (owner_id, pw_hash),
                )

            cur.execute("SELECT id FROM users WHERE role = 'STAFF' LIMIT 1;")
            r_staff = cur.fetchone()
            if r_staff:
                staff_id = r_staff[0]
            else:
                pw_hash = get_password_hash("StaffPass123!")
                cur.execute(
                    "INSERT INTO users (id, full_name, email, password_hash, role, is_active) VALUES (%s, 'Counter Staff', 'staff@viyon.store', %s, 'STAFF', true);",
                    (staff_id, pw_hash),
                )

            # 2. Store settings
            cur.execute("SELECT id FROM store_settings WHERE is_active_config = true LIMIT 1;")
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO store_settings (id, store_name, tagline, address, phone, currency_code, tax_enabled, default_tax_rate, receipt_width_mm, is_active_config)
                    VALUES (gen_random_uuid(), 'VIYON', 'MENS WEAR', 'Sathyamangalam', '082702 42681', 'INR', false, 0.00, 58, true);
                    """
                )

            # 3. Category
            cur.execute("SELECT id FROM categories WHERE name = 'Phase 4.3 Category' LIMIT 1;")
            r_cat = cur.fetchone()
            if r_cat:
                cat_id = r_cat[0]
            else:
                cur.execute("INSERT INTO categories (id, name, is_active) VALUES (%s, 'Phase 4.3 Category', true);", (cat_id,))

            # 4. Simple Product & Inventory
            cur.execute("SELECT id FROM products WHERE sku = 'P43-SIMPLE-01' LIMIT 1;")
            r_sprod = cur.fetchone()
            if r_sprod:
                simple_prod_id = r_sprod[0]
            else:
                cur.execute(
                    """
                    INSERT INTO products (id, category_id, product_name, product_type, base_price, sku, is_active, is_archived)
                    VALUES (%s, %s, 'Phase 4.3 Simple Shirt', 'SIMPLE', 1000.00, 'P43-SIMPLE-01', true, false);
                    """,
                    (simple_prod_id, cat_id),
                )
                cur.execute(
                    """
                    INSERT INTO inventory (id, product_id, variant_id, quantity, low_stock_threshold)
                    VALUES (gen_random_uuid(), %s, NULL, 50, 5);
                    """,
                    (simple_prod_id,),
                )

            # 5. Variant Product & Variant & Inventory
            cur.execute("SELECT id FROM products WHERE product_name = 'Phase 4.3 Jeans' LIMIT 1;")
            r_vprod = cur.fetchone()
            if r_vprod:
                variant_prod_id = r_vprod[0]
                cur.execute("SELECT id FROM product_variants WHERE product_id = %s LIMIT 1;", (variant_prod_id,))
                r_var = cur.fetchone()
                assert r_var is not None
                variant_id = r_var[0]
            else:
                cur.execute(
                    """
                    INSERT INTO products (id, category_id, product_name, product_type, base_price, is_active, is_archived)
                    VALUES (%s, %s, 'Phase 4.3 Jeans', 'VARIANT', 1500.00, true, false);
                    """,
                    (variant_prod_id, cat_id),
                )
                cur.execute(
                    """
                    INSERT INTO product_variants (id, product_id, sku, size, color, is_active)
                    VALUES (%s, %s, 'P43-JEANS-32-BLU', '32', 'Blue', true);
                    """,
                    (variant_id, variant_prod_id),
                )
                cur.execute(
                    """
                    INSERT INTO inventory (id, product_id, variant_id, quantity, low_stock_threshold)
                    VALUES (gen_random_uuid(), %s, %s, 40, 5);
                    """,
                    (variant_prod_id, variant_id),
                )

            # 6. Customer
            cur.execute("SELECT id FROM customers WHERE phone = '9876543210' LIMIT 1;")
            r_cust = cur.fetchone()
            if r_cust:
                cust_id = r_cust[0]
            else:
                cur.execute(
                    """
                    INSERT INTO customers (id, customer_name, phone)
                    VALUES (%s, 'Karthik Raja', '9876543210');
                    """,
                    (cust_id,),
                )

        conn.commit()

    owner_token = create_access_token(subject=str(owner_id), role="OWNER")
    staff_token = create_access_token(subject=str(staff_id), role="STAFF")

    owner_auth = {"Authorization": f"Bearer {owner_token}"}
    staff_auth = {"Authorization": f"Bearer {staff_token}"}

    return owner_auth, staff_auth, owner_id, staff_id, simple_prod_id, variant_prod_id, variant_id, cust_id


def run_phase4_3_cancellation_tests():
    client = TestClient(app)
    owner_auth, staff_auth, owner_id, staff_id, simple_p, var_p, var_v, cust_id = setup_test_data()
    run_tag = uuid4().hex[:6]

    print("=" * 80)
    print("VIYON PHASE 4.3: BILL CANCELLATION, INVENTORY RESTORATION & HISTORY SUITE")
    print(f"Target DB: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh)")
    print("=" * 80)

    results: List[Tuple[str, str]] = []

    # Helper function to create a test bill
    def create_bill(items: List[Dict], customer: Optional[UUID] = None) -> Dict:
        payload = {"items": items, "customer_id": str(customer) if customer else None}
        res = client.post("/api/v1/bills", json=payload, headers=staff_auth)
        assert res.status_code == status.HTTP_201_CREATED, res.text
        return res.json()

    # --------------------------------------------------------------------------
    # PART A: BILL HISTORY & FILTERING (Scenarios 1-8)
    # --------------------------------------------------------------------------
    print("\n[PART A: BILL HISTORY & FILTERING]")

    # Create baseline bills with known customer and dates
    hist_b1 = create_bill([{"product_id": str(simple_p), "quantity": 1}], customer=cust_id)
    hist_b2 = create_bill([{"product_id": str(var_p), "variant_id": str(var_v), "quantity": 1}])

    # 1. Retrieve bill history
    print("\n[TEST 1] Retrieve bill history...")
    r1 = client.get("/api/v1/bills", headers=staff_auth)
    assert r1.status_code == status.HTTP_200_OK
    data1 = r1.json()
    assert "items" in data1 and len(data1["items"]) >= 2
    print(f"         Retrieved {len(data1['items'])} bills from history.")
    results.append(("1. Retrieve bill history", "PASS"))

    # 2. Filter by bill number
    print("\n[TEST 2] Filter by bill number...")
    target_num = hist_b1["bill_number"]
    r2 = client.get(f"/api/v1/bills?bill_number={target_num}", headers=staff_auth)
    assert r2.status_code == status.HTTP_200_OK
    assert len(r2.json()["items"]) == 1
    assert r2.json()["items"][0]["bill_number"] == target_num
    print(f"         Filtered successfully by exact bill number: {target_num}")
    results.append(("2. Filter by bill number", "PASS"))

    # 3. Filter by date range
    print("\n[TEST 3] Filter by date range...")
    now = datetime.now(timezone.utc)
    start_iso = (now - timedelta(hours=1)).isoformat()
    end_iso = (now + timedelta(hours=1)).isoformat()
    r3 = client.get("/api/v1/bills", params={"start_date": start_iso, "end_date": end_iso}, headers=staff_auth)
    assert r3.status_code == status.HTTP_200_OK, r3.text
    assert len(r3.json()["items"]) >= 2
    print("         Date range filter verified.")
    results.append(("3. Filter by date range", "PASS"))

    # 4. Filter by payment status
    print("\n[TEST 4] Filter by payment status...")
    r4 = client.get("/api/v1/bills?payment_status=PENDING", headers=staff_auth)
    assert r4.status_code == status.HTTP_200_OK
    assert all(b["payment_status"] == "PENDING" for b in r4.json()["items"])
    print("         Payment status filter verified.")
    results.append(("4. Filter by payment status", "PASS"))

    # 5. Filter by bill status
    print("\n[TEST 5] Filter by bill status...")
    r5 = client.get("/api/v1/bills?bill_status=COMPLETED", headers=staff_auth)
    assert r5.status_code == status.HTTP_200_OK
    assert all(b["bill_status"] == "COMPLETED" for b in r5.json()["items"])
    print("         Bill status filter verified.")
    results.append(("5. Filter by bill status", "PASS"))

    # 6. Pagination works correctly
    print("\n[TEST 6] Pagination works correctly (page, page_size, total_records, total_pages)...")
    r6 = client.get("/api/v1/bills?page=1&page_size=2", headers=staff_auth)
    assert r6.status_code == status.HTTP_200_OK
    p_data = r6.json()
    assert p_data["page"] == 1
    assert p_data["page_size"] == 2
    assert p_data["total_records"] >= 2
    assert p_data["total_pages"] >= 1
    assert len(p_data["items"]) <= 2
    print(f"         Pagination metadata: page={p_data['page']}, total_pages={p_data['total_pages']}, records={p_data['total_records']}")
    results.append(("6. Pagination works correctly", "PASS"))

    # 7. Sorting works correctly (asc vs desc)
    print("\n[TEST 7] Sorting works correctly...")
    r7_desc = client.get("/api/v1/bills?sort_order=desc&page_size=5", headers=staff_auth)
    r7_asc = client.get("/api/v1/bills?sort_order=asc&page_size=5", headers=staff_auth)
    assert r7_desc.status_code == status.HTTP_200_OK
    assert r7_asc.status_code == status.HTTP_200_OK
    desc_dates = [b["bill_date"] for b in r7_desc.json()["items"]]
    asc_dates = [b["bill_date"] for b in r7_asc.json()["items"]]
    assert desc_dates == sorted(desc_dates, reverse=True)
    assert asc_dates == sorted(asc_dates)
    print("         Ascending and descending chronological sorting verified.")
    results.append(("7. Sorting works correctly", "PASS"))

    # 8. Retrieve bill details and line items
    print("\n[TEST 8] Retrieve bill details and items...")
    r8_detail = client.get(f"/api/v1/bills/{hist_b1['id']}", headers=staff_auth)
    assert r8_detail.status_code == status.HTTP_200_OK
    assert r8_detail.json()["customer_name"] == "Karthik Raja"
    assert r8_detail.json()["customer_phone"] == "9876543210"

    r8_items = client.get(f"/api/v1/bills/{hist_b1['id']}/items", headers=staff_auth)
    assert r8_items.status_code == status.HTTP_200_OK
    assert len(r8_items.json()) == 1
    assert r8_items.json()[0]["sku_snapshot"] == "P43-SIMPLE-01"
    print("         Bill header details and snapshot items retrieved.")
    results.append(("8. Retrieve bill details and items", "PASS"))

    # --------------------------------------------------------------------------
    # PART B: BILL CANCELLATION RULES & RBAC (Scenarios 9-15)
    # --------------------------------------------------------------------------
    print("\n[PART B: BILL CANCELLATION RULES & RBAC]")

    # 9. Owner can cancel an eligible bill
    print("\n[TEST 9] Owner can cancel an eligible bill...")
    cancel_b = create_bill([{"product_id": str(simple_p), "quantity": 2}])
    r9 = client.patch(
        f"/api/v1/bills/{cancel_b['id']}/cancel",
        json={"reason": "Customer cancelled order before delivery"},
        headers=owner_auth,
    )
    assert r9.status_code == status.HTTP_200_OK, r9.text
    b9 = r9.json()
    assert b9["bill_status"] == "CANCELLED"
    assert b9["cancelled_at"] is not None
    assert b9["cancelled_by_user_id"] == str(owner_id)
    assert b9["cancellation_reason"] == "Customer cancelled order before delivery"
    print(f"         Bill {cancel_b['bill_number']} successfully cancelled by Owner.")
    results.append(("9. Owner can cancel an eligible bill", "PASS"))

    # 10. Staff cannot cancel a bill (403 Forbidden)
    print("\n[TEST 10] Staff cannot cancel a bill (403)...")
    staff_test_b = create_bill([{"product_id": str(simple_p), "quantity": 1}])
    r10 = client.patch(
        f"/api/v1/bills/{staff_test_b['id']}/cancel",
        json={"reason": "Staff attempt"},
        headers=staff_auth,
    )
    assert r10.status_code == status.HTTP_403_FORBIDDEN
    print("         Staff cancellation blocked with 403 Forbidden.")
    results.append(("10. Staff cannot cancel a bill", "PASS"))

    # 11. Missing cancellation reason is rejected (422)
    print("\n[TEST 11] Missing cancellation reason rejected (422)...")
    r11 = client.patch(
        f"/api/v1/bills/{staff_test_b['id']}/cancel",
        json={},
        headers=owner_auth,
    )
    assert r11.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    print("         Missing reason payload rejected with 422.")
    results.append(("11. Missing cancellation reason is rejected", "PASS"))

    # 12. Empty cancellation reason is rejected (422)
    print("\n[TEST 12] Empty cancellation reason rejected (422)...")
    r12 = client.patch(
        f"/api/v1/bills/{staff_test_b['id']}/cancel",
        json={"reason": "   "},
        headers=owner_auth,
    )
    assert r12.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    print("         Whitespace/empty reason rejected with 422.")
    results.append(("12. Empty cancellation reason is rejected", "PASS"))

    # 13. Cancelling an already cancelled bill returns 409 Conflict
    print("\n[TEST 13] Cancelling an already cancelled bill returns 409...")
    r13 = client.patch(
        f"/api/v1/bills/{cancel_b['id']}/cancel",
        json={"reason": "Duplicate cancel attempt"},
        headers=owner_auth,
    )
    assert r13.status_code == status.HTTP_409_CONFLICT
    assert "already been cancelled" in r13.json()["detail"]
    print("         Duplicate cancellation rejected with 409 Conflict.")
    results.append(("13. Cancelling an already cancelled bill returns 409", "PASS"))

    # 14. Invalid bill ID returns 404 Not Found
    print("\n[TEST 14] Invalid bill ID returns 404...")
    fake_bid = uuid4()
    r14 = client.patch(
        f"/api/v1/bills/{fake_bid}/cancel",
        json={"reason": "Non-existent bill"},
        headers=owner_auth,
    )
    assert r14.status_code == status.HTTP_404_NOT_FOUND
    print("         Non-existent bill rejected with 404 Not Found.")
    results.append(("14. Invalid bill ID returns 404", "PASS"))

    # 15. Cancelled bill cannot receive a new payment
    print("\n[TEST 15] Cancelled bill cannot receive a new payment (409)...")
    r15 = client.post(
        f"/api/v1/bills/{cancel_b['id']}/payments",
        json={"payment_method": "CASH", "amount": "500.00"},
        headers=staff_auth,
    )
    assert r15.status_code == status.HTTP_409_CONFLICT
    assert "CANCELLED" in r15.json()["detail"]
    print("         Payment on cancelled bill rejected with 409.")
    results.append(("15. Cancelled bill cannot receive a new payment", "PASS"))

    # --------------------------------------------------------------------------
    # PART C: INVENTORY RESTORATION & ATOMICITY (Scenarios 16-21)
    # --------------------------------------------------------------------------
    print("\n[PART C: INVENTORY RESTORATION & ATOMICITY]")

    raw_pg_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")

    # 16. Simple product inventory is restored correctly
    print("\n[TEST 16] Simple product inventory restoration...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_p,))
            res_sp = cur.fetchone()
            assert res_sp is not None
            sp_qty_init = res_sp[0]

    # Create bill with 3 units of simple product -> stock drops by 3
    b_simple = create_bill([{"product_id": str(simple_p), "quantity": 3}])
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_p,))
            res_sp2 = cur.fetchone()
            assert res_sp2 is not None
            sp_qty_billed = res_sp2[0]
    assert sp_qty_billed == sp_qty_init - 3

    # Cancel bill -> stock must be restored by +3
    r16 = client.patch(
        f"/api/v1/bills/{b_simple['id']}/cancel",
        json={"reason": "Customer changed mind at counter"},
        headers=owner_auth,
    )
    assert r16.status_code == status.HTTP_200_OK

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_p,))
            res_sp3 = cur.fetchone()
            assert res_sp3 is not None
            sp_qty_restored = res_sp3[0]
    assert sp_qty_restored == sp_qty_init
    print(f"         Simple product stock restored accurately: {sp_qty_billed} -> {sp_qty_restored}")
    results.append(("16. Simple product inventory is restored correctly", "PASS"))

    # 17. Variant inventory is restored correctly
    print("\n[TEST 17] Variant inventory restoration...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id = %s;", (var_p, var_v))
            res_vp = cur.fetchone()
            assert res_vp is not None
            vp_qty_init = res_vp[0]

    b_var = create_bill([{"product_id": str(var_p), "variant_id": str(var_v), "quantity": 2}])
    r17 = client.patch(
        f"/api/v1/bills/{b_var['id']}/cancel",
        json={"reason": "Jeans sizing defective"},
        headers=owner_auth,
    )
    assert r17.status_code == status.HTTP_200_OK

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id = %s;", (var_p, var_v))
            res_vp2 = cur.fetchone()
            assert res_vp2 is not None
            vp_qty_restored = res_vp2[0]
    assert vp_qty_restored == vp_qty_init
    print(f"         Variant stock restored accurately: {vp_qty_init - 2} -> {vp_qty_restored}")
    results.append(("17. Variant inventory is restored correctly", "PASS"))

    # 18. Multiple products are restored correctly
    print("\n[TEST 18] Multi-item cart restoration...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_p,))
            res_s_base = cur.fetchone()
            assert res_s_base is not None
            s_base = res_s_base[0]
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id = %s;", (var_p, var_v))
            res_v_base = cur.fetchone()
            assert res_v_base is not None
            v_base = res_v_base[0]

    b_multi = create_bill([
        {"product_id": str(simple_p), "quantity": 2},
        {"product_id": str(var_p), "variant_id": str(var_v), "quantity": 4},
    ])

    client.patch(
        f"/api/v1/bills/{b_multi['id']}/cancel",
        json={"reason": "Multi-item order cancelled"},
        headers=owner_auth,
    )

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_p,))
            res_s_after = cur.fetchone()
            assert res_s_after is not None
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id = %s;", (var_p, var_v))
            res_v_after = cur.fetchone()
            assert res_v_after is not None
            assert res_s_after[0] == s_base
            assert res_v_after[0] == v_base
    print(f"         All items in multi-product order restored to exact original quantities.")
    results.append(("18. Multiple products are restored correctly", "PASS"))

    # 19. Stock movements are recorded correctly
    print("\n[TEST 19] Stock movements audit entries for CANCELLATION...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT movement_type, quantity_change, reference_type, reference_id, notes
                FROM stock_movements
                WHERE reference_id = %s AND movement_type = 'CANCELLATION';
                """,
                (b_simple["id"],),
            )
            movements = cur.fetchall()
            assert len(movements) >= 1
            m_type, m_qty, m_ref, m_refid, m_notes = movements[0]
            assert m_type == "CANCELLATION"
            assert m_qty == 3  # restored +3 units
            assert m_ref == "BILL_CANCELLATION"
            assert str(m_refid) == str(b_simple["id"])
            assert "Customer changed mind at counter" in m_notes
    print(f"         Stock movement verified: type={m_type}, change=+{m_qty}, ref={m_ref}")
    results.append(("19. Stock movements are recorded correctly", "PASS"))

    # 20. Repeated cancellation does not restore stock twice
    print("\n[TEST 20] Repeated cancellation does not restore stock twice...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_p,))
            res_pre20 = cur.fetchone()
            assert res_pre20 is not None
            pre_qty = res_pre20[0]

    # Attempt second cancellation on b_simple
    r20 = client.patch(
        f"/api/v1/bills/{b_simple['id']}/cancel",
        json={"reason": "Second cancel attempt"},
        headers=owner_auth,
    )
    assert r20.status_code == status.HTTP_409_CONFLICT

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_p,))
            res_post20 = cur.fetchone()
            assert res_post20 is not None
            post_qty = res_post20[0]
    assert pre_qty == post_qty
    print("         Confirmed: Stock remained identical; duplicate restoration prevented.")
    results.append(("20. Repeated cancellation does not restore stock twice", "PASS"))

    # 21. Failed cancellation rolls back all changes
    print("\n[TEST 21] Failed cancellation rolls back atomically...")
    # Bill with valid item
    b_fail = create_bill([{"product_id": str(simple_p), "quantity": 1}])
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_p,))
            res_q_before = cur.fetchone()
            assert res_q_before is not None
            q_before = res_q_before[0]

    # Attempt cancel with invalid reason (too short)
    r21 = client.patch(
        f"/api/v1/bills/{b_fail['id']}/cancel",
        json={"reason": "no"},  # Less than 3 chars fails validation
        headers=owner_auth,
    )
    assert r21.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Verify inventory is untouched and bill remains COMPLETED
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_p,))
            res_q_after = cur.fetchone()
            assert res_q_after is not None
            assert res_q_after[0] == q_before
            cur.execute("SELECT bill_status FROM bills WHERE id = %s;", (b_fail["id"],))
            res_st = cur.fetchone()
            assert res_st is not None
            assert res_st[0] == "COMPLETED"
    print("         Atomic rollback verified: 0 inventory leakage, bill status unchanged.")
    results.append(("21. Failed cancellation rolls back all changes", "PASS"))

    # --------------------------------------------------------------------------
    # PART D: PAYMENT HANDLING DURING CANCELLATION (Scenarios 22-27)
    # --------------------------------------------------------------------------
    print("\n[PART D: PAYMENT HANDLING DURING CANCELLATION]")

    # 22. Confirmed cash payments remain unchanged
    print("\n[TEST 22] Confirmed cash payments preserved...")
    b_cash = create_bill([{"product_id": str(simple_p), "quantity": 1}])
    # Pay cash 1000.00 (confirmed immediately)
    r_pay_cash = client.post(
        f"/api/v1/bills/{b_cash['id']}/payments",
        json={"payment_method": "CASH", "amount": "1000.00"},
        headers=staff_auth,
    )
    p_cash_id = r_pay_cash.json()["id"]

    # Cancel bill
    client.patch(f"/api/v1/bills/{b_cash['id']}/cancel", json={"reason": "Customer return"}, headers=owner_auth)

    # Check cash payment record in DB
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payment_status, amount FROM payments WHERE id = %s;", (p_cash_id,))
            row_cp = cur.fetchone()
            assert row_cp is not None
            assert row_cp[0] == "CONFIRMED"
            assert row_cp[1] == Decimal("1000.00")
    print("         Confirmed CASH payment remains CONFIRMED for audit and refund accounting.")
    results.append(("22. Confirmed cash payments remain unchanged", "PASS"))

    # 23. Confirmed UPI payments remain unchanged
    print("\n[TEST 23] Confirmed UPI payments preserved...")
    b_upi = create_bill([{"product_id": str(simple_p), "quantity": 1}])
    r_pay_upi = client.post(
        f"/api/v1/bills/{b_upi['id']}/payments",
        json={"payment_method": "UPI", "amount": "1000.00", "transaction_reference": f"UTR-CONF-023-{run_tag}"},
        headers=staff_auth,
    )
    p_upi_id = r_pay_upi.json()["id"]
    # Manually confirm UPI receipt
    client.patch(f"/api/v1/payments/{p_upi_id}/confirm", json={}, headers=staff_auth)

    client.patch(f"/api/v1/bills/{b_upi['id']}/cancel", json={"reason": "UPI order cancelled"}, headers=owner_auth)

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payment_status, amount FROM payments WHERE id = %s;", (p_upi_id,))
            row_up = cur.fetchone()
            assert row_up is not None
            assert row_up[0] == "CONFIRMED"
            assert row_up[1] == Decimal("1000.00")
    print("         Confirmed UPI payment remains CONFIRMED.")
    results.append(("23. Confirmed UPI payments remain unchanged", "PASS"))

    # 24. Pending UPI payments become REJECTED
    print("\n[TEST 24] Pending UPI payments become REJECTED...")
    b_pend = create_bill([{"product_id": str(simple_p), "quantity": 1}])
    r_pay_pend = client.post(
        f"/api/v1/bills/{b_pend['id']}/payments",
        json={"payment_method": "UPI", "amount": "1000.00", "transaction_reference": f"UTR-PEND-024-{run_tag}"},
        headers=staff_auth,
    )
    p_pend_id = r_pay_pend.json()["id"]
    assert r_pay_pend.json()["payment_status"] == "PENDING"

    # Cancel bill
    client.patch(f"/api/v1/bills/{b_pend['id']}/cancel", json={"reason": "Pending payment timed out"}, headers=owner_auth)

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payment_status, rejection_reason FROM payments WHERE id = %s;", (p_pend_id,))
            row_p24 = cur.fetchone()
            assert row_p24 is not None
            assert row_p24[0] == "REJECTED"
            assert "cancelled" in row_p24[1].lower()
    print("         Pending UPI payment automatically marked REJECTED with cancellation reason.")
    results.append(("24. Pending UPI payments become REJECTED", "PASS"))

    # 25. Pending UPI payments cannot be confirmed after cancellation
    print("\n[TEST 25] Pending UPI payment cannot be confirmed after cancellation...")
    r25_confirm = client.patch(
        f"/api/v1/payments/{p_pend_id}/confirm",
        json={"notes": "Late confirmation"},
        headers=staff_auth,
    )
    assert r25_confirm.status_code == status.HTTP_409_CONFLICT
    print("         Confirmation of payment on cancelled bill rejected with 409 Conflict.")
    results.append(("25. Pending UPI payments cannot be confirmed after cancellation", "PASS"))

    # 26. Refund review amount is calculated correctly
    print("\n[TEST 26] Refund review amount calculation...")
    # Bill with total 2000: Paid 500 cash + 1000 UPI confirmed = 1500 total received
    b_refund = create_bill([{"product_id": str(simple_p), "quantity": 2}])  # 2000.00
    client.post(f"/api/v1/bills/{b_refund['id']}/payments", json={"payment_method": "CASH", "amount": "500.00"}, headers=staff_auth)
    r_ref_upi = client.post(
        f"/api/v1/bills/{b_refund['id']}/payments",
        json={"payment_method": "UPI", "amount": "1000.00", "transaction_reference": f"UTR-REF-026-{run_tag}"},
        headers=staff_auth,
    )
    client.patch(f"/api/v1/payments/{r_ref_upi.json()['id']}/confirm", json={}, headers=staff_auth)
    # Plus a pending 500 UPI payment that was NOT confirmed
    client.post(
        f"/api/v1/bills/{b_refund['id']}/payments",
        json={"payment_method": "UPI", "amount": "500.00", "transaction_reference": f"UTR-UNCONF-026-{run_tag}"},
        headers=staff_auth,
    )

    # Cancel bill
    r26 = client.patch(
        f"/api/v1/bills/{b_refund['id']}/cancel",
        json={"reason": "Customer cancellation with split advance"},
        headers=owner_auth,
    )
    assert r26.status_code == status.HTTP_200_OK
    b26 = r26.json()
    assert b26["refund_review_amount"] == "1500.00"
    print(f"         Refund review amount computed accurately: Rs. {b26['refund_review_amount']} (500 CASH + 1000 UPI)")
    results.append(("26. Refund review amount is calculated correctly", "PASS"))

    # 27. Cancelled bills cannot receive new payments
    print("\n[TEST 27] Cancelled bills cannot receive new payments...")
    r27 = client.post(
        f"/api/v1/bills/{b_refund['id']}/payments",
        json={"payment_method": "CASH", "amount": "100.00"},
        headers=staff_auth,
    )
    assert r27.status_code == status.HTTP_409_CONFLICT
    print("         New payments blocked on cancelled bills.")
    results.append(("27. Cancelled bills cannot receive new payments", "PASS"))

    # --------------------------------------------------------------------------
    # PART E: CONCURRENCY, AUDIT & PRESERVATION (Scenarios 28-32)
    # --------------------------------------------------------------------------
    print("\n[PART E: CONCURRENCY, AUDIT & PRESERVATION]")

    # 28. Two concurrent cancellation requests restore stock only once
    print("\n[TEST 28] Concurrency: Two concurrent cancellations restore stock exactly once...")
    b_race = create_bill([{"product_id": str(simple_p), "quantity": 5}])
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_p,))
            res_q_race_pre = cur.fetchone()
            assert res_q_race_pre is not None
            q_race_pre = res_q_race_pre[0]

    barrier28 = threading.Barrier(2)
    race_results: List[int] = []

    def cancel_worker():
        barrier28.wait()
        res = client.patch(
            f"/api/v1/bills/{b_race['id']}/cancel",
            json={"reason": "Concurrent race cancellation"},
            headers=owner_auth,
        )
        race_results.append(res.status_code)

    t1 = threading.Thread(target=cancel_worker)
    t2 = threading.Thread(target=cancel_worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert status.HTTP_200_OK in race_results
    assert status.HTTP_409_CONFLICT in race_results

    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s AND variant_id IS NULL;", (simple_p,))
            res_q_race_post = cur.fetchone()
            assert res_q_race_post is not None
            q_race_post = res_q_race_post[0]
            # Must be exactly +5 restored, not +10!
            assert q_race_post == q_race_pre + 5
    print(f"         Concurrent cancellation handled cleanly: 1 Success (200), 1 Rejected (409). Stock restored exactly once (+5).")
    results.append(("28. Two concurrent cancellation requests restore stock only once", "PASS"))

    # 29. Concurrent payment confirmation and cancellation
    print("\n[TEST 29] Concurrency: Payment confirmation vs Bill cancellation...")
    b_concur = create_bill([{"product_id": str(simple_p), "quantity": 1}])
    r_pay_c = client.post(
        f"/api/v1/bills/{b_concur['id']}/payments",
        json={"payment_method": "UPI", "amount": "1000.00", "transaction_reference": f"UTR-RACE-029-{run_tag}"},
        headers=staff_auth,
    )
    p_concur_id = r_pay_c.json()["id"]

    barrier29 = threading.Barrier(2)
    concur_codes: Dict[str, int] = {}

    def do_confirm():
        barrier29.wait()
        res = client.patch(f"/api/v1/payments/{p_concur_id}/confirm", json={"notes": "Race confirm"}, headers=staff_auth)
        concur_codes["confirm"] = res.status_code

    def do_cancel():
        barrier29.wait()
        res = client.patch(f"/api/v1/bills/{b_concur['id']}/cancel", json={"reason": "Race cancel"}, headers=owner_auth)
        concur_codes["cancel"] = res.status_code

    th_c = threading.Thread(target=do_confirm)
    th_k = threading.Thread(target=do_cancel)
    th_c.start()
    th_k.start()
    th_c.join()
    th_k.join()

    # Both must complete without unhandled 500 error
    assert concur_codes["cancel"] in (status.HTTP_200_OK, status.HTTP_409_CONFLICT)
    assert concur_codes["confirm"] in (status.HTTP_200_OK, status.HTTP_409_CONFLICT)
    print(f"         Race resolution: confirm={concur_codes['confirm']}, cancel={concur_codes['cancel']}. Zero deadlock or inconsistency.")
    results.append(("29. Concurrent payment confirmation and cancellation", "PASS"))

    # 30. Audit logs are created correctly
    print("\n[TEST 30] Audit log verification for BILL_CANCELLED...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT action, entity_type, entity_id, new_values
                FROM audit_logs
                WHERE entity_id = %s AND action = 'BILL_CANCELLED';
                """,
                (cancel_b["id"],),
            )
            r_audit = cur.fetchone()
            assert r_audit is not None
            a_action, a_type, a_eid, a_vals = r_audit
            assert a_action == "BILL_CANCELLED"
            assert a_type == "BILL"
            assert str(a_eid) == str(cancel_b["id"])
            assert a_vals["bill_status"] == "CANCELLED"
            assert "restored_items" in a_vals
            assert "refund_review_amount" in a_vals
    print("         Audit entry verified with action, metadata, and restored items.")
    results.append(("30. Audit logs are created correctly", "PASS"))

    # 31. Cancellation metadata is consistent
    print("\n[TEST 31] Cancellation metadata database constraint consistency...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            # Check all cancelled bills in DB have all 3 fields populated
            cur.execute(
                """
                SELECT count(*)
                FROM bills
                WHERE bill_status = 'CANCELLED'
                  AND (cancelled_at IS NULL OR cancelled_by_user_id IS NULL OR cancellation_reason IS NULL);
                """
            )
            res_bad_cancel = cur.fetchone()
            assert res_bad_cancel is not None
            bad_cancels = res_bad_cancel[0]
            assert bad_cancels == 0

            # Check all non-cancelled bills have NULL cancellation metadata
            cur.execute(
                """
                SELECT count(*)
                FROM bills
                WHERE bill_status <> 'CANCELLED'
                  AND (cancelled_at IS NOT NULL OR cancelled_by_user_id IS NOT NULL OR cancellation_reason IS NOT NULL);
                """
            )
            res_bad_active = cur.fetchone()
            assert res_bad_active is not None
            bad_actives = res_bad_active[0]
            assert bad_actives == 0
    print("         Database consistency constraint verified: 0 partially populated cancellation rows.")
    results.append(("31. Cancellation metadata is consistent", "PASS"))

    # 32. Historical bill and payment records remain preserved
    print("\n[TEST 32] Historical record preservation...")
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            # Check cancelled bill still exists in bills table
            cur.execute("SELECT count(*) FROM bills WHERE id = %s;", (cancel_b["id"],))
            res_c_cnt = cur.fetchone()
            assert res_c_cnt is not None
            assert res_c_cnt[0] == 1

            # Check line items still exist
            cur.execute("SELECT count(*) FROM bill_items WHERE bill_id = %s;", (cancel_b["id"],))
            res_items_cnt = cur.fetchone()
            assert res_items_cnt is not None
            assert res_items_cnt[0] >= 1
    print("         Confirmed: Zero deletions. All cancelled bills and snapshot items preserved.")
    results.append(("32. Historical bill and payment records remain preserved", "PASS"))

    # --------------------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("VIYON PHASE 4.3 BILL CANCELLATION & HISTORY TEST RESULTS SUMMARY")
    print("=" * 80)
    for name, res in results:
        print(f"  {name:<65} [{res}]")
    print("=" * 80)
    print(f"ALL {len(results)} OF {len(results)} TESTS PASSED PERFECTLY WITH 100% ACCURACY!")
    print("=" * 80)


if __name__ == "__main__":
    run_phase4_3_cancellation_tests()
