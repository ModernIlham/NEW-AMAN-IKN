"""Uji SISA WAKTU tautan tanda tangan hingga kedaluwarsa.

Mandat pemilik: penanda tangan maupun penerbit harus tahu berapa lama lagi
tautan e-sign berlaku — di halaman registrasi per surat DAN di halaman penanda
tangannya.

JEBAKAN DATA YANG DIJAGA BERKAS INI. Cara "gampang" menghitung sisa waktu
adalah `created_at + 14 hari`. Itu SALAH, dan salahnya ke arah yang berbahaya:

* `exp` token dihitung saat token DICETAK (`auth_utils.create_sign_token`),
  sedangkan `created_at` permintaan ditulis sekali dan tak pernah berubah.
* Tautan yang DITERBITKAN ULANG mendapat token baru berumur 14 hari sejak saat
  itu. Perhitungan dari `created_at` akan mengaku "Kedaluwarsa" padahal
  tautannya masih hidup — penanda tangan berhenti meneken dokumen yang sah,
  dan penerbit mengejar-ngejar tautan yang sebetulnya tak bermasalah.

Karena itu kedaluwarsa DICATAT (`signers[].token_exp`) bersamaan dengan
pencetakan tokennya. Uji di bawah mengunci pencatatan itu di kedua titik
cetak, plus jalan mundur yang jujur untuk data lama.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.ttd as rt
from auth_utils import SIGN_TOKEN_EXPIRATION_DAYS

USER_A = {"username": "penulis-a", "role": "admin", "kode_satker": "111111"}

HARI = 86400


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    import tautan_pendek_utils as tp
    for mod in (rt, su, tp):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "send_esign_email", _diam, raising=False)
    return fake


def _iso(**delta):
    return (datetime.now(timezone.utc) + timedelta(**delta)).isoformat()


# ── Helper murni: dari mana angkanya diambil ────────────────────────────────

def test_token_exp_dipakai_apa_adanya_bukan_ditaksir():
    """Bila kedaluwarsa tercatat, itulah yang dipakai — dan bukan perkiraan."""
    sg = {"token_exp": _iso(days=3, hours=1)}
    sr = {"created_at": _iso(days=-13)}     # jauh berbeda: sengaja
    info = rt._sisa_kedaluwarsa(sg, sr)
    assert info["perkiraan"] is False
    # ±1 detik untuk waktu eksekusi uji
    assert abs(info["sisa_detik"] - (3 * HARI + 3600)) <= 2


def test_data_lama_tanpa_token_exp_ditandai_perkiraan():
    """Permintaan era-lama tetap dapat angka — tapi WAJIB berlabel perkiraan,
    supaya UI menampilkannya sebagai '±' dan tak diperlakukan sebagai janji."""
    sr = {"created_at": _iso(days=-4)}
    info = rt._sisa_kedaluwarsa({"nama": "Budi"}, sr)
    assert info["perkiraan"] is True
    assert abs(info["sisa_detik"] - (SIGN_TOKEN_EXPIRATION_DAYS - 4) * HARI) <= 2


def test_tanpa_token_exp_dan_tanpa_created_at_mengaku_tak_tahu():
    """Lebih baik menyembunyikan barisnya daripada menebak. `sisa_detik: None`
    adalah isyarat 'jangan tampilkan', bukan 'nol'."""
    info = rt._sisa_kedaluwarsa({}, {})
    assert info == {"kedaluwarsa": None, "sisa_detik": None, "perkiraan": True}


def test_token_exp_rusak_tak_meledak_dan_tak_mengaku_kedaluwarsa():
    """String kacau (data impor/tangan) tak boleh melempar, dan TAK boleh
    jatuh ke 0 — '0' terbaca 'Kedaluwarsa' dan menghentikan orang meneken."""
    info = rt._sisa_kedaluwarsa({"token_exp": "kemarin sore"}, {"created_at": _iso()})
    assert info["sisa_detik"] is None


def test_created_at_rusak_juga_tak_meledak():
    info = rt._sisa_kedaluwarsa({}, {"created_at": "31-12-9999"})
    assert info["sisa_detik"] is None and info["perkiraan"] is True


def test_sudah_lewat_dijepit_nol_bukan_negatif():
    """Angka negatif akan diformat jadi '-3 hari lagi'. Dijepit di server."""
    info = rt._sisa_kedaluwarsa({"token_exp": _iso(days=-2)}, {})
    assert info["sisa_detik"] == 0
    assert info["kedaluwarsa"]           # tanggalnya tetap dilaporkan apa adanya


def test_token_exp_tanpa_zona_waktu_dianggap_utc():
    """ISO tanpa offset (data lama/impor) tak boleh dibandingkan dengan waktu
    ber-zona — itu melempar TypeError dan menjatuhkan seluruh endpoint."""
    polos = (datetime.now(timezone.utc) + timedelta(days=5)).replace(
        tzinfo=None).isoformat()
    info = rt._sisa_kedaluwarsa({"token_exp": polos}, {})
    assert abs(info["sisa_detik"] - 5 * HARI) <= 2


# ── Titik cetak 1: saat permintaan dibuat ──────────────────────────────────

def test_permintaan_baru_mencatat_kedaluwarsa_tiap_penanda_tangan(dbx):
    async def skenario():
        hasil = await _unwrap(rt.buat_permintaan)(
            rt.PermintaanIn(judul="Dokumen", doc_type="dokumen_unggahan",
                            doc_ref="", mode="paralel",
                            signers=[rt.SignerIn(nama="Budi"),
                                     rt.SignerIn(nama="Wati")]),
            user=USER_A)
        return await dbx.signature_requests.find_one({"id": hasil["id"]})
    sr = _jalan(skenario())
    for s in sr["signers"]:
        info = rt._sisa_kedaluwarsa(s, sr)
        assert info["perkiraan"] is False, "kedaluwarsa harus TERCATAT, bukan ditaksir"
        assert abs(info["sisa_detik"] - SIGN_TOKEN_EXPIRATION_DAYS * HARI) <= 5


# ── Titik cetak 2: saat tautan diterbitkan ulang ───────────────────────────

def test_terbit_ulang_link_menyegarkan_kedaluwarsa(dbx):
    """INTI. Tautan lama nyaris mati, lalu diterbitkan ulang. Token barunya
    berlaku 14 hari LAGI — dan tampilannya wajib ikut, bukan tetap menunjuk
    batas token lama yang sudah dibuang."""
    async def skenario():
        await dbx.signature_requests.insert_one({
            "id": "sr-1", "judul": "Dokumen", "status": "aktif",
            "mode": "paralel", "kode_satker": "111111",
            "created_by": USER_A["username"],
            "created_at": _iso(days=-13),          # tinggal ±1 hari
            "signers": [{"signer_id": "s1", "nama": "Budi", "status": "aktif",
                         "jti": "j-lama", "token_exp": _iso(days=1),
                         "signature_file_id": ""}]})
        await _unwrap(rt.buat_ulang_link)("sr-1", "s1", user=USER_A)
        return await dbx.signature_requests.find_one({"id": "sr-1"})
    sr = _jalan(skenario())
    s = sr["signers"][0]
    assert s["jti"] != "j-lama", "token lama harus mati"
    info = rt._sisa_kedaluwarsa(s, sr)
    assert info["perkiraan"] is False
    assert abs(info["sisa_detik"] - SIGN_TOKEN_EXPIRATION_DAYS * HARI) <= 5, (
        "menghitung dari created_at akan menghasilkan ±1 hari — dan menyuruh "
        "orang mengejar tautan yang sebetulnya baru saja diperpanjang")


# ── Yang tampil di layar registrasi ────────────────────────────────────────

def _sr_dua_penanda(**ganti):
    dasar = {
        "id": "sr-2", "judul": "Dokumen", "status": "aktif", "mode": "paralel",
        "kode_satker": "111111", "created_by": USER_A["username"],
        "created_at": _iso(days=-1), "dok_file_id": "",
        "signers": [
            {"signer_id": "s1", "nama": "Budi", "status": "aktif",
             "jti": "j1", "signature_file_id": "", "token_exp": _iso(days=9)},
            {"signer_id": "s2", "nama": "Wati", "status": "aktif",
             "jti": "j2", "signature_file_id": "", "token_exp": _iso(days=2)}]}
    dasar.update(ganti)
    return dasar


def test_kartu_menampilkan_batas_TERCEPAT_di_antara_yang_belum_teken(dbx):
    """Batas terjauh akan menyembunyikan tautan yang justru hampir mati."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dua_penanda())
        return await rt.daftar_permintaan(_user=USER_A)
    it = _jalan(skenario())["items"][0]
    assert abs(it["kedaluwarsa_terdekat"]["sisa_detik"] - 2 * HARI) <= 5


