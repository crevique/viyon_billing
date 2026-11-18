"""Comprehensive test suite for Phase 2: Owner Setup, Authentication, JWT & RBAC.

Runs against an isolated in-memory test database to guarantee that the live
Neon PostgreSQL database is never polluted with test credentials or dummy data.
"""

import sys
from datetime import timedelta
from pathlib import Path
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
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.rate_limit import login_rate_limiter
from app.core.security import create_access_token
from app.core.token_blacklist import token_blacklist
from app.database.base import Base
from app.database.connection import get_db
from app.main import app as fastapi_app
import app.models  # Ensures all models loaded

# Setup isolated in-memory SQLite database
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Create only the users table in SQLite memory
Base.metadata.tables["users"].create(test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override dependency in FastAPI app
fastapi_app.dependency_overrides[get_db] = override_get_db
client = TestClient(fastapi_app)


def run_all_tests():
    print("=" * 75)
    print("VIYON BILLING SYSTEM - PHASE 2 AUTHENTICATION & RBAC TEST SUITE")
    print("=" * 75)
    test_results = []

    # Reset rate limiter & blacklist
    login_rate_limiter.reset_all()
    token_blacklist.clear()

    # --------------------------------------------------------------------------
    # Test 1: Owner setup when no owner exists
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Owner setup when no owner exists...")
    setup_payload = {
        "full_name": "Viyon Store Owner",
        "email": "owner@viyon.store",
        "password": "SecureOwnerPassword2026!",
    }
    r1 = client.post(
        "/api/v1/auth/setup-owner",
        json=setup_payload,
        headers={"X-Setup-Token": settings.OWNER_SETUP_TOKEN},
    )
    print(f"         Status: {r1.status_code}")
    print(f"         Body:   {r1.json()}")
    assert r1.status_code == status.HTTP_201_CREATED
    assert r1.json()["role"] == "OWNER"
    assert r1.json()["email"] == "owner@viyon.store"
    assert "password_hash" not in r1.json()
    test_results.append(("Test 1: Owner setup when no owner exists", "PASS"))

    # --------------------------------------------------------------------------
    # Test 2: Rejection of a second owner setup
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Rejection of a second owner setup...")
    r2 = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Second Rogue Owner",
            "email": "second@viyon.store",
            "password": "AnotherPassword123!",
        },
        headers={"X-Setup-Token": settings.OWNER_SETUP_TOKEN},
    )
    print(f"         Status: {r2.status_code}")
    print(f"         Body:   {r2.json()}")
    assert r2.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in r2.json()["detail"].lower()
    test_results.append(("Test 2: Rejection of second owner setup (409 Conflict)", "PASS"))

    # Also test rejection of missing/wrong setup token
    r2_bad_token = client.post(
        "/api/v1/auth/setup-owner",
        json=setup_payload,
        headers={"X-Setup-Token": "invalid-token-xyz"},
    )
    assert r2_bad_token.status_code == status.HTTP_403_FORBIDDEN

    # --------------------------------------------------------------------------
    # Test 3: Successful login (OAuth2 form and JSON)
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Successful login (JSON & OAuth2 Form)...")
    r3_json = client.post(
        "/api/v1/auth/login/json",
        json={"email": "owner@viyon.store", "password": "SecureOwnerPassword2026!"},
    )
    print(f"         JSON Login Status: {r3_json.status_code}")
    assert r3_json.status_code == status.HTTP_200_OK
    owner_token = r3_json.json()["access_token"]
    assert owner_token
    assert r3_json.json()["role"] == "OWNER"
    assert r3_json.json()["user"]["email"] == "owner@viyon.store"

    # Form login (Swagger UI compatibility)
    r3_form = client.post(
        "/api/v1/auth/login",
        data={"username": "owner@viyon.store", "password": "SecureOwnerPassword2026!"},
    )
    assert r3_form.status_code == status.HTTP_200_OK
    assert r3_form.json()["access_token"]
    test_results.append(("Test 3: Successful login (JWT token generated)", "PASS"))

    # --------------------------------------------------------------------------
    # Test 4: Incorrect password rejection (generic error)
    # --------------------------------------------------------------------------
    print("\n[TEST 4] Incorrect password rejection...")
    r4 = client.post(
        "/api/v1/auth/login/json",
        json={"email": "owner@viyon.store", "password": "WrongPassword123!"},
    )
    print(f"         Status: {r4.status_code} | Body: {r4.json()}")
    assert r4.status_code == status.HTTP_401_UNAUTHORIZED
    assert r4.json()["detail"] == "Incorrect email or password."

    # Test non-existent email gets identical generic error
    r4_unknown = client.post(
        "/api/v1/auth/login/json",
        json={"email": "unknown@viyon.store", "password": "WrongPassword123!"},
    )
    assert r4_unknown.status_code == status.HTTP_401_UNAUTHORIZED
    assert r4_unknown.json()["detail"] == "Incorrect email or password."
    test_results.append(("Test 4: Incorrect password & unknown user rejection (Generic 401)", "PASS"))

    # --------------------------------------------------------------------------
    # Test 5: Invalid JWT rejection
    # --------------------------------------------------------------------------
    print("\n[TEST 5] Invalid JWT rejection...")
    r5 = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer completely-fake-and-malformed-jwt-token"},
    )
    print(f"         Status: {r5.status_code} | Body: {r5.json()}")
    assert r5.status_code == status.HTTP_401_UNAUTHORIZED
    test_results.append(("Test 5: Invalid JWT rejection (401)", "PASS"))

    # --------------------------------------------------------------------------
    # Test 6: Expired JWT rejection
    # --------------------------------------------------------------------------
    print("\n[TEST 6] Expired JWT rejection...")
    owner_id = r1.json()["id"]
    expired_token = create_access_token(
        subject=owner_id,
        role="OWNER",
        expires_delta=timedelta(seconds=-60),  # expired 1 minute ago
    )
    r6 = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    print(f"         Status: {r6.status_code} | Body: {r6.json()}")
    assert r6.status_code == status.HTTP_401_UNAUTHORIZED
    test_results.append(("Test 6: Expired JWT rejection (401)", "PASS"))

    # --------------------------------------------------------------------------
    # Test 7: /auth/me with valid token
    # --------------------------------------------------------------------------
    print("\n[TEST 7] /auth/me with valid token...")
    r7 = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    print(f"         Status: {r7.status_code}")
    print(f"         Profile: {r7.json()}")
    assert r7.status_code == status.HTTP_200_OK
    assert r7.json()["email"] == "owner@viyon.store"
    assert r7.json()["role"] == "OWNER"
    test_results.append(("Test 7: /auth/me with valid Bearer token", "PASS"))

    # --------------------------------------------------------------------------
    # Test 8: /auth/me without token
    # --------------------------------------------------------------------------
    print("\n[TEST 8] /auth/me without token...")
    r8 = client.get("/api/v1/auth/me")
    print(f"         Status: {r8.status_code} | Body: {r8.json()}")
    assert r8.status_code == status.HTTP_401_UNAUTHORIZED
    test_results.append(("Test 8: /auth/me without token (401)", "PASS"))

    # --------------------------------------------------------------------------
    # Test 9: Owner-only authorization
    # --------------------------------------------------------------------------
    print("\n[TEST 9] Owner-only authorization on staff management...")
    # Owner creates staff account
    r9_staff_create = client.post(
        "/api/v1/users/staff",
        json={
            "full_name": "Ravi Cashier",
            "email": "ravi.staff@viyon.store",
            "password": "StaffPassword123!",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    print(f"         Owner create staff Status: {r9_staff_create.status_code}")
    assert r9_staff_create.status_code == status.HTTP_201_CREATED
    staff_user = r9_staff_create.json()
    assert staff_user["role"] == "STAFF"

    # Log in as Staff
    r_staff_login = client.post(
        "/api/v1/auth/login/json",
        json={"email": "ravi.staff@viyon.store", "password": "StaffPassword123!"},
    )
    assert r_staff_login.status_code == status.HTTP_200_OK
    staff_token = r_staff_login.json()["access_token"]

    # Staff attempts to access Owner-only endpoint (create staff)
    r9_forbidden = client.post(
        "/api/v1/users/staff",
        json={
            "full_name": "Unauthorized Staff",
            "email": "unauth@viyon.store",
            "password": "StaffPassword123!",
        },
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    print(f"         Staff accessing owner endpoint Status: {r9_forbidden.status_code}")
    assert r9_forbidden.status_code == status.HTTP_403_FORBIDDEN
    test_results.append(("Test 9: Owner-only authorization (Staff blocked with 403)", "PASS"))

    # --------------------------------------------------------------------------
    # Test 10: Staff authorization behavior (accessing staff-permitted routes)
    # --------------------------------------------------------------------------
    print("\n[TEST 10] Staff authorization behavior...")
    # Staff can access /auth/me
    r10_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r10_me.status_code == status.HTTP_200_OK
    assert r10_me.json()["role"] == "STAFF"
    assert r10_me.json()["email"] == "ravi.staff@viyon.store"

    # Staff can change own password
    r10_pwd = client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "StaffPassword123!",
            "new_password": "NewStaffPassword456!",
        },
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r10_pwd.status_code == status.HTTP_200_OK
    test_results.append(("Test 10: Staff authorization behavior on permitted routes", "PASS"))

    # --------------------------------------------------------------------------
    # Test 11: Password hashes never returned in API responses
    # --------------------------------------------------------------------------
    print("\n[TEST 11] Verifying password hashes are NEVER exposed in responses...")
    endpoints_to_check = [
        r1.json(),
        r3_json.json()["user"],
        r7.json(),
        r9_staff_create.json(),
        r10_me.json(),
    ]
    for resp_dict in endpoints_to_check:
        for forbidden_key in ["password", "password_hash", "hash", "salt"]:
            assert forbidden_key not in resp_dict, f"Security violation: {forbidden_key} found in response!"
    print("         Confirmed: Zero password hashes or secrets in any response object.")
    test_results.append(("Test 11: Password hashes never returned in API responses", "PASS"))

    # --------------------------------------------------------------------------
    # Test 12: Logout & Token Revocation
    # --------------------------------------------------------------------------
    print("\n[TEST 12] Logout and server-side token revocation...")
    # Logout with staff token
    r12_logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r12_logout.status_code == status.HTTP_200_OK
    assert r12_logout.json()["revoked"] is True

    # Attempting to use the revoked token now must be rejected with 401
    r12_use_revoked = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    print(f"         Using revoked token Status: {r12_use_revoked.status_code} | Body: {r12_use_revoked.json()}")
    assert r12_use_revoked.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in r12_use_revoked.json()["detail"].lower()
    test_results.append(("Test 12: Logout server-side token revocation", "PASS"))

    # --------------------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("PHASE 2 AUTHENTICATION & RBAC TEST RESULTS SUMMARY")
    print("=" * 75)
    for test_name, status_str in test_results:
        print(f"  {test_name:<65} [{status_str}]")
    print("=" * 75)
    print("ALL 12 TESTS PASSED PERFECTLY!\n")
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
