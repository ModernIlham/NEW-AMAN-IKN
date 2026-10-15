"""Konfigurasi test unit (bebas infra).

Modul backend bisa di-import tanpa MongoDB/JWT_SECRET nyata: koneksi motor
lazy (tidak konek saat import), jadi cukup mengisi env var dummy SEBELUM
modul backend ter-import. Test di direktori ini TIDAK boleh menyentuh
database atau jaringan.
"""
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "aman_unit_test")
os.environ.setdefault("JWT_SECRET", "unit-test-secret")


@pytest.fixture
def mongomock_update_sort_compat(monkeypatch):
    """Bridge PyMongo's optional sort=None to mongomock's older bulk API.

    Keep the original builder responsible for filters, update operators and
    upserts. A real sort remains unsupported and must fail visibly rather
    than silently change which document the test updates.
    """
    from mongomock.collection import BulkOperationBuilder

    original = BulkOperationBuilder.add_update

    def add_update(self, *args, sort=None, **kwargs):
        if sort is not None:
            raise NotImplementedError("mongomock bulk update does not support sort")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(BulkOperationBuilder, "add_update", add_update)


@pytest.fixture
def mongo_not_regex(monkeypatch):
    """MongoDB menerima $not: {$regex, $options}; mongomock belum mendukungnya.

    Ubah representasi itu saja menjadi re.Pattern yang didukung Mongo tiruan.
    Filter tetap dijalankan, termasuk pengecualian dummy (bukan dilewati).
    """
    import re
    from mongomock.filtering import _Filterer

    original = _Filterer._not_op

    def not_op(self, document, key, condition):
        if isinstance(condition, dict) and set(condition) == {"$regex", "$options"} and condition["$options"] == "i":
            condition = re.compile(condition["$regex"], re.I)
        return original(self, document, key, condition)

    monkeypatch.setattr(_Filterer, "_not_op", not_op)
