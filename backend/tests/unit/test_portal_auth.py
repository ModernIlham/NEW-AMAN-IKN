"""Kontrak autentikasi BMN Saya: bebas jaringan, email dan MongoDB nyata."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

import portal_auth as pa
import routes.portal_auth as routes
import routes.pegawai as rp
import shared_utils as su

ORIGIN = "https://portal.example"
PREFIX = "/api/portal-pemegang"
ADMIN = {"id": "admin-a", "username": "admin-a", "role": "admin", "kode_satker": "111111"}
NOW = datetime(2026, 10, 3, 1, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def env(monkeypatch):
    database = AsyncMongoMockClient()["portal_unit"]
    for module in (pa, routes, rp, su):
        monkeypatch.setattr(module, "db", database)
    for module in (routes, rp):
        monkeypatch.setattr(module, "log_audit", AsyncMock())
    monkeypatch.setenv("APP_PUBLIC_URL", ORIGIN)
    monkeypatch.setenv("ALLOWED_ORIGINS", ORIGIN)
    monkeypatch.setattr(pa, "sekarang", lambda: NOW)
    monkeypatch.setattr(su.limiter, "enabled", False)
    kiriman = []

    async def send(email, nama, link):
        kiriman.append({"email": email, "nama": nama, "link": link})
        return True

    monkeypatch.setattr(pa, "kirim_email_portal", send)
    app = FastAPI()
    app.state.limiter = su.limiter
    app.include_router(routes.portal_auth_router, prefix="/api")
    app.include_router(rp.pegawai_router, prefix="/api")
    app.dependency_overrides[routes.require_admin] = lambda: dict(ADMIN)
    peg = {"id": "p-a", "nama": "Ani", "nip": "198501012010011001", "email": "ani@example.org",
           "kode_satker": "111111", "status": "aktif", "status_kepegawaian": "pns", "version": 1}
    run(database.pegawai.insert_one(dict(peg)))
    run(database.idempotency_keys.create_index("key", unique=True))
    with TestClient(app, base_url=ORIGIN) as client:
        yield {"db": database, "client": client, "app": app, "peg": peg, "kiriman": kiriman}


def activate(env, **extra):
    payload = {"pegawai_id": "p-a", "aktif": True, "catatan": "Email dikonfirmasi kepada pemegang",
               "email": "ani@example.org", "konfirmasi_email": True, "version": 0, **extra}
    return env["client"].post(PREFIX + "/admin/akses", json=payload,
                              headers={"Origin": ORIGIN, "If-Match": str(payload["version"]),
                                       "Idempotency-Key": "aktivasi-" + str(payload["version"])})


def ask(env, email="ani@example.org"):
    return env["client"].post(PREFIX + "/auth/minta-link", json={"email": email},
                              headers={"Origin": ORIGIN})


def token(env):
    return parse_qs(urlsplit(env["kiriman"][-1]["link"]).fragment)["token"][0]


def login(env):
    assert activate(env).status_code == 200
    assert ask(env).status_code == 200
    result = env["client"].post(PREFIX + "/auth/masuk", json={"token": token(env)},
                                headers={"Origin": ORIGIN})
    assert result.status_code == 200, result.text
    return result


def test_admin_get_awal_versi_nol_dan_aktivasi_tidak_mengirim_email(env):
    result = env["client"].get(PREFIX + "/admin/akses?pegawai_id=p-a")
    assert result.status_code == 200
    assert result.json()["akses"] == {"aktif": False, "version": 0}
    assert activate(env).status_code == 200
    assert env["kiriman"] == []
    assert run(env["db"].users.count_documents({})) == 0


def test_email_attestation_wajib_dan_menolak_alamat_yang_berubah(env):
    assert activate(env, konfirmasi_email=False).status_code == 400
    assert activate(env, email="lain@example.org").status_code == 400
    assert run(env["db"].portal_pemegang_akses.count_documents({})) == 0


@pytest.mark.parametrize("admin", [{**ADMIN, "kode_satker": ""}, {**ADMIN, "kode_satker": "222222"}])
def test_admin_wajib_satker_eksplisit_sama(env, admin):
    env["app"].dependency_overrides[routes.require_admin] = lambda: admin
    assert activate(env).status_code in {403, 404}


def test_aktivasi_occ_idempotensi_dan_pencabutan(env):
    result = activate(env)
    assert result.status_code == 200
    assert activate(env).json() == result.json()
    assert activate(env, catatan="Permintaan berbeda").status_code == 409
    stale = env["client"].post(PREFIX + "/admin/akses", json={
        "pegawai_id": "p-a", "aktif": False, "catatan": "Akses dicabut", "version": 0},
        headers={"Origin": ORIGIN, "If-Match": "0", "Idempotency-Key": "stale"})
    assert stale.status_code == 409
    assert activate(env, aktif=False, version=1).status_code == 200
    assert ask(env).status_code == 200
    assert env["kiriman"] == []


def test_respons_generik_email_tidak_ada_dan_belum_diaktifkan(env):
    absent = ask(env, "tidakada@example.org")
    pending = ask(env)
    assert absent.status_code == pending.status_code == 200
    assert absent.json() == pending.json() == {"message": pa.PESAN_LINK}
    assert env["kiriman"] == []


def test_token_fragment_cookie_aman_dan_single_use(env):
    assert activate(env).status_code == 200
    r = ask(env)
    challenge = env["client"].cookies.get(pa.CHALLENGE_COOKIE)
    assert "HttpOnly" in r.headers["set-cookie"] and "Secure" in r.headers["set-cookie"]
    assert "SameSite=strict" in r.headers["set-cookie"]
    assert f"Path={PREFIX}" in r.headers["set-cookie"]
    assert urlsplit(env["kiriman"][0]["link"]).query == ""
    raw = token(env)
    saved = run(env["db"].portal_pemegang_tokens.find_one({}))
    assert saved["_id"] == pa.hash_rahasia(raw) and raw not in str(saved)
    result = env["client"].post(PREFIX + "/auth/masuk", json={"token": raw}, headers={"Origin": ORIGIN})
    assert result.status_code == 200
    assert result.json()["session_id"]
    env["client"].cookies.set(pa.CHALLENGE_COOKIE, challenge, domain="portal.example", path=PREFIX)
    repeated = env["client"].post(PREFIX + "/auth/masuk", json={"token": raw}, headers={"Origin": ORIGIN})
    assert repeated.status_code == 401
    assert run(env["db"].portal_pemegang_sesi.count_documents({})) == 1
    cookie = env["client"].cookies.get(pa.SESSION_COOKIE)
    assert cookie not in str(run(env["db"].portal_pemegang_sesi.find_one({})))


def test_scanner_get_dan_browser_lain_tidak_memakai_token(env):
    assert activate(env).status_code == 200
    ask(env)
    raw = token(env)
    with TestClient(env["app"], base_url=ORIGIN) as other:
        assert other.get(PREFIX + "/auth/masuk?token=" + raw).status_code == 405
        assert other.post(PREFIX + "/auth/masuk", json={"token": raw},
                          headers={"Origin": ORIGIN}).status_code == 401
    saved = run(env["db"].portal_pemegang_tokens.find_one({}))
    assert saved["status"] == "menunggu"
    assert env["client"].post(PREFIX + "/auth/masuk", json={"token": raw},
                              headers={"Origin": ORIGIN}).status_code == 200


def test_nonce_salah_dan_origin_salah_ditolak_tanpa_consume(env):
    assert activate(env).status_code == 200
    ask(env)
    raw = token(env)
    assert env["client"].post(PREFIX + "/auth/masuk", json={"token": raw},
                              headers={"Origin": "https://jahat.example"}).status_code == 403
    env["client"].cookies.set(pa.CHALLENGE_COOKIE, pa.rahasia_baru(), domain="portal.example", path=PREFIX)
    assert env["client"].post(PREFIX + "/auth/masuk", json={"token": raw},
                              headers={"Origin": ORIGIN}).status_code == 401
    assert run(env["db"].portal_pemegang_tokens.find_one({}))["status"] == "menunggu"


def test_csrf_keluar_dan_sesi_tidak_menerima_jwt_staf(env):
    assert env["client"].get(PREFIX + "/sesi", headers={"Authorization": "Bearer token-staf"}).status_code == 401
    masuk = login(env).json()
    assert env["client"].post(PREFIX + "/auth/keluar", headers={"Origin": ORIGIN}).status_code == 403
    assert env["client"].get(PREFIX + "/sesi").status_code == 200
    keluar = env["client"].post(PREFIX + "/auth/keluar", headers={"Origin": ORIGIN,
                                                   "X-Portal-CSRF": masuk["csrf_token"]})
    assert keluar.status_code == 200
    assert env["client"].get(PREFIX + "/sesi").status_code == 401


def test_minta_link_tidak_mencabut_sesi_aktif(env):
    session_id = login(env).json()["session_id"]
    assert ask(env).status_code == 200
    assert env["client"].get(PREFIX + "/sesi").json()["session_id"] == session_id


def test_resend_cooldown_tidak_mematikan_challenge_link_sebelumnya(env):
    assert activate(env).status_code == 200
    ask(env)
    raw = token(env)
    challenge = env["client"].cookies.get(pa.CHALLENGE_COOKIE)
    ask(env)
    assert len(env["kiriman"]) == 1
    assert env["client"].cookies.get(pa.CHALLENGE_COOKIE) == challenge
    assert env["client"].post(PREFIX + "/auth/masuk", json={"token": raw},
                              headers={"Origin": ORIGIN}).status_code == 200


def test_tautan_www_mengikuti_origin_terverifikasi_bukan_host_header(env, monkeypatch):
    assert activate(env).status_code == 200
    asal = "https://www.portal.example"
    monkeypatch.setenv("ALLOWED_ORIGINS", ORIGIN + "," + asal)
    with TestClient(env["app"], base_url=asal) as client:
        result = client.post(PREFIX + "/auth/minta-link", json={"email": "ani@example.org"},
                             headers={"Origin": asal, "X-Forwarded-Host": "jahat.example"})
        assert result.status_code == 200
        assert env["kiriman"][-1]["link"].startswith(asal + "/bmn-saya#")
        assert client.post(PREFIX + "/auth/masuk", json={"token": token(env)},
                           headers={"Origin": asal}).status_code == 200


def test_epoch_dinaikkan_dan_token_lama_ditolak(env):
    assert activate(env).status_code == 200
    ask(env)
    raw = token(env)
    run(env["db"].portal_pemegang_akses.update_one({"id": "p-a"}, {"$inc": {"epoch": 1}}))
    assert env["client"].post(PREFIX + "/auth/masuk", json={"token": raw},
                              headers={"Origin": ORIGIN}).status_code == 401


def test_kirim_paralel_token_hanya_membuat_satu_sesi(env):
    from fastapi import Request, Response

    assert activate(env).status_code == 200
    ask(env)
    raw = token(env)
    nonce = env["client"].cookies.get(pa.CHALLENGE_COOKIE)
    fn = routes.masuk_portal
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__

    async def sekali():
        request = Request({"type": "http", "method": "POST", "path": PREFIX + "/auth/masuk",
                           "headers": [(b"origin", ORIGIN.encode()),
                                       (b"cookie", f"{pa.CHALLENGE_COOKIE}={nonce}".encode())]})
        return await fn(request, routes.MasukPortal(token=raw), Response())

    async def bersamaan():
        return await asyncio.gather(sekali(), sekali(), return_exceptions=True)

    results = run(bersamaan())
    assert sum(isinstance(r, dict) for r in results) == 1
    assert run(env["db"].portal_pemegang_sesi.count_documents({})) == 1


@pytest.mark.parametrize("change", [
    {"email": "pengganti@example.org"}, {"status": "nonaktif"},
    {"kode_satker": "222222"}, {"nama": "Orang lain"}, {"nip": "198601012010011001"},
    {"portal_identitas_epoch": "baru"},
])
def test_sesi_gugur_bila_master_berubah_meski_hook_dilewati(env, change):
    login(env)
    run(env["db"].pegawai.update_one({"id": "p-a"}, {"$set": change}))
    assert env["client"].get(PREFIX + "/sesi").status_code == 401


def test_duplikat_email_lintas_satker_menolak_aktivasi_dan_sesi(env):
    login(env)
    run(env["db"].pegawai.insert_one({**env["peg"], "id": "p-b", "kode_satker": "222222",
                                     "email": " ANI@EXAMPLE.ORG "}))
    assert env["client"].get(PREFIX + "/sesi").status_code == 401
    assert activate(env, version=1).status_code == 409


@pytest.mark.parametrize("perubahan", [
    {"status": "nonaktif"}, {"status": "meninggal"}, {"status": "diperbantukan"},
    {"status": ""}, {"kode_satker": ""},
    {"status_kepegawaian": "non_asn", "tgl_selesai_kontrak": "2026-10-02"},
    {"status_kepegawaian": "non_asn", "tgl_mulai_kontrak": "2026-10-04"},
    {"status_kepegawaian": "non_asn", "tgl_selesai_kontrak": "999999-99-99"},
])
def test_pegawai_tidak_layak(env, perubahan):
    assert not pa.pegawai_layak_portal({**env["peg"], **perubahan})


def test_non_asn_tanpa_nip_tetap_boleh(env):
    assert pa.pegawai_layak_portal({**env["peg"], "nip": "", "status_kepegawaian": "non_asn",
                                  "tgl_mulai_kontrak": "2026-10-03", "tgl_selesai_kontrak": "2026-10-03"})


def test_kedaluwarsa_token_idle_dan_absolute(env, monkeypatch):
    assert activate(env).status_code == 200
    ask(env)
    raw = token(env)
    monkeypatch.setattr(pa, "sekarang", lambda: NOW + timedelta(minutes=16))
    assert env["client"].post(PREFIX + "/auth/masuk", json={"token": raw}, headers={"Origin": ORIGIN}).status_code == 401
    monkeypatch.setattr(pa, "sekarang", lambda: NOW + timedelta(minutes=17))
    ask(env)
    assert env["client"].post(PREFIX + "/auth/masuk", json={"token": token(env)}, headers={"Origin": ORIGIN}).status_code == 200
    monkeypatch.setattr(pa, "sekarang", lambda: NOW + timedelta(minutes=48))
    assert env["client"].get(PREFIX + "/sesi").status_code == 401
    run(env["db"].portal_pemegang_sesi.update_many({}, {"$set": {"idle_expires_at": NOW + timedelta(days=1)}}))
    monkeypatch.setattr(pa, "sekarang", lambda: NOW + timedelta(hours=9))
    assert env["client"].get(PREFIX + "/sesi").status_code == 401


def test_rate_email_global_dan_gagal_email_tidak_memberi_token(env, monkeypatch):
    assert activate(env).status_code == 200
    ask(env)
    ask(env)
    assert len(env["kiriman"]) == 1
    assert run(pa.batas_kirim_portal("baru@example.org")) is True
    key = f"global:3600:{int(NOW.timestamp()) // 3600}"
    run(env["db"].portal_pemegang_batas.update_one({"_id": key}, {"$set": {"jumlah": 100}}))
    assert run(pa.batas_kirim_portal("lain@example.org")) is False
    run(env["db"].portal_pemegang_batas.delete_many({}))
    run(env["db"].portal_pemegang_tokens.delete_many({}))
    monkeypatch.setattr(pa, "kirim_email_portal", AsyncMock(return_value=False))
    assert ask(env).status_code == 200
    assert run(env["db"].portal_pemegang_tokens.count_documents({})) == 0


def test_hook_put_hapus_dan_bentrok_create_mencabut_akses(env):
    login(env)
    payload = {k: v for k, v in env["peg"].items() if k not in {"id", "version"}}
    payload["email"] = "emailbaru@example.org"
    edited = env["client"].put("/api/pegawai/p-a", json=payload, headers={"If-Match": "1"})
    assert edited.status_code == 200, edited.text
    assert run(env["db"].portal_pemegang_akses.find_one({"id": "p-a"}))["aktif"] is False
    assert run(env["db"].portal_pemegang_sesi.count_documents({})) == 0
    assert activate(env, email="emailbaru@example.org", version=2).status_code == 200
    dupe = env["client"].post("/api/pegawai", json={"nama": "Pegawai lain", "email": " EMAILBARU@example.org "})
    assert dupe.status_code == 200, dupe.text
    assert run(env["db"].portal_pemegang_akses.find_one({"id": "p-a"}))["aktif"] is False
    deleted = env["client"].delete("/api/pegawai/p-a")
    assert deleted.status_code == 200, deleted.text


def test_hook_impor_mencabut_identitas_dan_revisi_mencegah_hidup_kembali(env, monkeypatch):
    login(env)
    # mongomock versi ini belum menerima argumen sort dari pymongo UpdateOne.
    # Jalankan operasi aslinya satu per satu; query/update tetap dipakai utuh.
    async def bulk(ops, ordered=False):
        from types import SimpleNamespace
        n = 0
        for op in ops:
            result = await env["db"].pegawai.update_one(op._filter, op._doc, upsert=op._upsert)
            n += result.modified_count
        return SimpleNamespace(upserted_count=0, inserted_count=0, modified_count=n)

    monkeypatch.setattr(env["db"].pegawai, "bulk_write", bulk)
    data = "NIP/NIK/NRP,Nama Lengkap,Email\n198501012010011001,Ani,baru@example.org\n"
    result = env["client"].post("/api/pegawai/impor", files={"file": ("pegawai.csv", data.encode(), "text/csv")})
    assert result.status_code == 200, result.text
    assert run(env["db"].portal_pemegang_akses.find_one({"id": "p-a"}))["aktif"] is False
    peg = run(env["db"].pegawai.find_one({"id": "p-a"}))
    assert peg["portal_identitas_epoch"] and peg["version"] == 2
    assert run(env["db"].portal_pemegang_sesi.count_documents({})) == 0


def test_cabut_email_batch_memeriksa_lintas_satker(env):
    login(env)
    run(env["db"].pegawai.insert_one({**env["peg"], "id": "p-b", "kode_satker": "222222",
                                     "email": " ANI@EXAMPLE.ORG "}))
    run(pa.cabut_email_bentrok_banyak(["ani@example.org"], database=env["db"]))
    assert run(env["db"].portal_pemegang_akses.find_one({"id": "p-a"}))["aktif"] is False
    assert run(env["db"].portal_pemegang_sesi.count_documents({})) == 0


def test_restore_cabut_semua_dan_tautan_tertunda_tidak_bertahan(env):
    login(env)
    run(pa.cabut_semua_portal_akses("Restore selesai"))
    run(pa.cabut_semua_portal_akses("Restore selesai"))
    assert env["client"].get(PREFIX + "/sesi").status_code == 401
    assert run(env["db"].portal_pemegang_sesi.count_documents({})) == 0
    assert run(env["db"].portal_pemegang_tokens.count_documents({})) == 0
    assert run(env["db"].portal_pemegang_akses.find_one({"id": "p-a"}))["aktif"] is False


def test_galat_provider_tidak_mencatat_credential(env, monkeypatch, caplog):
    monkeypatch.setattr(su, "RESEND_API_KEY", "kunci-uji")
    secret = "jangan-catat-token-ini"

    def gagal(_params):
        raise RuntimeError(secret)

    monkeypatch.setattr(su.resend.Emails, "send", gagal)
    # Fixture mengganti pengirim portal; ambil implementasi asli tersimpan.
    assert run(PENGIRIM_ASLI("ani@example.org", "Ani", ORIGIN + "/#token=" + secret)) is False
    assert secret not in caplog.text


PENGIRIM_ASLI = pa.kirim_email_portal
