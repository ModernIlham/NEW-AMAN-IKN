"""Shared pytest configuration & fixtures for backend tests.

Centralizes test credentials so they are NOT hardcoded across 40+ test files.
Values default to the dev bootstrap admin; override in CI via environment:

    export TEST_ADMIN_USERNAME=admin
    export TEST_ADMIN_PASSWORD=admin123
    export TEST_BASE_URL=http://localhost:8001
"""
import os

# Centralised test credentials (read from env, fall back to dev defaults).
TEST_ADMIN_USERNAME = os.environ.get("TEST_ADMIN_USERNAME", "admin")
TEST_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")
TEST_BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8001")

# Backwards-compatibility aliases for older tests.
ADMIN_USERNAME = TEST_ADMIN_USERNAME
ADMIN_PASSWORD = TEST_ADMIN_PASSWORD
BASE_URL = TEST_BASE_URL


def get_admin_credentials() -> dict:
    """Return a dict suitable for POST /api/auth/login."""
    return {"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD}