def test_yang_sudah_meneken_tak_ikut_menentukan_sisa_waktu_kartu(dbx):
    """Batas milik orang yang sudah selesai tak lagi bermakna — bila ia ikut
    dihitung, kartu menyala 'mendesak' padahal tak ada yang perlu ditagih."""
    sr = _sr_dua_penanda()
    sr["signers"][1].update(status="ditandatangani", signature_file_id="f2")

    async def skenario():
        await dbx.signature_requests.insert_one(sr)
        return await rt.daftar_permintaan(_user=USER_A)
    it = _jalan(skenario())["items"][0]
    assert abs(it["kedaluwarsa_terdekat"]["sisa_detik"] - 9 * HARI) <= 5


def test_semua_sudah_teken_tak_menampilkan_sisa_waktu(dbx):
    sr = _sr_dua_penanda()
    for s in sr["signers"]:
        s.update(status="ditandatangani", signature_file_id="f")

    async def skenario():
        await dbx.signature_requests.insert_one(sr)
        return await rt.daftar_permintaan(_user=USER_A)
    assert _jalan(skenario())["items"][0]["kedaluwarsa_terdekat"] is None


def test_detail_memberi_sisa_waktu_PER_penanda_tangan(dbx):
    """Inilah "per masing-masing" yang dipakai untuk memutuskan tautan SIAPA
    yang perlu diterbitkan ulang."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dua_penanda())
        return await rt.detail_permintaan("sr-2", user=USER_A)
    sg = {s["signer_id"]: s["kedaluwarsa_info"] for s in _jalan(skenario())["signers"]}
    assert abs(sg["s1"]["sisa_detik"] - 9 * HARI) <= 5
    assert abs(sg["s2"]["sisa_detik"] - 2 * HARI) <= 5


# ── Yang tampil di halaman penanda tangan (publik) ─────────────────────────

def test_halaman_penanda_tangan_menerima_sisa_waktunya_sendiri(dbx):
    """Dihitung DI SERVER: jam perangkat tamu bisa meleset, dan tulisan
    'kedaluwarsa' yang keliru membuat orang berhenti meneken dokumen sah."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dua_penanda())
        return await _unwrap(rt.info_tandatangan)(
            "sr-2", tok={"sr": "sr-2", "signer": "s2", "jti": "j2"})
    r = _jalan(skenario())
    assert abs(r["sisa_detik"] - 2 * HARI) <= 5
    assert r["perkiraan"] is False and r["kedaluwarsa"]
