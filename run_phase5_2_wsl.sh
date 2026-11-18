#!/usr/bin/env bash
set -e

cd "/mnt/d/viyon billing"
source /opt/viyon_venv/bin/activate

export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5433/viyon_test_fresh"
export ENVIRONMENT="test"
export SECRET_KEY="test-secret-key-phase5-2-secure-random-at-least-32-chars"

echo "=== RUNNING PHASE 5.2 STAFF MANAGEMENT SUITE IN ISOLATED ENVIRONMENT ==="
python -u tests/test_staff_management_phase5_2.py
