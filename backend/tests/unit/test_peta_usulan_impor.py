"""Uji IMPOR USULAN peta kolaborasi ke peta ASLI.

Mandat pemilik: hasil penambahan titik dan komentarnya dapat diimpor ke peta
asli satu per satu ATAU sekaligus ("yakin semua"); titik yang disetujui
menjadi aset baru berkode barang dummy "0000000000" + NUP otomatis.

Yang dijaga berkas ini adalah hal-hal yang rusaknya SENYAP:

* NUP KEMBAR pada impor massal. Membaca "NUP terbesar" ulang per titik akan
  mengembalikan angka yang sama berkali-kali dalam satu batch — aset kedua
  dan seterusnya lahir bernomor sama (atau gagal karena bentrok keunikan).
* ASET KEMBAR saat tombol ditekan dua kali / batch diulang karena jaringan
  putus. Persetujuan memakai kunci idempotensi turunan id usulan.
* KOMENTAR YATIM. Komentar pada TITIK usulan tak punya aset tujuan sampai
  titiknya disetujui; menyalinnya lebih dulu akan menunjuk id yang tak pernah
  ada di peta asli.
* USULAN ERA-LAMA HILANG. Dokumen sebelum alur ini tak punya `status_usulan`;
  bila dianggap "sudah selesai" ia tak akan pernah muncul di layar peninjauan.
* ISOLASI SATKER. Menyetujui = menulis data resmi. Tamu pemegang tautan dan
  admin satker LAIN tak boleh bisa.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.peta_kolaborasi as pk

ADMIN_A = {"username": "a", "role": "admin", "kode_satker": "111111"}
ADMIN_B = {"username": "b", "role": "admin", "kode_satker": "222222"}
OPERATOR_A = {"username": "op-a", "role": "operator", "kode_satker": "111111"}

SHARE_ID = "sh-1"
KEG = "keg-1"


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    import routes.assets as ra
    import spasial_penempatan as sp_mod
    for mod in (pk, su, ra, sp_mod):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    # Jalur samping create_asset yang tak relevan bagi uji ini.
    monkeypatch.setattr(ra, "jadwalkan_sync", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(ra, "invalidate_asset_cache", lambda *a, **k: None,
                        raising=False)
    return fake


async def _seed(dbx, **ganti):
    await dbx.inventory_activities.insert_one(
        {"id": KEG, "kode_satker": "111111", "nama": "Inventarisasi 2026"})
    doc = {"id": SHARE_ID, "activity_id": KEG, "kode_satker": "111111",
           "nama_kegiatan": "Inventarisasi 2026", "judul": "Peta",
           "jti": "j1", "status": "aktif",
           "berlaku_sampai": "2099-01-01T00:00:00+00:00",
           "izinkan_titik_publik": True, "izinkan_komentar_publik": True,
           "created_by": "a", "created_at": "2026-01-01T00:00:00+00:00",
           "updated_at": "2026-01-01T00:00:00+00:00"}
    doc.update(ganti)
    await dbx.peta_shares.insert_one(doc)
    await dbx.categories.insert_one({"id": "k1", "label": "Dummy",
                                     "kode_aset": "0000000000"})


async def _titik(dbx, tid, nama, lat=-0.9, lng=116.7, **ganti):
    doc = {"id": tid, "share_id": SHARE_ID, "jenis": "titik",
           "lat": lat, "lng": lng, "nama_titik": nama, "keterangan": "",
           "oleh": "Budi", "oleh_tipe": "tamu", "oleh_user_id": "",
           "kode_satker": "111111", "activity_id": KEG,
           "created_at": f"2026-01-02T00:00:0{tid[-1]}+00:00",
           "dihapus": False, "status_usulan": "terbuka"}
    doc.update(ganti)
    await dbx.peta_kolaborasi.insert_one(doc)
    return doc


async def _komentar(dbx, kid, target_jenis, target_id, teks="bagus", **ganti):
    doc = {"id": kid, "share_id": SHARE_ID, "jenis": "komentar",
           "target_jenis": target_jenis, "target_id": target_id, "teks": teks,
           "oleh": "Wati", "oleh_tipe": "tamu", "oleh_user_id": "",
           "kode_satker": "111111", "activity_id": KEG,
           "created_at": "2026-01-03T00:00:00+00:00",
           "dihapus": False, "status_usulan": "terbuka"}
    doc.update(ganti)
    await dbx.peta_kolaborasi.insert_one(doc)
    return doc


# ── Isolasi: menyetujui = menulis data resmi ───────────────────────────────

def test_admin_satker_lain_tak_boleh_meninjau(dbx):
    async def skenario():
        await _seed(dbx)
        await pk.daftar_usulan(SHARE_ID, user=ADMIN_B)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 403


def test_admin_satker_lain_tak_boleh_menyetujui(dbx):
    async def skenario():
        await _seed(dbx)
        await _titik(dbx, "t1", "Genset")
        await _unwrap(pk.setujui_usulan)(SHARE_ID, "t1", request=None, user=ADMIN_B)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 403
    # Tak ada aset yang terlanjur lahir sebelum penolakan.
    assert _jalan(dbx.assets.count_documents({})) == 0


def test_operator_satker_sendiri_boleh_menyetujui(dbx):
    """Impor usulan pekerjaan lapangan — operator, bukan hanya admin."""
    async def skenario():
        await _seed(dbx)
        await _titik(dbx, "t1", "Genset")
        return await _unwrap(pk.setujui_usulan)(SHARE_ID, "t1", request=None,
                                                user=OPERATOR_A)
    assert _jalan(skenario())["ok"] is True


# ── Titik disetujui → aset berkode dummy + NUP otomatis ────────────────────

def test_titik_disetujui_jadi_aset_kode_dummy_dan_nup(dbx):
    async def skenario():
        await _seed(dbx)
        await _titik(dbx, "t1", "Genset Lapangan", lat=-0.925, lng=116.712)
        r = await _unwrap(pk.setujui_usulan)(SHARE_ID, "t1", request=None,
                                             user=ADMIN_A)
        aset = await dbx.assets.find_one({"id": r["aset_id"]}, {"_id": 0})
        usulan = await dbx.peta_kolaborasi.find_one({"id": "t1"}, {"_id": 0})
        return aset, usulan
    aset, usulan = _jalan(skenario())
    assert aset["asset_code"] == "0000000000"
    assert aset["NUP"] == "1"
    assert aset["asset_name"] == "Genset Lapangan"
    assert aset["activity_id"] == KEG
    assert aset["koordinat_latitude"].startswith("-0.925")
    assert "dummy" in str(aset["category"]).lower()
    assert aset["inventory_status"] == "Belum Diinventarisasi"
    # Jejak asal-usul ikut tercatat pada asetnya.
    assert "Budi" in str(aset.get("notes") or "")
    # Usulannya ditandai, bukan dihapus.
    assert usulan["status_usulan"] == "disetujui"
    assert usulan["aset_id"] == aset["id"]
    assert usulan["ditinjau_oleh"] == "a"


def test_setujui_dua_kali_tak_melahirkan_aset_kembar(dbx):
    """Tombol ditekan dua kali / jaringan putus lalu diulang."""
    async def skenario():
        await _seed(dbx)
        await _titik(dbx, "t1", "Genset")
        a = await _unwrap(pk.setujui_usulan)(SHARE_ID, "t1", request=None, user=ADMIN_A)
        b = await _unwrap(pk.setujui_usulan)(SHARE_ID, "t1", request=None, user=ADMIN_A)
        return a, b, await dbx.assets.count_documents({})
    a, b, n = _jalan(skenario())
    assert n == 1, "persetujuan ulang tak boleh melahirkan aset kedua"
    assert b.get("sudah") is True and b["aset_id"] == a["aset_id"]


# ── "Yakin semua" — impor massal ───────────────────────────────────────────

def test_setujui_semua_memberi_nup_berurutan_tanpa_kembar(dbx):
    """Satu batch harus menghasilkan deret NUP rapat tanpa kembar & tanpa
    bolong. (Keunikannya sendiri ditegakkan `create_asset`; uji ini menjaga
    penghitung batch tetap benar sehingga tak ada penolakan bentrok.)"""
    async def skenario():
        await _seed(dbx)
        for i in range(1, 6):
            await _titik(dbx, f"t{i}", f"Titik {i}", lat=-0.9 - i / 1000)
        r = await _unwrap(pk.setujui_semua_usulan)(
            SHARE_ID, pk.SetujuiSemuaIn(), request=None, user=ADMIN_A)
        aset = await dbx.assets.find({}, {"_id": 0, "NUP": 1, "asset_code": 1}).to_list(50)
        return r, aset
    r, aset = _jalan(skenario())
    assert r["disetujui"] == 5 and not r["gagal"]
    nups = sorted(int(a["NUP"]) for a in aset)
    assert nups == [1, 2, 3, 4, 5], f"NUP kembar/bolong: {nups}"
    assert all(a["asset_code"] == "0000000000" for a in aset)


def test_setujui_semua_menyambung_dari_nup_yang_sudah_ada(dbx):
    """Batch kedua tak boleh mengulang nomor batch pertama."""
    async def skenario():
        await _seed(dbx)
        await _titik(dbx, "t1", "A")
        await _unwrap(pk.setujui_semua_usulan)(
            SHARE_ID, pk.SetujuiSemuaIn(), request=None, user=ADMIN_A)
        await _titik(dbx, "t2", "B")
        await _titik(dbx, "t3", "C")
        await _unwrap(pk.setujui_semua_usulan)(
            SHARE_ID, pk.SetujuiSemuaIn(), request=None, user=ADMIN_A)
        return await dbx.assets.find({}, {"_id": 0, "NUP": 1}).to_list(50)
    nups = sorted(int(a["NUP"]) for a in _jalan(skenario()))
    assert nups == [1, 2, 3]


def test_setujui_semua_mendahulukan_titik_walau_urutan_waktu_terbalik(dbx):
    """INTI. Komentar pada TITIK usulan baru punya aset tujuan SETELAH titiknya
    jadi aset. Urutan alami biasanya sudah benar, tapi ia bersandar pada
    perbandingan STRING waktu — meleset bila stempel waktunya bercampur format
    atau jam perangkat penyumbang salah. Di sini komentarnya sengaja bertanggal
    LEBIH AWAL daripada titiknya: tanpa pengurutan eksplisit, komentar itu
    dilewati diam-diam padahal pemilik menekan "yakin semua"."""
    async def skenario():
        await _seed(dbx)
        await _komentar(dbx, "k1", "titik", "t1", teks="atapnya bocor",
                        created_at="2026-01-01T00:00:00+00:00")
        await _titik(dbx, "t1", "Pos Jaga",
                     created_at="2026-01-09T00:00:00+00:00")
        r = await _unwrap(pk.setujui_semua_usulan)(
            SHARE_ID, pk.SetujuiSemuaIn(), request=None, user=ADMIN_A)
        kom = await dbx.komentar_aset.find({}, {"_id": 0}).to_list(10)
        return r, kom
    r, kom = _jalan(skenario())
    assert r["disetujui"] == 2 and not r["dilewati"] and not r["gagal"]
    assert len(kom) == 1
    assert kom[0]["teks"] == "atapnya bocor" and kom[0]["oleh"] == "Wati"
    assert kom[0]["kode_satker"] == "111111"


def test_komentar_pada_titik_yang_belum_disetujui_ditolak_terang_terangan(dbx):
    """409 dengan sebab, bukan komentar yatim yang menunjuk id tak ada."""
    async def skenario():
        await _seed(dbx)
        await _titik(dbx, "t1", "Pos")
        await _komentar(dbx, "k1", "titik", "t1")
        await _unwrap(pk.setujui_usulan)(SHARE_ID, "k1", request=None, user=ADMIN_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 409
    assert "titik" in str(e.value.detail).lower()
    assert _jalan(dbx.komentar_aset.count_documents({})) == 0


def test_komentar_pada_aset_nyata_langsung_bisa_diimpor(dbx):
    async def skenario():
        await _seed(dbx)
        await _komentar(dbx, "k1", "aset", "aset-nyata-1", teks="perlu dicat")
        r = await _unwrap(pk.setujui_usulan)(SHARE_ID, "k1", request=None, user=ADMIN_A)
        return r, await dbx.komentar_aset.find({}, {"_id": 0}).to_list(10)
    r, kom = _jalan(skenario())
    assert r["aset_id"] == "aset-nyata-1"
    assert len(kom) == 1 and kom[0]["asset_id"] == "aset-nyata-1"


def test_komentar_disetujui_dua_kali_tak_menggandakan(dbx):
    async def skenario():
        await _seed(dbx)
        await _komentar(dbx, "k1", "aset", "aset-1")
        await _unwrap(pk.setujui_usulan)(SHARE_ID, "k1", request=None, user=ADMIN_A)
        await dbx.peta_kolaborasi.update_one({"id": "k1"},
                                             {"$set": {"status_usulan": "terbuka"}})
        await _unwrap(pk.setujui_usulan)(SHARE_ID, "k1", request=None, user=ADMIN_A)
        return await dbx.komentar_aset.count_documents({})
    assert _jalan(skenario()) == 1


# ── Layar peninjauan ───────────────────────────────────────────────────────

def test_usulan_era_lama_tanpa_status_tetap_muncul_sebagai_terbuka(dbx):
    """Dokumen sebelum alur ini tak punya `status_usulan`. Kalau dianggap
    selesai, kontribusi lapangan yang sudah terlanjur masuk tak akan pernah
    bisa diimpor — hilang tanpa pernah terlihat."""
    async def skenario():
        await _seed(dbx)
        await dbx.peta_kolaborasi.insert_one(
            {"id": "lama", "share_id": SHARE_ID, "jenis": "titik",
             "lat": -0.9, "lng": 116.7, "nama_titik": "Titik Lama",
             "oleh": "Tamu", "created_at": "2025-05-01T00:00:00+00:00",
             "dihapus": False})
        return await pk.daftar_usulan(SHARE_ID, user=ADMIN_A)
    r = _jalan(skenario())
    assert r["jumlah"] == 1 and r["items"][0]["id"] == "lama"
    assert r["items"][0]["status_usulan"] == "terbuka"
    assert r["rekap"]["terbuka"] == 1


def test_daftar_usulan_tak_membocorkan_ip_kontributor(dbx):
    async def skenario():
        await _seed(dbx)
        await _titik(dbx, "t1", "X", ip="203.0.113.9", oleh_user_id="u-1")
        return await pk.daftar_usulan(SHARE_ID, user=ADMIN_A)
    it = _jalan(skenario())["items"][0]
    assert "ip" not in it and "oleh_user_id" not in it


def test_rekap_memisahkan_terbuka_disetujui_ditolak(dbx):
    async def skenario():
        await _seed(dbx)
        await _titik(dbx, "t1", "A")
        await _titik(dbx, "t2", "B", status_usulan="ditolak")
        await _unwrap(pk.setujui_usulan)(SHARE_ID, "t1", request=None, user=ADMIN_A)
        await _titik(dbx, "t3", "C")
        return await pk.daftar_usulan(SHARE_ID, status="semua", user=ADMIN_A)
    r = _jalan(skenario())
    assert r["rekap"] == {"terbuka": 1, "disetujui": 1, "ditolak": 1}


def test_tolak_menyimpan_alasan_dan_tak_menghapus_usulan(dbx):
    async def skenario():
        await _seed(dbx)
        await _titik(dbx, "t1", "A")
        await _unwrap(pk.tolak_usulan)(SHARE_ID, "t1", pk.TinjauIn(alasan="duplikat"),
                                       request=None, user=ADMIN_A)
        return await dbx.peta_kolaborasi.find_one({"id": "t1"}, {"_id": 0})
    u = _jalan(skenario())
    assert u["status_usulan"] == "ditolak" and u["alasan_tolak"] == "duplikat"
    assert u["dihapus"] is False, "jejak usulan tak boleh hilang"


def test_usulan_yang_sudah_disetujui_tak_bisa_ditolak_belakangan(dbx):
    """Menolak setelah asetnya lahir akan membuat catatan berbohong."""
    async def skenario():
        await _seed(dbx)
        await _titik(dbx, "t1", "A")
        await _unwrap(pk.setujui_usulan)(SHARE_ID, "t1", request=None, user=ADMIN_A)
        await _unwrap(pk.tolak_usulan)(SHARE_ID, "t1", pk.TinjauIn(),
                                       request=None, user=ADMIN_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 404


# ── Komentar pada peta ASLI ────────────────────────────────────────────────

def test_komentar_aset_terdaftar_per_aset_untuk_peta_asli(dbx):
    async def skenario():
        await _seed(dbx)
        await _komentar(dbx, "k1", "aset", "aset-1", teks="satu")
        await _komentar(dbx, "k2", "aset", "aset-1", teks="dua")
        await _komentar(dbx, "k3", "aset", "aset-2", teks="tiga")
        for kid in ("k1", "k2", "k3"):
            await _unwrap(pk.setujui_usulan)(SHARE_ID, kid, request=None, user=ADMIN_A)
        return await pk.daftar_komentar_aset(activity_id=KEG, _user=ADMIN_A)
    r = _jalan(skenario())
    assert r["jumlah"] == 3
    assert len(r["per_aset"]["aset-1"]) == 2 and len(r["per_aset"]["aset-2"]) == 1


def test_hapus_komentar_aset_satu_per_satu(dbx):
    async def skenario():
        await _seed(dbx)
        await _komentar(dbx, "k1", "aset", "aset-1", teks="satu")
        await _komentar(dbx, "k2", "aset", "aset-1", teks="dua")
        for kid in ("k1", "k2"):
            await _unwrap(pk.setujui_usulan)(SHARE_ID, kid, request=None, user=ADMIN_A)
        semua = await dbx.komentar_aset.find({}, {"_id": 0}).to_list(10)
        satu = next(k for k in semua if k["teks"] == "satu")
        await pk.hapus_komentar_aset(satu["id"], user=ADMIN_A)
        return await pk.daftar_komentar_aset(activity_id=KEG, _user=ADMIN_A)
    r = _jalan(skenario())
    assert r["jumlah"] == 1 and r["items"][0]["teks"] == "dua"


def test_komentar_aset_satker_lain_tak_bisa_dihapus(dbx):
    async def skenario():
        await _seed(dbx)
        await dbx.komentar_aset.insert_one(
            {"id": "kx", "asset_id": "a-x", "activity_id": "keg-lain",
             "kode_satker": "222222", "teks": "milik satker lain",
             "oleh": "X", "created_at": "2026-01-01T00:00:00+00:00",
             "dihapus": False})
        await pk.hapus_komentar_aset("kx", user=ADMIN_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 403


def test_komentar_aset_tak_bocor_lintas_kegiatan(dbx):
    async def skenario():
        await _seed(dbx)
        await dbx.komentar_aset.insert_one(
            {"id": "kx", "asset_id": "a-x", "activity_id": "keg-lain",
             "kode_satker": "111111", "teks": "kegiatan lain",
             "oleh": "X", "created_at": "2026-01-01T00:00:00+00:00",
             "dihapus": False})
        await _komentar(dbx, "k1", "aset", "aset-1")
        await _unwrap(pk.setujui_usulan)(SHARE_ID, "k1", request=None, user=ADMIN_A)
        return await pk.daftar_komentar_aset(activity_id=KEG, _user=ADMIN_A)
    r = _jalan(skenario())
    assert r["jumlah"] == 1 and r["items"][0]["asset_id"] == "aset-1"


# ── Stempel asal pada kontribusi baru ──────────────────────────────────────

def test_kontribusi_baru_distempel_satker_dan_kegiatan(dbx):
    """Tanpa stempel ini setiap kueri lintas-share terpaksa menjoin dokumen
    share lebih dulu; satu kueri yang lupa menjoin = kebocoran lintas-satker."""
    assert pk._stempel_asal({"kode_satker": "111111", "activity_id": KEG}) == {
        "kode_satker": "111111", "activity_id": KEG}
    assert pk._stempel_asal({}) == {"kode_satker": "", "activity_id": ""}


# ══════════════════════════════════════════════════════════════════════════
# USULAN GESER — tamu memindahkan marker aset ASLI
# ══════════════════════════════════════════════════════════════════════════
#
# Mandat pemilik: tamu boleh menggeser marker asli; garis putus-putus + marker
# transparan menandai usulannya; "akan berubah ketika disetujui".
#
# KEPUTUSAN YANG DIKUNCI UJI DI SINI: menggeser TIDAK langsung mengubah
# koordinat aset. Pemegang tautan peta kolaborasi adalah siapa saja yang
# menerima tautannya — menulis langsung ke `assets` berarti siapa pun yang
# meneruskan tautan bisa memindahkan titik BMN resmi tanpa jejak persetujuan.

# Konteks TAMU lengkap: penjaga kontribusi memeriksa klaim token (share + jti)
# dan membaca ?token= dari query. Uji yang memakai ctx setengah jadi hanya akan
# menguji penolakan tokennya, bukan perilaku yang kita maksud.
TAMU = {"guest": True, "peta": {"share": SHARE_ID, "jti": "j1"}}


class _Req:
    """Request seadanya: `_punya_link` membaca query_params, `request.client`
    dipakai mencatat IP penyumbang."""

    def __init__(self, token=None):
        # Token PETA yang benar-benar sah — `_punya_link` mendekodenya, jadi
        # string asal-asalan hanya akan menguji penolakan token.
        from auth_utils import create_map_token
        self.query_params = {"token": token or create_map_token(SHARE_ID, "j1")}
        self.client = None


async def _aset(dbx, aid="a-1", lat="-0.9000000", lng="116.7000000", **ganti):
    doc = {"id": aid, "activity_id": KEG, "kode_satker": "111111",
           "asset_code": "3100102001", "NUP": "7", "asset_name": "Genset",
           "koordinat_latitude": lat, "koordinat_longitude": lng,
           "version": 3, "dihapus": False}
    doc.update(ganti)
    await dbx.assets.insert_one(doc)
    return doc


def test_geser_oleh_tamu_TIDAK_langsung_mengubah_aset(dbx):
    """INTI. Yang tersimpan adalah USULAN; koordinat aset belum bergerak."""
    async def skenario():
        await _seed(dbx)
        await _aset(dbx)
        r = await _unwrap(pk.usul_geser_titik)(
            SHARE_ID, pk.GeserIn(asset_id="a-1", lat=-0.95, lng=116.75,
                                 oleh="Budi"),
            request=_Req(), ctx=TAMU)
        aset = await dbx.assets.find_one({"id": "a-1"}, {"_id": 0})
        return r, aset
    r, aset = _jalan(skenario())
    assert r["jenis"] == "geser" and r["status_usulan"] == "terbuka"
    # Posisi ASAL ikut disimpan → garis putus-putus punya pangkal.
    assert r["lat_asal"] == -0.9 and r["lng_asal"] == 116.7
    assert aset["koordinat_latitude"] == "-0.9000000", "aset belum boleh pindah"
    assert aset["version"] == 3


def test_geser_disetujui_benar_benar_memindahkan_aset(dbx):
    """"…akan berubah ketika disetujui" — dibuktikan sampai ke dokumen aset."""
    async def skenario():
        await _seed(dbx)
        await _aset(dbx)
        u = await _unwrap(pk.usul_geser_titik)(
            SHARE_ID, pk.GeserIn(asset_id="a-1", lat=-0.95, lng=116.75),
            request=_Req(), ctx=TAMU)
        r = await _unwrap(pk.setujui_usulan)(SHARE_ID, u["id"], request=None,
                                             user=ADMIN_A)
        return r, await dbx.assets.find_one({"id": "a-1"}, {"_id": 0})
    r, aset = _jalan(skenario())
    assert r["jenis"] == "geser" and r["aset_id"] == "a-1"
    assert aset["koordinat_latitude"].startswith("-0.95")
    assert aset["koordinat_longitude"].startswith("116.75")
    assert aset["version"] == 4, "OCC harus naik agar klien tahu data berubah"
    # Jejak balik: dari mana ia dipindah & atas usulan siapa.
    assert aset["geser_dari"]["lat"] == "-0.9000000"
    assert aset["geser_dari"]["disetujui_oleh"] == "a"


def test_geser_memindahkan_geo_bukan_hanya_koordinat(dbx):
    """`geo` (indeks 2dsphere) harus ikut. Kalau tidak, aset tetap muncul di
    kueri area pada titik LAMANYA — peta benar, pencarian spasial diam-diam
    salah."""
    async def skenario():
        await _seed(dbx)
        await _aset(dbx)
        u = await _unwrap(pk.usul_geser_titik)(
            SHARE_ID, pk.GeserIn(asset_id="a-1", lat=-0.95, lng=116.75),
            request=_Req(), ctx=TAMU)
        await _unwrap(pk.setujui_usulan)(SHARE_ID, u["id"], request=None,
                                         user=ADMIN_A)
        return await dbx.assets.find_one({"id": "a-1"}, {"_id": 0})
    aset = _jalan(skenario())
    koord = (aset.get("geo") or {}).get("coordinates") or []
    assert len(koord) == 2
    assert abs(koord[0] - 116.75) < 1e-6 and abs(koord[1] + 0.95) < 1e-6


def test_geser_aset_kegiatan_lain_ditolak_404(dbx):
    """Tautan peta tak boleh jadi pintu menggeser aset kegiatan/satker lain."""
    async def skenario():
        await _seed(dbx)
        await _aset(dbx, "a-lain", activity_id="keg-lain", kode_satker="222222")
        await _unwrap(pk.usul_geser_titik)(
            SHARE_ID, pk.GeserIn(asset_id="a-lain", lat=-0.95, lng=116.75),
            request=_Req(), ctx=TAMU)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 404


def test_koordinat_ngawur_ditolak(dbx):
    async def skenario():
        await _seed(dbx)
        await _aset(dbx)
        await _unwrap(pk.usul_geser_titik)(
            SHARE_ID, pk.GeserIn(asset_id="a-1", lat=999, lng=116.7),
            request=_Req(), ctx=TAMU)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 400


def test_menyeret_berkali_kali_tak_menumpuk_garis(dbx):
    """Satu penyumbang, satu usulan geser per aset. Tanpa ini, orang yang
    menyeret marker lima kali meninggalkan lima garis putus-putus ke titik
    yang sama dan pengelola harus meninjau lima usulan identik."""
    async def skenario():
        await _seed(dbx)
        await _aset(dbx)
        for lat in (-0.91, -0.92, -0.93):
            await _unwrap(pk.usul_geser_titik)(
                SHARE_ID, pk.GeserIn(asset_id="a-1", lat=lat, lng=116.75,
                                     oleh="Budi"),
                request=_Req(), ctx=TAMU)
        return await pk.daftar_usulan_geser(activity_id=KEG, _user=ADMIN_A)
    r = _jalan(skenario())
    assert r["jumlah"] == 1, "usulan lama harus digantikan, bukan menumpuk"
    assert abs(r["items"][0]["lat"] + 0.93) < 1e-9, "yang tersisa yang TERBARU"


def test_penyumbang_berbeda_boleh_punya_usulan_masing_masing(dbx):
    """Penggantian di atas hanya berlaku per ORANG — usul Wati tak boleh
    menghapus usul Budi."""
    async def skenario():
        await _seed(dbx)
        await _aset(dbx)
        await _unwrap(pk.usul_geser_titik)(
            SHARE_ID, pk.GeserIn(asset_id="a-1", lat=-0.91, lng=116.7, oleh="Budi"),
            request=_Req(), ctx=TAMU)
        await _unwrap(pk.usul_geser_titik)(
            SHARE_ID, pk.GeserIn(asset_id="a-1", lat=-0.92, lng=116.7, oleh="Wati"),
            request=_Req(), ctx=TAMU)
        return await pk.daftar_usulan_geser(activity_id=KEG, _user=ADMIN_A)
    r = _jalan(skenario())
    assert r["jumlah"] == 2
    assert {x["oleh"] for x in r["items"]} == {"Budi", "Wati"}


def test_peta_asli_hanya_menampilkan_usulan_yang_masih_menunggu(dbx):
    """Garis putus-putus harus HILANG setelah usulannya disetujui — kalau
    tidak, peta asli menyisakan bayangan yang menunjuk posisi lama selamanya."""
    async def skenario():
        await _seed(dbx)
        await _aset(dbx)
        u = await _unwrap(pk.usul_geser_titik)(
            SHARE_ID, pk.GeserIn(asset_id="a-1", lat=-0.95, lng=116.75),
            request=_Req(), ctx=TAMU)
        sebelum = await pk.daftar_usulan_geser(activity_id=KEG, _user=ADMIN_A)
        await _unwrap(pk.setujui_usulan)(SHARE_ID, u["id"], request=None,
                                         user=ADMIN_A)
        sesudah = await pk.daftar_usulan_geser(activity_id=KEG, _user=ADMIN_A)
        return sebelum, sesudah
    sebelum, sesudah = _jalan(skenario())
    assert sebelum["jumlah"] == 1 and sesudah["jumlah"] == 0


def test_usulan_geser_tak_bocor_ke_kegiatan_lain(dbx):
    async def skenario():
        await _seed(dbx)
        await _aset(dbx)
        await _unwrap(pk.usul_geser_titik)(
            SHARE_ID, pk.GeserIn(asset_id="a-1", lat=-0.95, lng=116.75),
            request=_Req(), ctx=TAMU)
        # Kegiatan LAIN yang benar-benar ada & milik satker yang sama —
        # kalau tidak, yang teruji cuma penjaga data yatim, bukan penyaringan
        # per kegiatan yang kita maksud.
        await dbx.inventory_activities.insert_one(
            {"id": "keg-2", "kode_satker": "111111", "nama": "Kegiatan lain"})
        return await pk.daftar_usulan_geser(activity_id="keg-2", _user=ADMIN_A)
    assert _jalan(skenario())["jumlah"] == 0


def test_geser_aset_yang_keburu_hilang_dilewati_dengan_sebab(dbx):
    """Aset dihapus setelah usulan dibuat: batch tak boleh meledak, dan
    usulannya tak boleh diam-diam ditandai selesai."""
    async def skenario():
        await _seed(dbx)
        await _aset(dbx)
        u = await _unwrap(pk.usul_geser_titik)(
            SHARE_ID, pk.GeserIn(asset_id="a-1", lat=-0.95, lng=116.75),
            request=_Req(), ctx=TAMU)
        await dbx.assets.delete_one({"id": "a-1"})
        r = await _unwrap(pk.setujui_semua_usulan)(
            SHARE_ID, pk.SetujuiSemuaIn(), request=None, user=ADMIN_A)
        tetap = await dbx.peta_kolaborasi.find_one({"id": u["id"]}, {"_id": 0})
        return r, tetap
    r, tetap = _jalan(skenario())
    assert r["disetujui"] == 0 and len(r["dilewati"]) == 1
    assert "tidak ada" in r["dilewati"][0]["alasan"].lower()
    assert pk._status_usulan(tetap) == "terbuka", "jangan ditandai selesai"
