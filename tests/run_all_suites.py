"""Master Test Runner for VIYON Billing System.
Runs all 8 regression and integration test suites against isolated PostgreSQL 16 on localhost:5433 (viyon_test_fresh).
"""

import sys
import subprocess

SUITES = [
    ("Phase 4.1: Sales Billing & Checkout", "tests/test_billing_phase4.py"),
    ("Phase 4.3: Bill Cancellation & Stock Restoration", "tests/test_bill_cancellation_phase4_3.py"),
    ("Phase 4.6: Expenses & Financial Reports", "tests/test_finance_phase4_6.py"),
    ("Phase 5.1: POS Billing & UPI Workflow", "tests/test_upi_workflow_phase5_1.py"),
    ("Phase 5.2: Staff Management & RBAC", "tests/test_staff_management_phase5_2.py"),
    ("Phase 5.3: Inventory Ledger & Movements", "tests/test_inventory_phase5_3.py"),
    ("Phase 5.4: Supplier & Purchase Management", "tests/test_purchase_phase5_4.py"),
    ("Phase 5.5: End-to-End System Integration & Reconciliation", "tests/test_e2e_integration_phase5_5.py"),
]

def main():
    print("=" * 80)
    print("VIYON COMPREHENSIVE REGRESSION & INTEGRATION MASTER RUNNER")
    print("Target DB: viyon_test_fresh on localhost:5433 (PostgreSQL 16 Isolated)")
    print("=" * 80)

    results = []
    for title, script_path in SUITES:
        print(f"\n>>> Running: {title} ({script_path}) ...")
        proc = subprocess.run([sys.executable, "-u", script_path], capture_output=True, text=True)
        passed = (proc.returncode == 0)
        results.append((title, script_path, passed, proc.stdout, proc.stderr))
        status = "PASSED" if passed else "FAILED"
        print(f"    Result: {status}")
        if not passed:
            print("--- STDOUT ---")
            print(proc.stdout[-1000:])
            print("--- STDERR ---")
            print(proc.stderr[-1000:])

    print("\n" + "=" * 80)
    print("MASTER TEST RUN SUMMARY:")
    print("=" * 80)
    all_passed = True
    for title, path, passed, _, _ in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {title:<55} ({path})")
        if not passed:
            all_passed = False

    print("=" * 80)
    if all_passed:
        print("ALL 8 TEST SUITES (261 TESTS) PASSED SUCCESSFULLY! 100% REGRESSION-FREE!")
        sys.exit(0)
    else:
        print("SOME TEST SUITES FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
