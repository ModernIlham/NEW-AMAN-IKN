"""Konfigurasi test unit (bebas infra).

Modul backend bisa di-import tanpa MongoDB/JWT_SECRET nyata: koneksi motor
lazy (tidak konek saat import), jadi cukup mengisi env var dummy SEBELUM
modul backend ter-import. Test di direktori ini TIDAK boleh menyentuh
database atau jaringan.
"""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "aman_unit_test")
os.environ.setdefault("JWT_SECRET", "unit-test-secret")
