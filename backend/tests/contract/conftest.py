"""Fixture kontrak dengan Mongo/Redis nyata, selalu pada database sementara.

Jalankan hanya dengan -m integration dan AMAN_CONTRACT_MONGO_URL loopback.
Tidak memakai MONGO_URL/DB_NAME dari .env aplikasi atau akun produksi.
"""
import os
import secrets
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import httpx
import pytest
import pytest_asyncio


def local_url(raw, schemes):
    value = urlparse(raw)
    if value.scheme not in schemes or value.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Kontrak hanya menerima layanan loopback, bukan target produksi")
    return raw


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def contract():
    mongo = os.environ.get("AMAN_CONTRACT_MONGO_URL", "")
    if not mongo:
        pytest.fail("AMAN_CONTRACT_MONGO_URL wajib diset ke Mongo lokal terisolasi")
    local_url(mongo, {"mongodb"})
    redis = os.environ.get("AMAN_CONTRACT_REDIS_URL", "")
    if redis:
        local_url(redis, {"redis"})
    database = "aman_ci_" + uuid.uuid4().hex
    bootstrap = secrets.token_urlsafe(48)
    password = "Kontrak9-" + secrets.token_urlsafe(20)
    overrides = {
        "MONGO_URL": mongo, "DB_NAME": database,
        "JWT_SECRET": secrets.token_urlsafe(48), "ADMIN_BOOTSTRAP_TOKEN": bootstrap,
        "REDIS_URL": redis, "MEILI_URL": "", "MEILI_MASTER_KEY": "",
        "TINIFY_API_KEY": "", "RESEND_API_KEY": "",
    }
    before = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    # Fresh pytest process is required: importing runtime before applying the
    # isolated configuration would bind module-level collections to another DB.
    if "db" in sys.modules:
        pytest.fail("Suite kontrak harus berjalan dalam proses pytest tersendiri")
    from db import client, db, fs_bucket
    from server import app
    from indexes import create_indexes, kegagalan_indeks
    from auth_utils import create_token, hash_password
    import redis_utils
    try:
        await db.command("ping")
        assert db.name == database and database.startswith("aman_ci_")
        await create_indexes()
        assert not kegagalan_indeks(), kegagalan_indeks()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://contract") as http:
            seeded = await http.post("/api/auth/bootstrap", json={
                "username": "contract-root", "password": password, "name": "Kontrak pusat",
            }, headers={"X-Admin-Bootstrap-Token": bootstrap})
            assert seeded.status_code == 200, seeded.text
            headers = {"root": {"Authorization": "Bearer " + seeded.json()["access_token"]}}
            users = {}
            now = "2026-10-15T00:00:00+00:00"
            encoded = hash_password(password)
            for letter in ("a", "b"):
                user = {"id": "contract-" + letter, "username": "contract-" + letter,
                        "name": "Kontrak " + letter, "role": "admin", "is_active": True,
                        "password": encoded, "kode_satker": "99000" + letter,
                        "created_at": now}
                await db.users.insert_one(user)
                await db.satker.insert_one({"id": letter, "kode_satker": user["kode_satker"],
                                           "nama_satker": "Satker sintetis " + letter})
                await db.inventory_activities.insert_one({
                    "id": "contract-activity-" + letter, "kode_satker": user["kode_satker"],
                    "nama_kegiatan": "Kontrak " + letter, "status_pengesahan": "draft",
                    "created_at": now,
                })
                users[letter] = user
                headers[letter] = {"Authorization": "Bearer " + create_token(user["id"], user["username"])}
            yield SimpleNamespace(db=db, fs=fs_bucket, http=http, app=app, headers=headers,
                                  users=users, password=password, bootstrap=bootstrap,
                                  database=database)
    finally:
        # Only this generated DB can be deleted; no broad collection flush.
        if db.name == database and database.startswith("aman_ci_"):
            await client.drop_database(database)
        await redis_utils.tutup_client()
        client.close()
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
