"""Bootstrap admin: tertutup untuk publik, sekali pakai, dan bebas balapan."""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.auth as ra
from bootstrap_state import (COLLECTION_NAME as STATE_COLLECTION,
                             STATE_ID, tutup_bila_pengguna_sudah_ada)
from models import OTPRequest, OTPVerify, UserCreate, UserLogin


TOKEN = "b" * ra.MIN_BOOTSTRAP_TOKEN_LENGTH
PASSWORD = "RahasiaAman123"


class _Req:
    headers = {}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(ra, "db", fake)
    monkeypatch.setenv(ra.BOOTSTRAP_TOKEN_ENV, TOKEN)
    return fake


def test_registrasi_publik_tidak_bisa_menjadi_admin_pertama(dbx):
    async def skenario():
        fn = _unwrap(ra.register)
        with pytest.raises(HTTPException) as exc:
            await fn(_Req(), UserCreate(
                username="penyerang@example.go.id", password=PASSWORD,
                name="Bukan Admin"))
        assert exc.value.status_code == 503
        assert await dbx.users.count_documents({}) == 0

    _jalan(skenario())


def test_jalur_otp_juga_ditutup_sebelum_admin_tersedia(dbx):
    async def skenario():
        with pytest.raises(HTTPException) as req_exc:
            await _unwrap(ra.request_otp)(
                _Req(), OTPRequest(email="orang@example.go.id",
                                   password=PASSWORD, name="Orang"))
        assert req_exc.value.status_code == 503

        with pytest.raises(HTTPException) as verify_exc:
            await _unwrap(ra.verify_otp)(
                _Req(), OTPVerify(email="orang@example.go.id", otp="123456"))
        assert verify_exc.value.status_code == 503

    _jalan(skenario())


@pytest.mark.parametrize("admin", [
    {"role": "super_admin", "is_active": True},
    {"role": "admin", "is_active": False},
    {"role": "admin", "is_active": None},
])
def test_hanya_admin_yang_bisa_login_dianggap_penyetuju_tersedia(dbx, admin):
    async def skenario():
        await dbx.users.insert_one({
            "id": "admin-rusak", "username": "rusak@example.go.id", **admin,
        })
        with pytest.raises(HTTPException) as exc:
            await _unwrap(ra.register)(
                _Req(), UserCreate(username="baru@example.go.id",
                                   password=PASSWORD, name="Baru"))
        assert exc.value.status_code == 503

    _jalan(skenario())


def test_admin_legacy_tanpa_field_is_active_tetap_dikenali(dbx):
    async def skenario():
        await dbx.users.insert_one({
            "id": "admin-lama", "username": "lama@example.go.id",
            "role": "admin",
        })
        hasil = await _unwrap(ra.register)(
            _Req(), UserCreate(username="baru@example.go.id",
                               password=PASSWORD, name="Baru"))
        assert hasil["user"]["role"] == "viewer"
        assert hasil["user"]["is_active"] is False

    _jalan(skenario())


def test_bootstrap_wajib_secret_server_yang_valid(dbx, monkeypatch):
    async def skenario():
        fn = _unwrap(ra.bootstrap_admin)
        data = UserCreate(username="admin@example.go.id", password=PASSWORD,
                          name="Admin Awal")

        with pytest.raises(HTTPException) as salah:
            await fn(_Req(), data, "token-yang-salah")
        assert salah.value.status_code == 403
        assert await dbx.users.count_documents({}) == 0

        monkeypatch.delenv(ra.BOOTSTRAP_TOKEN_ENV)
        with pytest.raises(HTTPException) as kosong:
            await fn(_Req(), data, TOKEN)
        assert kosong.value.status_code == 503

    _jalan(skenario())


def test_bootstrap_hanya_sekali_lalu_registrasi_tetap_viewer(dbx):
    async def skenario():
        fn = _unwrap(ra.bootstrap_admin)
        hasil = await fn(
            _Req(),
            UserCreate(username="ADMIN@EXAMPLE.GO.ID", password=PASSWORD,
                       name="Admin Awal"),
            TOKEN,
        )
        assert hasil["user"]["role"] == "admin"
        assert hasil["user"]["username"] == "admin@example.go.id"
        assert hasil["access_token"]

        masuk = await _unwrap(ra.login)(
            _Req(), UserLogin(username="ADMIN@EXAMPLE.GO.ID",
                              password=PASSWORD))
        assert masuk.user.username == "admin@example.go.id"
        assert masuk.user.role == "admin"

        tersimpan = await dbx.users.find_one({"username": "admin@example.go.id"})
        assert tersimpan["bootstrap_admin"] is True
        assert tersimpan["is_active"] is True
        state = await dbx[STATE_COLLECTION].find_one({"_id": STATE_ID})
        assert state["status"] == "closed"
        assert "claim_id" not in state

        with pytest.raises(HTTPException) as kedua:
            await fn(
                _Req(),
                UserCreate(username="lain@example.go.id", password=PASSWORD,
                           name="Admin Lain"),
                TOKEN,
            )
        assert kedua.value.status_code == 409

        daftar = await _unwrap(ra.register)(
            _Req(), UserCreate(username="viewer@example.go.id",
                               password=PASSWORD, name="Viewer"))
        assert daftar["access_token"] is None
        assert daftar["pending_approval"] is True
        assert daftar["user"]["role"] == "viewer"
        assert daftar["user"]["is_active"] is False

    _jalan(skenario())


