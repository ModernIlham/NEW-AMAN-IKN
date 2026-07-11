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


# ---------------------------------------------------------------------------
# Marking otomatis: semua test di luar tests/unit/ adalah test live-server
# (butuh backend jalan + MongoDB) → beri marker `integration` supaya `pytest`
# default (addopts -m "not integration" di pytest.ini) hanya menjalankan
# test bebas-infra. Jalankan test integrasi dengan: pytest -m integration
# ---------------------------------------------------------------------------
import pathlib

import pytest

_TESTS_DIR = pathlib.Path(__file__).resolve().parent


def _integration_requested(config) -> bool:
    markexpr = config.getoption("-m", default="") or ""
    return "integration" in markexpr and "not integration" not in markexpr


def pytest_ignore_collect(collection_path, config):
    """Jangan import modul test live-server pada run default: beberapa modul
    lama raise saat import bila env (REACT_APP_BACKEND_URL dll.) tidak diset,
    yang menggagalkan collection sebelum marker sempat menyeleksi."""
    path = pathlib.Path(str(collection_path)).resolve()
    try:
        rel = path.relative_to(_TESTS_DIR)
    except ValueError:
        return None
    if not rel.parts or rel.parts[0] == "unit" or path.suffix != ".py":
        return None
    if _integration_requested(config):
        return None
    return True


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = pathlib.Path(str(item.fspath)).resolve()
        try:
            rel = path.relative_to(_TESTS_DIR)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] == "unit":
            continue
        item.add_marker(pytest.mark.integration)
