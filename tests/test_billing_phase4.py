"""Comprehensive integration test suite for Phase 4.1: Sales Bill Creation & Checkout.

Target Database: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh)
Guarantees 100% isolation: Neon production database is NEVER connected to or modified.

Covers all 23 required test scenarios:
1. Successful bill with one simple product.
2. Successful bill with multiple products.
3. Successful bill with a product variant.
4. Correct backend price calculation.
5. Frontend-supplied price cannot override database price.
6. Invalid product rejection (404).
7. Invalid variant rejection (400/404).
8. Variant belonging to another product rejection (400).
9. Archived product rejection (409).
10. Inactive product rejection (409).
11. Insufficient stock rejection (409).
12. Negative and zero quantity rejection (422).
13. Discount validation (negative rejection & discount exceeding subtotal).
14. Correct SKU and product snapshots in bill_items.
15. Stock deduction after successful checkout.
16. Stock movement SALE entry creation.
17. Full rollback if any item fails.
18. Concurrent checkout cannot oversell stock.
19. Unique bill numbers under concurrent requests.
20. Authentication and staff/owner permissions.
21. Walk-in customer bill creation.
22. Invalid customer rejection (404).
23. Bill listing pagination and filtering.
"""

import sys
import threading
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
from app.models.category import Category, Subcategory
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.product import Product, ProductVariant
from app.models.store_settings import StoreSettings
from app.models.user import User