def test_registrasi_otp_tetap_berfungsi_setelah_admin_tersedia(dbx,
                                                               monkeypatch):
    async def skenario():
        await _unwrap(ra.bootstrap_admin)(
            _Req(),
            UserCreate(username="admin@example.go.id", password=PASSWORD,
                       name="Admin Awal"),
            TOKEN,
        )

        kotak = {}

        async def simpan(email, otp, user_data):
            kotak[email] = {"otp": otp, "user_data": user_data}

        async def ambil(email):
            return kotak.get(email)

        async def hapus(email):
            kotak.pop(email, None)

        async def kirim(_email, _otp, _name):
            return True, "terkirim"

        monkeypatch.setattr(ra, "generate_otp", lambda: "654321")
        monkeypatch.setattr(ra, "store_otp", simpan)
        monkeypatch.setattr(ra, "get_otp", ambil)
        monkeypatch.setattr(ra, "delete_otp", hapus)
        monkeypatch.setattr(ra, "send_otp_email", kirim)

        diminta = await _unwrap(ra.request_otp)(
            _Req(), OTPRequest(email="Viewer@Example.go.id",
                               password=PASSWORD, name="Viewer OTP"))
        assert diminta["otp_sent"] is True

        diverifikasi = await _unwrap(ra.verify_otp)(
            _Req(), OTPVerify(email="viewer@example.go.id", otp="654321"))
        assert diverifikasi["access_token"] is None
        assert diverifikasi["pending_approval"] is True
        assert diverifikasi["user"]["role"] == "viewer"
        assert diverifikasi["user"]["is_active"] is False

    _jalan(skenario())


def test_status_terpisah_mencegah_bootstrap_terbuka_setelah_users_dihapus(dbx):
    async def skenario():
        fn = _unwrap(ra.bootstrap_admin)
        await fn(
            _Req(),
            UserCreate(username="admin@example.go.id", password=PASSWORD,
                       name="Admin Awal"),
            TOKEN,
        )
        await dbx.users.delete_many({})

        with pytest.raises(HTTPException) as kedua:
            await fn(
                _Req(),
                UserCreate(username="penyerang@example.go.id",
                           password=PASSWORD, name="Penyerang"),
                TOKEN,
            )
        assert kedua.value.status_code == 409
        assert await dbx.users.count_documents({}) == 0

    _jalan(skenario())


def test_gagal_menulis_user_setelah_claim_tetap_fail_closed(dbx, monkeypatch):
    async def skenario():
        users = dbx.users

        class UsersGagal:
            async def find_one(self, *args, **kwargs):
                return await users.find_one(*args, **kwargs)

            async def insert_one(self, _doc):
                raise RuntimeError("simulasi Mongo terputus sesudah claim")

        class DbGagal:
            users = UsersGagal()

            def __getitem__(self, nama):
                return dbx[nama]

        monkeypatch.setattr(ra, "db", DbGagal())
        fn = _unwrap(ra.bootstrap_admin)
        data = UserCreate(username="admin@example.go.id", password=PASSWORD,
                          name="Admin Awal")
        with pytest.raises(RuntimeError):
            await fn(_Req(), data, TOKEN)

        state = await dbx[STATE_COLLECTION].find_one({"_id": STATE_ID})
        assert state["status"] == "claimed"
        assert await users.count_documents({}) == 0

        # Retry tidak boleh menciptakan admin lain meski secret tetap benar.
        with pytest.raises(HTTPException) as ulang:
            await fn(_Req(), data, TOKEN)
        assert ulang.value.status_code == 409

    _jalan(skenario())


def test_migrasi_instalasi_lama_menutup_bootstrap_secara_permanen(dbx):
    async def skenario():
        await dbx.users.insert_one({
            "id": "admin-lama", "username": "lama@example.go.id",
            "role": "admin", "is_active": True,
        })
        await tutup_bila_pengguna_sudah_ada(dbx)
        await dbx.users.delete_many({})

        with pytest.raises(HTTPException) as exc:
            await _unwrap(ra.bootstrap_admin)(
                _Req(),
                UserCreate(username="baru@example.go.id", password=PASSWORD,
                           name="Admin Baru"),
                TOKEN,
            )
        assert exc.value.status_code == 409

    _jalan(skenario())


def test_status_bootstrap_tidak_ikut_backup_atau_reset():
    from backup_utils import (collections_from_backup, collections_to_process,
                              collections_to_reset)

    daftar = ["users", STATE_COLLECTION, "assets"]
    assert STATE_COLLECTION not in collections_to_process(daftar)
    assert STATE_COLLECTION not in collections_to_reset(daftar)
    assert STATE_COLLECTION not in collections_from_backup([
        "users.json", f"{STATE_COLLECTION}.json", "assets.json",
    ])


def test_id_konstan_menjadi_cas_untuk_dua_bootstrap_bersamaan(dbx):
    async def skenario():
        fn = _unwrap(ra.bootstrap_admin)

        async def pasang(nama):
            try:
                await fn(
                    _Req(),
                    UserCreate(username=nama, password=PASSWORD, name=nama),
                    TOKEN,
                )
                return "menang"
            except HTTPException as exc:
                return exc.status_code

        hasil = await asyncio.gather(
            pasang("satu@example.go.id"), pasang("dua@example.go.id"))
        assert sorted(str(x) for x in hasil) == ["409", "menang"]
        assert await dbx.users.count_documents({"role": "admin"}) == 1

    _jalan(skenario())
