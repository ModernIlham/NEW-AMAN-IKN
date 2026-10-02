"""Alur HTTP portal lengkap dengan cookie asli TestClient dan Mongo tiruan.

Hanya autentikasi staf dan pengiriman email diganti. Dependency sesi/CSRF
pemegang, middleware, parsing body, OCC, dan route domain dijalankan utuh.
"""
import asyncio
import base64
import io
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient
from PIL import Image

import portal_auth as pa
import routes.portal_auth as auth
import routes.portal_pemegang as domain
import shared_utils as su
from auth_utils import require_admin, require_user, require_writer
from portal_middleware import PortalPemegangMiddleware


ORIGIN = "https://portal-http.example.test"
PREFIX = "/api/portal-pemegang"
ADMIN = {"id": "admin-http", "username": "admin@example.test", "role": "admin", "kode_satker": "001"}
OPERATOR = {"id": "operator-http", "username": "operator@example.test", "role": "operator", "kode_satker": "001"}


def run(coro):
    return asyncio.run(coro)


def headers(key, version, csrf=None):
    return {"Origin": ORIGIN, "Idempotency-Key": key, "If-Match": str(version),
            **({"X-Portal-CSRF": csrf} if csrf else {})}


def test_http_tautan_sesi_penugasan_bukti_review_dan_isolasi(monkeypatch):
    database = AsyncMongoMockClient()["uji_portal_http"]
    for module in (pa, auth, domain, su):
        monkeypatch.setattr(module, "db", database)
    monkeypatch.setattr(auth, "log_audit", AsyncMock())
    monkeypatch.setattr(domain, "log_audit", AsyncMock())
    monkeypatch.setattr(su.limiter, "enabled", False)
    monkeypatch.setenv("APP_PUBLIC_URL", ORIGIN)
    monkeypatch.setenv("ALLOWED_ORIGINS", ORIGIN)
    kiriman = []

    async def email_tiruan(email, nama, link):
        kiriman.append({"email": email, "nama": nama, "link": link})
        return True

    monkeypatch.setattr(pa, "kirim_email_portal", email_tiruan)
    run(database.pegawai.insert_many([
        {"id": "p1", "nama": "Pegawai Pertama", "nip": "123456789",
         "email": "satu@example.test", "kode_satker": "001", "status": "aktif", "version": 1},
        {"id": "p2", "nama": "Pegawai Kedua", "nip": "987654321",
         "email": "dua@example.test", "kode_satker": "001", "status": "aktif", "version": 1},
    ]))
    run(database.inventory_activities.insert_one({"id": "act1", "kode_satker": "001"}))
    run(database.assets.insert_one({
        "id": "as1", "activity_id": "act1", "asset_code": "3050104001", "NUP": "1",
        "asset_name": "Laptop Pemeriksaan", "condition": "Baik", "location": "Ruang Awal",
        "user": "Pegawai Pertama", "pengguna_nip": "123456789", "version": 9,
    }))
    run(database.idempotency_keys.create_index("key", unique=True))
    sebelum_aset = run(database.assets.find_one({"id": "as1"}))

    app = FastAPI()
    app.state.limiter = su.limiter
    app.include_router(auth.portal_auth_router, prefix="/api")
    app.include_router(domain.portal_pemegang_router, prefix="/api")
    app.add_middleware(PortalPemegangMiddleware)
    app.dependency_overrides[require_admin] = lambda: dict(ADMIN)
    app.dependency_overrides[require_writer] = lambda: dict(OPERATOR)
    app.dependency_overrides[require_user] = lambda: dict(OPERATOR)

    def aktifkan(client, pid, email):
        result = client.post(PREFIX + "/admin/akses", json={
            "pegawai_id": pid, "aktif": True, "email": email,
            "konfirmasi_email": True, "version": 0,
            "catatan": "Email telah diperiksa langsung kepada pegawai",
        }, headers=headers("akses-" + pid, 0))
        assert result.status_code == 200, result.text

    def masuk(client, email):
        requested = client.post(PREFIX + "/auth/minta-link", json={"email": email},
                                headers={"Origin": ORIGIN})
        assert requested.status_code == 200, requested.text
        assert client.cookies.get(pa.CHALLENGE_COOKIE)
        assert "Secure" in requested.headers["set-cookie"]
        link = kiriman[-1]["link"]
        assert urlsplit(link).query == "" and urlsplit(link).path == "/bmn-saya"
        token = parse_qs(urlsplit(link).fragment)["token"][0]
        logged = client.post(PREFIX + "/auth/masuk", json={"token": token},
                             headers={"Origin": ORIGIN})
        assert logged.status_code == 200, logged.text
        assert client.cookies.get(pa.SESSION_COOKIE)
        assert "HttpOnly" in logged.headers["set-cookie"]
        assert "SameSite=strict" in logged.headers["set-cookie"]
        assert "private, no-store" in logged.headers["cache-control"]
        session = client.get(PREFIX + "/sesi")
        assert session.status_code == 200
        assert session.json()["session_id"] == logged.json()["session_id"]
        assert session.json()["csrf_token"] == logged.json()["csrf_token"]
        assert session.json()["idle_expires_at"]
        return session.json()

    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get(PREFIX + "/aset").status_code == 401
        aktifkan(client, "p1", "satu@example.test")
        session = masuk(client, "satu@example.test")
        csrf = session["csrf_token"]
        mapped = client.post(PREFIX + "/admin/penugasan", json={
            "pegawai_id": "p1", "asset_id": "as1",
            "dasar_penugasan": "BAST sah nomor 123 tanggal 1 Oktober 2026", "catatan": "Pemetaan akses",
        }, headers=headers("map-p1", 0))
        assert mapped.status_code == 200, mapped.text
        pid = mapped.json()["item"]["id"]
        assignments = client.get(PREFIX + "/aset").json()
        assert assignments["total"] == 1
        assert assignments["items"][0]["version"] == 1
        assert assignments["items"][0]["status"] == "menunggu_konfirmasi"
        assert assignments["items"][0]["asset_id"] == "as1"

        confirmation = {"version": 1, "keputusan": "terima", "catatan": "Barang telah saya periksa"}
        assert client.post(PREFIX + f"/penugasan/{pid}/konfirmasi", json=confirmation,
                           headers=headers("terima-p1", 1)).status_code == 403
        accepted = client.post(PREFIX + f"/penugasan/{pid}/konfirmasi", json=confirmation,
                               headers=headers("terima-p1", 1, csrf))
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["item"]["status"] == "diterima"
        assert accepted.json()["item"]["version"] == 2
        assert client.post(PREFIX + f"/penugasan/{pid}/konfirmasi", json=confirmation,
                           headers=headers("terima-p1", 1, csrf)).json() == accepted.json()

        image = io.BytesIO()
        Image.new("RGB", (24, 16), "navy").save(image, "PNG")
        original = image.getvalue()
        body = {
            "penugasan_id": pid, "penugasan_version": 2, "jenis": "kerusakan",
            "kondisi": "Rusak Ringan", "status_operasional": "tidak_digunakan",
            "lokasi_laporan": "Ruang Pemeriksaan", "catatan": "Tombol papan ketik tidak bekerja",
            "diambil_pada": "2026-10-03T09:10:00+08:00", "laporan_sebelumnya_id": "",
            "bukti": [{"nama": "papan-ketik.png", "mime": "image/png",
                       "data_base64": base64.b64encode(original).decode("ascii")}],
        }
        sent = client.post(PREFIX + "/laporan", json=body, headers=headers("laporan-p1", 2, csrf))
        assert sent.status_code == 200, sent.text
        rid = sent.json()["item"]["id"]
        assert sent.json()["item"]["version"] == 1
        assert sent.json()["item"]["status"] == "diajukan"
        assert "data_base64" not in sent.text
        assert client.post(PREFIX + "/laporan", json=body,
                           headers=headers("laporan-p1", 2, csrf)).json() == sent.json()
        assert run(database.portal_laporan.count_documents({})) == 1
        evidence = client.get(PREFIX + f"/laporan/{rid}/bukti/0")
        assert evidence.status_code == 200 and evidence.content == original
        assert evidence.headers["content-type"] == "image/png"
        assert evidence.headers["x-content-type-options"] == "nosniff"
        assert "no-store" in evidence.headers["cache-control"]

        staff_list = client.get(PREFIX + "/admin/laporan", params={
            "pegawai_id": "p1", "status": "diajukan", "page": 1, "page_size": 10})
        assert staff_list.status_code == 200
        assert staff_list.json()["total"] == 1 and staff_list.json()["items"][0]["id"] == rid
        assert "data_base64" not in staff_list.text
        reviewed = client.post(PREFIX + f"/admin/laporan/{rid}/tinjau", json={
            "version": 1, "keputusan": "terverifikasi", "catatan": "Bukti sesuai; lanjutkan telaah pemeliharaan",
        }, headers=headers("review-p1", 1))
        assert reviewed.status_code == 200, reviewed.text
        history = client.get(PREFIX + "/laporan").json()
        assert history["total"] == 1
        assert history["items"][0]["version"] == 2
        assert history["items"][0]["status"] == "terverifikasi"
        assert history["items"][0]["tinjauan"][0]["oleh"] == OPERATOR["username"]
        assert client.get(PREFIX + f"/admin/laporan/{rid}/bukti/0").content == original
        assert run(database.assets.find_one({"id": "as1"})) == sebelum_aset
        assert run(database.mutasi_bmn.count_documents({})) == 0
        assert run(database.pemeliharaan.count_documents({})) == 0

        # Cookie pegawai lain sungguhan (bukan dependency override holder).
        aktifkan(client, "p2", "dua@example.test")
        with TestClient(app, base_url=ORIGIN) as other:
            second = masuk(other, "dua@example.test")
            assert second["pegawai"]["id"] == "p2"
            assert other.get(PREFIX + "/aset").json() == {"items": [], "total": 0}
            assert other.get(PREFIX + "/laporan").json() == {"items": [], "total": 0}
            assert other.get(PREFIX + f"/laporan/{rid}/bukti/0").status_code == 404
            denied = other.post(PREFIX + "/laporan", json=body,
                                headers=headers("curang-p2", 2, second["csrf_token"]))
            assert denied.status_code == 404
            assert run(database.portal_laporan.count_documents({})) == 1