TEST_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/viyon_test_fresh"

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
    """Wipe test data in isolated test database."""
    raw_url = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(raw_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                TRUNCATE TABLE stock_movements CASCADE;
                TRUNCATE TABLE bill_items CASCADE;
                TRUNCATE TABLE bills CASCADE;
                TRUNCATE TABLE inventory CASCADE;
                TRUNCATE TABLE product_variants CASCADE;
                TRUNCATE TABLE products CASCADE;
                TRUNCATE TABLE product_identifiers CASCADE;
                TRUNCATE TABLE subcategories CASCADE;
                TRUNCATE TABLE categories CASCADE;
                TRUNCATE TABLE customers CASCADE;
                TRUNCATE TABLE store_settings CASCADE;
                TRUNCATE TABLE users CASCADE;
            """)
        conn.commit()


def setup_test_environment():
    """Seed prerequisite store settings, users, catalog items, and inventory."""
    clean_test_tables()
    db = TestingSessionLocal()
    try:
        # 1. Store settings
        settings = StoreSettings(
            id=uuid4(),
            store_name="VIYON",
            tax_enabled=False,
            default_tax_rate=Decimal("0.00"),
            is_active_config=True,
        )
        db.add(settings)

        # 2. Users (Owner & Staff)
        owner = User(
            id=uuid4(),
            full_name="Viyon Store Owner",
            email="owner@viyon.store",
            password_hash=get_password_hash("OwnerSecurePass123!"),
            role="OWNER",
            is_active=True,
        )
        staff = User(
            id=uuid4(),
            full_name="Billing Cashier Staff",
            email="staff@viyon.store",
            password_hash=get_password_hash("StaffSecurePass123!"),
            role="STAFF",
            is_active=True,
        )
        db.add_all([owner, staff])

        # 3. Customer
        customer = Customer(
            id=uuid4(),
            customer_name="Rajesh Kumar",
            phone="9876543210",
            email="rajesh@example.com",
            address="Sathyamangalam, Tamil Nadu",
        )
        db.add(customer)

        # 4. Category & Subcategory
        cat = Category(
            id=uuid4(),
            name="Mens Wear",
            is_active=True,
        )
        db.add(cat)
        db.flush()

        subcat = Subcategory(
            id=uuid4(),
            category_id=cat.id,
            name="Formal Shirts",
            is_active=True,
        )
        db.add(subcat)
        db.flush()

        # 5. Simple Product A (Active, in stock: 20, price: 999.00)
        prod_a = Product(
            id=uuid4(),
            product_name="White Cotton Shirt",
            product_code="VY-WCS-01",
            category_id=cat.id,
            subcategory_id=subcat.id,
            product_type="SIMPLE",
            base_price=Decimal("999.00"),
            sku="SKU-WCS-01",
            barcode="BAR-WCS-01",
            is_active=True,
            is_archived=False,
        )
        db.add(prod_a)
        db.flush()
        inv_a = Inventory(
            product_id=prod_a.id,
            variant_id=None,
            quantity=20,
            low_stock_threshold=5,
        )
        db.add(inv_a)

        # 6. Simple Product B (Active, in stock: 10, price: 499.00)
        prod_b = Product(
            id=uuid4(),
            product_name="Casual Polo T-Shirt",
            product_code="VY-CPT-02",
            category_id=cat.id,
            subcategory_id=subcat.id,
            product_type="SIMPLE",
            base_price=Decimal("499.00"),
            sku="SKU-CPT-02",
            is_active=True,
            is_archived=False,
        )
        db.add(prod_b)
        db.flush()
        inv_b = Inventory(
            product_id=prod_b.id,
            variant_id=None,
            quantity=10,
            low_stock_threshold=2,
        )
        db.add(inv_b)

        # 7. Variant Product C (Jeans, price: 1499.00)
        prod_c = Product(
            id=uuid4(),
            product_name="Slim Fit Jeans",
            product_code="VY-SFJ-03",
            category_id=cat.id,
            subcategory_id=subcat.id,
            product_type="VARIANT",
            base_price=Decimal("1499.00"),
            sku=None,
            barcode=None,
            is_active=True,
            is_archived=False,
        )
        db.add(prod_c)
        db.flush()

        # Variant C1: Size 32 Navy (Stock: 15, base price 1499.00)
        var_c1 = ProductVariant(
            id=uuid4(),
            product_id=prod_c.id,
            size="32",
            color="NAVY",
            sku="JEANS-NVY-32",
            is_active=True,
        )
        db.add(var_c1)
        db.flush()
        inv_c1 = Inventory(
            product_id=prod_c.id,
            variant_id=var_c1.id,
            quantity=15,
            low_stock_threshold=3,
        )
        db.add(inv_c1)

        # Variant C2: Size 34 Black (Stock: 5, price override 1699.00)
        var_c2 = ProductVariant(
            id=uuid4(),
            product_id=prod_c.id,
            size="34",
            color="BLACK",
            sku="JEANS-BLK-34",
            price_override=Decimal("1699.00"),
            is_active=True,
        )
        db.add(var_c2)
        db.flush()
        inv_c2 = Inventory(
            product_id=prod_c.id,
            variant_id=var_c2.id,
            quantity=5,
            low_stock_threshold=2,
        )
        db.add(inv_c2)

        # Variant C3: Inactive Variant (Stock: 10)
        var_c3 = ProductVariant(
            id=uuid4(),
            product_id=prod_c.id,
            size="36",
            color="GREY",
            sku="JEANS-GRY-36",
            is_active=False,
        )
        db.add(var_c3)
        db.flush()
        inv_c3 = Inventory(
            product_id=prod_c.id,
            variant_id=var_c3.id,
            quantity=10,
            low_stock_threshold=2,
        )
        db.add(inv_c3)

        # 8. Inactive Simple Product D (Stock: 5)
        prod_d = Product(
            id=uuid4(),
            product_name="Inactive Summer Shorts",
            product_code="VY-ISS-04",
            category_id=cat.id,
            product_type="SIMPLE",
            base_price=Decimal("399.00"),
            sku="SKU-ISS-04",
            is_active=False,
            is_archived=False,
        )
        db.add(prod_d)
        db.flush()
        inv_d = Inventory(
            product_id=prod_d.id,
            variant_id=None,
            quantity=5,
            low_stock_threshold=1,
        )
        db.add(inv_d)

        # 9. Archived Simple Product E (Stock: 5)
        prod_e = Product(
            id=uuid4(),
            product_name="Archived Winter Jacket",
            product_code="VY-AWJ-05",
            category_id=cat.id,
            product_type="SIMPLE",
            base_price=Decimal("2999.00"),
            sku="SKU-AWJ-05",
            is_active=False,
            is_archived=True,
        )
        db.add(prod_e)
        db.flush()
        inv_e = Inventory(
            product_id=prod_e.id,
            variant_id=None,
            quantity=5,
            low_stock_threshold=1,
        )
        db.add(inv_e)

        # 10. Limited Stock Product F (Stock: exactly 2)
        prod_f = Product(
            id=uuid4(),
            product_name="Limited Edition Blazer",
            product_code="VY-LEB-06",
            category_id=cat.id,
            product_type="SIMPLE",
            base_price=Decimal("4999.00"),
            sku="SKU-LEB-06",
            is_active=True,
            is_archived=False,
        )
        db.add(prod_f)
        db.flush()
        inv_f = Inventory(
            product_id=prod_f.id,
            variant_id=None,
            quantity=2,
            low_stock_threshold=1,
        )
        db.add(inv_f)

        db.commit()

        owner_token = create_access_token(subject=str(owner.id), role="OWNER")
        staff_token = create_access_token(subject=str(staff.id), role="STAFF")

        return {
            "owner_auth": {"Authorization": f"Bearer {owner_token}"},
            "staff_auth": {"Authorization": f"Bearer {staff_token}"},
            "customer_id": str(customer.id),
            "prod_a_id": str(prod_a.id),
            "prod_b_id": str(prod_b.id),
            "prod_c_id": str(prod_c.id),
            "var_c1_id": str(var_c1.id),
            "var_c2_id": str(var_c2.id),
            "var_c3_id": str(var_c3.id),
            "prod_d_id": str(prod_d.id),
            "prod_e_id": str(prod_e.id),
            "prod_f_id": str(prod_f.id),
        }
    finally:
        db.close()


def run_phase4_billing_tests():
    print("=" * 80)
    print("VIYON PHASE 4.1: SALES BILLING & CHECKOUT TEST SUITE (23 SCENARIOS)")
    print("Target DB: Isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh)")
    print("=" * 80)

    env = setup_test_environment()
    owner_auth = env["owner_auth"]
    staff_auth = env["staff_auth"]
    cust_id = env["customer_id"]
    prod_a = env["prod_a_id"]
    prod_b = env["prod_b_id"]
    prod_c = env["prod_c_id"]
    var_c1 = env["var_c1_id"]
    var_c2 = env["var_c2_id"]
    var_c3 = env["var_c3_id"]
    prod_d = env["prod_d_id"]
    prod_e = env["prod_e_id"]
    prod_f = env["prod_f_id"]

    results = []

    # --------------------------------------------------------------------------
    # Test 1: Successful bill with one simple product
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Successful bill with one simple product...")
    payload1 = {
        "customer_id": cust_id,
        "items": [{"product_id": prod_a, "variant_id": None, "quantity": 2}],
        "discount_amount": 0,
        "notes": "First in-store test purchase",
    }
    r1 = client.post("/api/v1/bills", json=payload1, headers=staff_auth)
    assert r1.status_code == status.HTTP_201_CREATED, r1.text
    b1 = r1.json()
    assert b1["subtotal"] == "1998.00"  # 999.00 * 2
    assert b1["total_amount"] == "1998.00"
    assert b1["payment_status"] == "PENDING"
    assert b1["bill_status"] == "COMPLETED"
    assert len(b1["items"]) == 1
    assert b1["items"][0]["quantity"] == 2
    assert b1["items"][0]["unit_price"] == "999.00"
    assert b1["customer_name"] == "Rajesh Kumar"
    print(f"         Bill created: {b1['bill_number']} | Total: Rs. {b1['total_amount']}")
    results.append(("1. Successful bill with one simple product", "PASS"))

    # --------------------------------------------------------------------------
    # Test 2: Successful bill with multiple products
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Successful bill with multiple products...")
    payload2 = {
        "customer_id": None,  # Walk-in
        "items": [
            {"product_id": prod_a, "variant_id": None, "quantity": 1},
            {"product_id": prod_b, "variant_id": None, "quantity": 2},
        ],
        "discount_amount": 0,
    }
    r2 = client.post("/api/v1/bills", json=payload2, headers=staff_auth)
    assert r2.status_code == status.HTTP_201_CREATED, r2.text
    b2 = r2.json()
    # 999.00 + (499.00 * 2) = 1997.00
    assert b2["subtotal"] == "1997.00"
    assert b2["total_amount"] == "1997.00"
    assert len(b2["items"]) == 2
    print(f"         Multi-item bill created: {b2['bill_number']} | Total: Rs. {b2['total_amount']}")
    results.append(("2. Successful bill with multiple products", "PASS"))

    # --------------------------------------------------------------------------
    # Test 3: Successful bill with a product variant
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Successful bill with product variants...")
    payload3 = {
        "customer_id": cust_id,
        "items": [
            {"product_id": prod_c, "variant_id": var_c1, "quantity": 1},  # 1499.00
            {"product_id": prod_c, "variant_id": var_c2, "quantity": 1},  # 1699.00 price override
        ],
    }
    r3 = client.post("/api/v1/bills", json=payload3, headers=staff_auth)
    assert r3.status_code == status.HTTP_201_CREATED, r3.text
    b3 = r3.json()
    # 1499.00 + 1699.00 = 3198.00
    assert b3["subtotal"] == "3198.00"
    assert b3["total_amount"] == "3198.00"
    skus = {item["sku_snapshot"]: item for item in b3["items"]}
    assert "JEANS-NVY-32" in skus
    assert "JEANS-BLK-34" in skus
    assert skus["JEANS-BLK-34"]["unit_price"] == "1699.00"
    print(f"         Variant bill created: {b3['bill_number']} | Total: Rs. {b3['total_amount']}")
    results.append(("3. Successful bill with a product variant", "PASS"))

    # --------------------------------------------------------------------------
    # Test 4: Correct backend price calculation with discount
    # --------------------------------------------------------------------------
    print("\n[TEST 4] Backend price calculation with discount...")
    payload4 = {
        "customer_id": None,
        "items": [{"product_id": prod_a, "variant_id": None, "quantity": 2, "discount_amount": 50}],
        "discount_amount": 100,  # Additional 100 off bill
    }
    r4 = client.post("/api/v1/bills", json=payload4, headers=staff_auth)
    assert r4.status_code == status.HTTP_201_CREATED, r4.text
    b4 = r4.json()
    # Gross: 999 * 2 = 1998.00
    # Total discount: 50 (item) + 100 (bill) = 150.00
    # Final: 1998 - 150 = 1848.00
    assert b4["subtotal"] == "1998.00"
    assert b4["discount_amount"] == "150.00"
    assert b4["total_amount"] == "1848.00"
    assert b4["balance_amount"] == "1848.00"
    print(f"         Calculations verified: Subtotal={b4['subtotal']}, Discount={b4['discount_amount']}, Final={b4['total_amount']}")
    results.append(("4. Correct backend price calculation", "PASS"))

    # --------------------------------------------------------------------------
    # Test 5: Frontend-supplied price cannot override database price
    # --------------------------------------------------------------------------
    print("\n[TEST 5] Frontend cannot tamper with selling prices...")
    # Attacker tries to inject "unit_price": 1.00
    tamper_payload = {
        "customer_id": None,
        "items": [
            {"product_id": prod_a, "variant_id": None, "quantity": 1, "unit_price": 1.00}
        ],
    }
    r5 = client.post("/api/v1/bills", json=tamper_payload, headers=staff_auth)
    assert r5.status_code == status.HTTP_201_CREATED
    b5 = r5.json()
    # Must use DB price 999.00, NOT the injected 1.00!
    assert b5["items"][0]["unit_price"] == "999.00"
    assert b5["total_amount"] == "999.00"
    print("         Confirmed: Database prices are authoritative. Injected price ignored.")
    results.append(("5. Frontend price tampering prevented", "PASS"))

    # --------------------------------------------------------------------------
    # Test 6: Invalid product rejection (404)
    # --------------------------------------------------------------------------
    print("\n[TEST 6] Non-existent product rejection (404)...")
    fake_prod = str(uuid4())
    r6 = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": fake_prod, "quantity": 1}]},
        headers=staff_auth,
    )
    assert r6.status_code == status.HTTP_404_NOT_FOUND
    print(f"         Rejected non-existent product: 404 | {r6.json()['detail']}")
    results.append(("6. Invalid product rejection (404)", "PASS"))

    # --------------------------------------------------------------------------
    # Test 7: Invalid variant rejection (404/400)
    # --------------------------------------------------------------------------
    print("\n[TEST 7] Non-existent variant rejection (400/404)...")
    fake_var = str(uuid4())
    r7 = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_c, "variant_id": fake_var, "quantity": 1}]},
        headers=staff_auth,
    )
    assert r7.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND)
    print(f"         Rejected non-existent variant: {r7.status_code} | {r7.json()['detail']}")
    results.append(("7. Invalid variant rejection", "PASS"))

    # --------------------------------------------------------------------------
    # Test 8: Variant belonging to another product rejection
    # --------------------------------------------------------------------------
    print("\n[TEST 8] Variant mismatch with parent product...")
    # Passing variant var_c1 with simple product prod_a!
    r8 = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_a, "variant_id": var_c1, "quantity": 1}]},
        headers=staff_auth,
    )
    assert r8.status_code == status.HTTP_400_BAD_REQUEST
    assert "SIMPLE product; variant_id must be null" in r8.json()["detail"]
    print(f"         Rejected variant on simple product: 400 | {r8.json()['detail']}")
    results.append(("8. Variant mismatch rejection", "PASS"))

    # --------------------------------------------------------------------------
    # Test 9: Archived product rejection (409)
    # --------------------------------------------------------------------------
    print("\n[TEST 9] Archived product checkout rejection (409)...")
    r9 = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_e, "quantity": 1}]},
        headers=staff_auth,
    )
    assert r9.status_code == status.HTTP_409_CONFLICT
    assert "archived" in r9.json()["detail"]
    print(f"         Rejected archived product: 409 | {r9.json()['detail']}")
    results.append(("9. Archived product rejection", "PASS"))

    # --------------------------------------------------------------------------
    # Test 10: Inactive product & variant rejection (409)
    # --------------------------------------------------------------------------
    print("\n[TEST 10] Inactive product & inactive variant rejection (409)...")
    # Inactive product prod_d
    r10_a = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_d, "quantity": 1}]},
        headers=staff_auth,
    )
    assert r10_a.status_code == status.HTTP_409_CONFLICT
    assert "inactive" in r10_a.json()["detail"]

    # Inactive variant var_c3
    r10_b = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_c, "variant_id": var_c3, "quantity": 1}]},
        headers=staff_auth,
    )
    assert r10_b.status_code == status.HTTP_409_CONFLICT
    assert "inactive" in r10_b.json()["detail"]
    print("         Both inactive product and inactive variant correctly rejected with 409.")
    results.append(("10. Inactive product/variant rejection", "PASS"))

    # --------------------------------------------------------------------------
    # Test 11: Insufficient stock rejection (409)
    # --------------------------------------------------------------------------
    print("\n[TEST 11] Insufficient stock rejection (409)...")
    # Product F has only 2 units available
    r11 = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_f, "quantity": 10}]},
        headers=staff_auth,
    )
    assert r11.status_code == status.HTTP_409_CONFLICT
    assert "Insufficient stock" in r11.json()["detail"]
    print(f"         Insufficient stock rejected: 409 | {r11.json()['detail']}")
    results.append(("11. Insufficient stock rejection", "PASS"))

    # --------------------------------------------------------------------------
    # Test 12: Negative and zero quantity rejection (422)
    # --------------------------------------------------------------------------
    print("\n[TEST 12] Negative and zero quantity validation (422)...")
    r12_zero = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_a, "quantity": 0}]},
        headers=staff_auth,
    )
    assert r12_zero.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    r12_neg = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_a, "quantity": -5}]},
        headers=staff_auth,
    )
    assert r12_neg.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    print("         Both zero and negative quantity requests rejected with 422.")
    results.append(("12. Negative/zero quantity rejection", "PASS"))

    # --------------------------------------------------------------------------
    # Test 13: Discount validation
    # --------------------------------------------------------------------------
    print("\n[TEST 13] Discount validation (Negative discount & excessive discount)...")
    # Negative discount
    r13_neg = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_a, "quantity": 1}], "discount_amount": -50},
        headers=staff_auth,
    )
    assert r13_neg.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Discount exceeding subtotal (subtotal is 999.00, discount requested 5000.00)
    r13_excess = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_a, "quantity": 1}], "discount_amount": 5000.00},
        headers=staff_auth,
    )
    assert r13_excess.status_code == status.HTTP_400_BAD_REQUEST
    assert "exceed" in r13_excess.json()["detail"].lower()
    print("         Discount constraints verified: negative blocked (422), excess blocked (400).")
    results.append(("13. Discount validation", "PASS"))

    # --------------------------------------------------------------------------
    # Test 14: Correct SKU and product snapshots in bill_items
    # --------------------------------------------------------------------------
    print("\n[TEST 14] Frozen snapshots in bill_items...")
    r14 = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_c, "variant_id": var_c1, "quantity": 1}]},
        headers=staff_auth,
    )
    assert r14.status_code == status.HTTP_201_CREATED
    b14_item = r14.json()["items"][0]
    assert b14_item["product_name_snapshot"] == "Slim Fit Jeans"
    assert b14_item["sku_snapshot"] == "JEANS-NVY-32"
    assert b14_item["size_snapshot"] == "32"
    assert b14_item["color_snapshot"] == "NAVY"
    print("         Confirmed: Snapshot fields match purchased product & variant.")
    results.append(("14. Correct SKU and product snapshots", "PASS"))

    # --------------------------------------------------------------------------
    # Test 15: Stock deduction after successful checkout
    # --------------------------------------------------------------------------
    print("\n[TEST 15] Inventory stock deduction verification...")
    # Product F has 2 units in stock. Buy 1 unit.
    r15 = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_f, "quantity": 1}]},
        headers=staff_auth,
    )
    assert r15.status_code == status.HTTP_201_CREATED
    # Check remaining inventory in DB
    with psycopg.connect(TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s;", (prod_f,))
            rf = cur.fetchone()
            assert rf is not None
            remaining_f = rf[0]
    assert remaining_f == 1  # 2 - 1 = 1
    print(f"         Stock decremented correctly: 2 -> {remaining_f}")
    results.append(("15. Stock deduction verified", "PASS"))

    # --------------------------------------------------------------------------
    # Test 16: Stock movement SALE entry creation
    # --------------------------------------------------------------------------
    print("\n[TEST 16] Stock movement SALE ledger verification...")
    with psycopg.connect(TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT movement_type, quantity_change, reference_type FROM stock_movements WHERE product_id = %s AND movement_type = 'SALE';",
                (prod_f,),
            )
            rm = cur.fetchone()
            assert rm is not None
            m_type, m_qty, m_ref = rm
    assert m_type == "SALE"
    assert m_qty == -1
    assert m_ref == "BILL"
    print(f"         Audit movement confirmed: type={m_type}, change={m_qty}, ref={m_ref}")
    results.append(("16. Stock movement SALE entry creation", "PASS"))

    # --------------------------------------------------------------------------
    # Test 17: Full rollback if any item fails
    # --------------------------------------------------------------------------
    print("\n[TEST 17] Atomic rollback if any item fails in cart...")
    # Product A has stock, Product F has only 1 left. Cart asks for 1 A and 10 F.
    # Should fail due to F, and Product A must NOT be decremented!
    with psycopg.connect(TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s;", (prod_a,))
            ra = cur.fetchone()
            assert ra is not None
            qty_a_before = ra[0]
            cur.execute("SELECT count(*) FROM bills;")
            rb = cur.fetchone()
            assert rb is not None
            bills_count_before = rb[0]

    r17 = client.post(
        "/api/v1/bills",
        json={
            "items": [
                {"product_id": prod_a, "quantity": 1},
                {"product_id": prod_f, "quantity": 10},  # Fails!
            ]
        },
        headers=staff_auth,
    )
    assert r17.status_code == status.HTTP_409_CONFLICT

    with psycopg.connect(TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s;", (prod_a,))
            ra2 = cur.fetchone()
            assert ra2 is not None
            qty_a_after = ra2[0]
            cur.execute("SELECT count(*) FROM bills;")
            rb2 = cur.fetchone()
            assert rb2 is not None
            bills_count_after = rb2[0]

    assert qty_a_before == qty_a_after
    assert bills_count_before == bills_count_after
    print("         Atomic rollback verified: Product A stock untouched, 0 orphan bills.")
    results.append(("17. Full rollback on failure", "PASS"))

    # --------------------------------------------------------------------------
    # Test 18: Concurrent checkout cannot oversell stock
    # --------------------------------------------------------------------------
    print("\n[TEST 18] Concurrency test: Prevent overselling stock under race conditions...")
    # Product F has exactly 1 unit left in inventory!
    # Run 5 concurrent threads all trying to buy 1 unit of Product F.
    # Exactly ONE must succeed (201) and FOUR must fail with 409 Insufficient stock!
    thread_results = []
    barrier = threading.Barrier(5)

    def checkout_worker():
        barrier.wait()
        r = client.post(
            "/api/v1/bills",
            json={"items": [{"product_id": prod_f, "quantity": 1}]},
            headers=staff_auth,
        )
        thread_results.append(r.status_code)

    threads = [threading.Thread(target=checkout_worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = thread_results.count(status.HTTP_201_CREATED)
    conflicts = thread_results.count(status.HTTP_409_CONFLICT)
    print(f"         5 Concurrent Requests: {successes} Succeeded, {conflicts} Rejected with 409")
    assert successes == 1
    assert conflicts == 4

    with psycopg.connect(TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s;", (prod_f,))
            rf_final = cur.fetchone()
            assert rf_final is not None
            final_f = rf_final[0]
    assert final_f == 0
    print("         Final stock is exactly 0. Zero overselling!")
    results.append(("18. Concurrent overselling prevention", "PASS"))

    # --------------------------------------------------------------------------
    # Test 19: Unique bill numbers under concurrent requests
    # --------------------------------------------------------------------------
    print("\n[TEST 19] Unique bill numbers under concurrent requests...")
    # Product A has plenty of stock. 5 threads buying simultaneously.
    bill_numbers = []
    barrier_bn = threading.Barrier(5)

    def bill_number_worker():
        barrier_bn.wait()
        r = client.post(
            "/api/v1/bills",
            json={"items": [{"product_id": prod_a, "quantity": 1}]},
            headers=staff_auth,
        )
        if r.status_code == 201:
            bill_numbers.append(r.json()["bill_number"])

    threads_bn = [threading.Thread(target=bill_number_worker) for _ in range(5)]
    for t in threads_bn:
        t.start()
    for t in threads_bn:
        t.join()

    assert len(bill_numbers) == 5
    assert len(set(bill_numbers)) == 5
    print(f"         Generated numbers: {bill_numbers}")
    results.append(("19. Unique concurrent bill numbers", "PASS"))

    # --------------------------------------------------------------------------
    # Test 20: Authentication and staff/owner permissions
    # --------------------------------------------------------------------------
    print("\n[TEST 20] Authentication and staff/owner permissions...")
    # Unauthenticated checkout -> 401
    r_unauth = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_a, "quantity": 1}]},
    )
    assert r_unauth.status_code == status.HTTP_401_UNAUTHORIZED

    # Owner checkout -> 201
    r_owner = client.post(
        "/api/v1/bills",
        json={"items": [{"product_id": prod_a, "quantity": 1}]},
        headers=owner_auth,
    )
    assert r_owner.status_code == status.HTTP_201_CREATED
    print("         Verified: Unauthenticated blocked (401), Owner & Staff authorized (201).")
    results.append(("20. Authentication & RBAC permissions", "PASS"))

    # --------------------------------------------------------------------------
    # Test 21: Walk-in customer bill creation
    # --------------------------------------------------------------------------
    print("\n[TEST 21] Walk-in customer bill creation (customer_id = null)...")
    r21 = client.post(
        "/api/v1/bills",
        json={"customer_id": None, "items": [{"product_id": prod_a, "quantity": 1}]},
        headers=staff_auth,
    )
    assert r21.status_code == status.HTTP_201_CREATED
    b21 = r21.json()
    assert b21["customer_id"] is None
    assert b21["customer_name"] is None
    print("         Walk-in bill created successfully with null customer.")
    results.append(("21. Walk-in customer bill creation", "PASS"))

    # --------------------------------------------------------------------------
    # Test 22: Invalid customer rejection (404)
    # --------------------------------------------------------------------------
    print("\n[TEST 22] Invalid customer UUID rejection (404)...")
    fake_cust = str(uuid4())
    r22 = client.post(
        "/api/v1/bills",
        json={"customer_id": fake_cust, "items": [{"product_id": prod_a, "quantity": 1}]},
        headers=staff_auth,
    )
    assert r22.status_code == status.HTTP_404_NOT_FOUND
    assert "Customer" in r22.json()["detail"]
    print(f"         Rejected non-existent customer: 404 | {r22.json()['detail']}")
    results.append(("22. Invalid customer rejection (404)", "PASS"))

    # --------------------------------------------------------------------------
    # Test 23: Bill listing, search, and line item queries
    # --------------------------------------------------------------------------
    print("\n[TEST 23] Bill listing, pagination, search, and line items...")
    r23_list = client.get("/api/v1/bills?limit=10&offset=0", headers=staff_auth)
    assert r23_list.status_code == status.HTTP_200_OK
    bills_data = r23_list.json()
    assert bills_data["total"] >= 5
    assert len(bills_data["items"]) <= 10

    # Search by bill number
    sample_bn = bills_data["items"][0]["bill_number"]
    sample_id = bills_data["items"][0]["id"]
    r23_search = client.get(f"/api/v1/bills?search={sample_bn}", headers=staff_auth)
    assert r23_search.status_code == status.HTTP_200_OK
    assert r23_search.json()["total"] == 1
    assert r23_search.json()["items"][0]["bill_number"] == sample_bn

    # Get single bill
    r23_get = client.get(f"/api/v1/bills/{sample_id}", headers=staff_auth)
    assert r23_get.status_code == status.HTTP_200_OK
    assert r23_get.json()["id"] == sample_id

    # Get bill line items
    r23_items = client.get(f"/api/v1/bills/{sample_id}/items", headers=staff_auth)
    assert r23_items.status_code == status.HTTP_200_OK
    assert len(r23_items.json()) >= 1
    print("         Bill listing, search, get, and items endpoints verified.")
    results.append(("23. Bill listing, pagination and search", "PASS"))

    # Clean test tables
    clean_test_tables()

    # --------------------------------------------------------------------------
    # Final Results Table
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("VIYON PHASE 4.1 BILLING & CHECKOUT TEST RESULTS SUMMARY")
    print("=" * 80)
    for name, st in results:
        print(f"  {name:<65} [{st}]")
    print("=" * 80)
    print(f"ALL {len(results)} OF 23 TESTS PASSED PERFECTLY WITH 100% ACCURACY!")
    print("=" * 80)


if __name__ == "__main__":
    run_phase4_billing_tests()
