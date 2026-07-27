"""Uji ENDPOINT opname scan (Fase 11) — Mongo in-process, tanpa jaringan.

Helper murninya sudah diuji terpisah; yang diperiksa di sini justru hal-hal yang
HANYA muncul saat handler benar-benar berjalan: resolusi kode ke aset yang
benar, penolakan kode ambigu, jaring anti-replay antrean luring, dan janji
terpenting fase ini — bahwa memindai TIDAK diam-diam memindahkan catatan lokasi.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.opname as ro
import routes.perencanaan as rp  # noqa: F401 (fixture db bersama)

# kode_satker "" = super-admin lintas satker → guard akses no-op, sehingga uji
# ini fokus pada logika opname (isolasi satker punya uji sendiri di modul lain).
USER = {"username": "petugas", "role": "admin", "kode_satker": ""}


class _Req:
    def __init__(self):
        self.headers = {}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


def rp_rekon():
    """Handler rekonsiliasi — dibungkus fungsi agar unwrap terjadi saat uji."""
    return ro.rekonsiliasi


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(ro, "db", fake)
    monkeypatch.setattr(ro, "log_audit", _diam)
    import shared_utils as su_mod
    monkeypatch.setattr(su_mod, "db", fake)
    return fake


async def _seed(dbx):
    """Satu gedung → satu lantai → dua ruangan, plus tiga aset."""
    await dbx.spasial_node.insert_many([
        {"id": "gedA", "nama": "Gedung A", "tipe": "gedung", "status": "aktif",
         "kode_satker": "", "ancestors": [], "ancestors_nama": []},
        {"id": "lt3", "nama": "Lantai 3", "tipe": "lantai", "status": "aktif",
         "kode_satker": "", "ancestors": ["gedA"], "ancestors_nama": ["Gedung A"]},
        {"id": "r305", "nama": "Ruang 305", "tipe": "ruangan", "status": "aktif",
         "kode_satker": "", "ancestors": ["gedA", "lt3"],
         "ancestors_nama": ["Gedung A", "Lantai 3"]},
        {"id": "r307", "nama": "Ruang 307", "tipe": "ruangan", "status": "aktif",
         "kode_satker": "", "ancestors": ["gedA", "lt3"],
         "ancestors_nama": ["Gedung A", "Lantai 3"]},
    ])
    await dbx.assets.insert_many([
        {"id": "a1", "activity_id": "keg1", "asset_code": "3.05.01.05.007",
         "NUP": "12", "asset_name": "Meja Rapat",
         "lokasi_spasial": {"node_id": "r305", "node_nama": "Ruang 305",
                            "jalur_nama": "Gedung A / Lantai 3 / Ruang 305",
                            "titik": [116.7, -1.4]}},
        {"id": "a2", "activity_id": "keg1", "asset_code": "3.05.01.05.007",
         "NUP": "13", "asset_name": "Meja Rapat 2"},
        {"id": "a3", "activity_id": "keg1", "asset_code": "3.10.01.02.001",
         "NUP": "", "asset_name": "Printer"},
    ])


async def _scan(**kw):
    body = ro.ScanIn(**kw)
    return await _unwrap(ro.catat_scan)(_Req(), body, USER)


class TestResolusiKode:
    def test_stiker_kode_nup_menemukan_aset_yang_tepat(self, dbx):
        async def jalan():
            await _seed(dbx)
            r = await _scan(kode="#3.05.01.05.007-12", node_id="r305",
                            scan_id="s1")
            return r
        r = _jalan(jalan())
        assert r["scan"]["asset_id"] == "a1"
        assert r["scan"]["status_rekonsiliasi"] == "sesuai"

    def test_stiker_ber_NUP_KOSONG_tercetak_nol_tetap_terpindai(self, dbx):
        # routes/stiker.py mencetak `nup or '0'`. Aset ber-NUP kosong karenanya
        # menghasilkan "-0"; tanpa cabang khusus stiker itu abadi tak terbaca.
        async def jalan():
            await _seed(dbx)
            return await _scan(kode="#3.10.01.02.001-0", node_id="r305",
                               scan_id="s2")
        r = _jalan(jalan())
        assert r["scan"]["asset_id"] == "a3"

    def test_kode_ambigu_TIDAK_ditebak_melainkan_409_berisi_kandidat(self, dbx):
        from fastapi import HTTPException

        async def jalan():
            await _seed(dbx)
            # Kode barang tanpa NUP cocok dengan dua aset (NUP 12 & 13).
            await _scan(kode="3.05.01.05.007", node_id="r305", scan_id="s3")
        with pytest.raises(HTTPException) as ex:
            _jalan(jalan())
        assert ex.value.status_code == 409
        assert len(ex.value.detail["kandidat"]) == 2

    def test_pilihan_aset_wajib_berasal_dari_kode_yang_dipindai(self, dbx):
        # Tanpa penjaga ini `asset_id` menjadi jalan mencatat scan palsu untuk
        # aset mana pun tanpa pernah menyentuh stikernya.
        from fastapi import HTTPException

        async def jalan():
            await _seed(dbx)
            await _scan(kode="3.05.01.05.007", node_id="r305", scan_id="s4",
                        asset_id="a3")
        with pytest.raises(HTTPException) as ex:
            _jalan(jalan())
        assert ex.value.status_code == 400

    def test_pilihan_aset_yang_sah_diterima(self, dbx):
        async def jalan():
            await _seed(dbx)
            return await _scan(kode="3.05.01.05.007", node_id="r305",
                               scan_id="s5", asset_id="a2")
        assert _jalan(jalan())["scan"]["asset_id"] == "a2"

    def test_kode_tak_dikenal_menjelaskan_sebabnya(self, dbx):
        from fastapi import HTTPException

        async def jalan():
            await _seed(dbx)
            await _scan(kode="#TIDAK-ADA-9", node_id="r305", scan_id="s6")
        with pytest.raises(HTTPException) as ex:
            _jalan(jalan())
        assert ex.value.status_code == 404


class TestIdempotensiAntreanLuring:
    def test_pengiriman_ulang_scan_id_yang_sama_tak_menggandakan(self, dbx):
        # Indeks unik `opname_scan_idem` adalah penegak sebenarnya; jalur cepat
        # inilah yang diuji di sini (mongomock tak menegakkan indeks unik).
        async def jalan():
            await _seed(dbx)
            a = await _scan(kode="#3.05.01.05.007-12", node_id="r305",
                            scan_id="antre-1")
            b = await _scan(kode="#3.05.01.05.007-12", node_id="r305",
                            scan_id="antre-1")
            n = await dbx.opname_scan.count_documents({})
            return a, b, n
        a, b, n = _jalan(jalan())
        assert a["duplikat"] is False and b["duplikat"] is True
        assert b["scan"]["id"] == a["scan"]["id"]
        assert n == 1

    def test_pindaian_sengaja_kedua_adalah_catatan_baru(self, dbx):
        async def jalan():
            await _seed(dbx)
            await _scan(kode="#3.05.01.05.007-12", node_id="r305", scan_id="x1")
            await _scan(kode="#3.05.01.05.007-12", node_id="r307", scan_id="x2")
            return await dbx.opname_scan.count_documents({})
        assert _jalan(jalan()) == 2


class TestWaktuScan:
    def test_jam_klien_ber_offset_disimpan_dalam_UTC(self, dbx):
        # `pada` dibandingkan sebagai STRING (filter periode & pemilihan scan
        # terbaru). HP Indonesia mengirim +07:00; tanpa normalisasi
        # "08:00+07:00" tampak lebih besar daripada "09:00+00:00" yang
        # sebenarnya terjadi dua jam kemudian.
        async def jalan():
            await _seed(dbx)
            r = await _scan(kode="#3.05.01.05.007-12", node_id="r305",
                            scan_id="tz1", ts_scan="2026-07-27T08:00:00+07:00")
            return r["scan"]["pada"]
        assert _jalan(jalan()) == "2026-07-27T01:00:00+00:00"

    def test_jam_klien_dari_masa_depan_dijatuhkan_ke_waktu_server(self, dbx):
        async def jalan():
            await _seed(dbx)
            r = await _scan(kode="#3.05.01.05.007-12", node_id="r305",
                            scan_id="tz2", ts_scan="2099-01-01T00:00:00+00:00")
            return r["scan"]
        s = _jalan(jalan())
        assert s["pada"] == s["diterima_pada"]

    def test_ts_scan_sampah_tak_menggagalkan_pencatatan(self, dbx):
        async def jalan():
            await _seed(dbx)
            return await _scan(kode="#3.05.01.05.007-12", node_id="r305",
                               scan_id="tz3", ts_scan="bukan tanggal")
        assert _jalan(jalan())["scan"]["pada"]


class TestScanTidakMemindahkan:
    def test_scan_di_ruangan_lain_TIDAK_mengubah_lokasi_aset(self, dbx):
        # Janji inti fase ini: opname MEMERIKSA, bukan menulis ulang buku.
        async def jalan():
            await _seed(dbx)
            r = await _scan(kode="#3.05.01.05.007-12", node_id="r307",
                            scan_id="p1")
            aset = await dbx.assets.find_one({"id": "a1"}, {"_id": 0})
            return r, aset
        r, aset = _jalan(jalan())
        assert r["scan"]["status_rekonsiliasi"] == "pindah"
        assert r["perlu_dipindahkan"] is True
        assert aset["lokasi_spasial"]["node_id"] == "r305"   # buku BELUM berubah

    def test_scan_di_level_gedung_mengukuhkan_bukan_memindah(self, dbx):
        # Buku: Ruang 305 (di dalam Gedung A). Menganggapnya "pindah" lalu
        # menerapkannya akan MENURUNKAN presisi ruangan menjadi gedung.
        async def jalan():
            await _seed(dbx)
            return await _scan(kode="#3.05.01.05.007-12", node_id="gedA",
                               scan_id="p2")
        r = _jalan(jalan())
        assert r["scan"]["status_rekonsiliasi"] == "sesuai"
        assert r["perlu_dipindahkan"] is False

    def test_aset_belum_pernah_ditempatkan_berstatus_baru(self, dbx):
        async def jalan():
            await _seed(dbx)
            return await _scan(kode="#3.10.01.02.001-0", node_id="r307",
                               scan_id="p3")
        assert _jalan(jalan())["scan"]["status_rekonsiliasi"] == "baru"


class TestTerapkan:
    async def _siapkan_pindah(self, dbx):
        await _seed(dbx)
        r = await _scan(kode="#3.05.01.05.007-12", node_id="r307", scan_id="t1")
        return r["scan"]["id"]

    def test_perpindahan_diterapkan_beserta_baris_riwayat(self, dbx):
        async def jalan():
            sid = await self._siapkan_pindah(dbx)
            hasil = await _unwrap(ro.terapkan_perpindahan)(
                _Req(), ro.TerapkanIn(scan_ids=[sid]), USER)
            aset = await dbx.assets.find_one({"id": "a1"}, {"_id": 0})
            riwayat = await dbx.riwayat_lokasi_aset.count_documents({})
            return hasil, aset, riwayat
        hasil, aset, riwayat = _jalan(jalan())
        assert hasil["jumlah_diterapkan"] == 1
        assert aset["lokasi_spasial"]["node_id"] == "r307"
        assert aset["lokasi_spasial"]["sumber"] == "scan_qr"
        assert riwayat == 1

    def test_terap_kedua_dilewati_dan_tak_menambah_riwayat(self, dbx):
        # Menekan tombol dua kali tak boleh melahirkan dua baris riwayat untuk
        # satu kejadian fisik yang sama.
        async def jalan():
            sid = await self._siapkan_pindah(dbx)
            terap = _unwrap(ro.terapkan_perpindahan)
            await terap(_Req(), ro.TerapkanIn(scan_ids=[sid]), USER)
            kedua = await terap(_Req(), ro.TerapkanIn(scan_ids=[sid]), USER)
            return kedua, await dbx.riwayat_lokasi_aset.count_documents({})
        kedua, riwayat = _jalan(jalan())
        assert kedua["jumlah_diterapkan"] == 0
        assert kedua["dilewati"][0]["alasan"] == "sudah diterapkan"
        assert riwayat == 1

    def test_scan_berstatus_sesuai_tak_ikut_diterapkan(self, dbx):
        async def jalan():
            await _seed(dbx)
            r = await _scan(kode="#3.05.01.05.007-12", node_id="r305",
                            scan_id="t2")
            return await _unwrap(ro.terapkan_perpindahan)(
                _Req(), ro.TerapkanIn(scan_ids=[r["scan"]["id"]]), USER)
        hasil = _jalan(jalan())
        assert hasil["jumlah_diterapkan"] == 0
        assert "sesuai" in hasil["dilewati"][0]["alasan"]

    def test_daftar_kosong_ditolak(self, dbx):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ex:
            _jalan(_unwrap(ro.terapkan_perpindahan)(
                _Req(), ro.TerapkanIn(scan_ids=[]), USER))
        assert ex.value.status_code == 400


class TestRekonsiliasi:
    def test_tiga_keranjang_dari_data_nyata(self, dbx):
        async def jalan():
            await _seed(dbx)
            # a1 tercatat di r305 dan terpindai di sana → sesuai.
            await _scan(kode="#3.05.01.05.007-12", node_id="r305", scan_id="k1")
            # a3 belum punya lokasi tetapi terpindai di r305 → pindah_masuk.
            await _scan(kode="#3.10.01.02.001-0", node_id="r305", scan_id="k2")
            return await _unwrap(ro.rekonsiliasi)("r305", True, "", USER)
        r = _jalan(jalan())
        assert [x["id"] for x in r["sesuai"]] == ["a1"]
        assert [x["asset_id"] for x in r["pindah_masuk"]] == ["a3"]
        assert r["ringkas"]["persen_terkonfirmasi"] == 100.0

    def test_yang_tercatat_tapi_belum_terpindai_muncul_sebagai_daftar_kerja(self, dbx):
        async def jalan():
            await _seed(dbx)
            return await _unwrap(ro.rekonsiliasi)("r305", True, "", USER)
        r = _jalan(jalan())
        assert [x["id"] for x in r["belum_terpindai"]] == ["a1"]
        assert r["ringkas"]["persen_terkonfirmasi"] == 0.0

    def test_lingkup_gedung_mencakup_isi_ruangannya(self, dbx):
        async def jalan():
            await _seed(dbx)
            return await _unwrap(ro.rekonsiliasi)("gedA", True, "", USER)
        assert _jalan(jalan())["ringkas"]["harapan"] == 1

    def test_tanpa_keturunan_gedung_kosong(self, dbx):
        async def jalan():
            await _seed(dbx)
            return await _unwrap(ro.rekonsiliasi)("gedA", False, "", USER)
        assert _jalan(jalan())["ringkas"]["harapan"] == 0

    def test_node_tak_dikenal_404(self, dbx):
        from fastapi import HTTPException

        async def jalan():
            await _seed(dbx)
            await _unwrap(ro.rekonsiliasi)("tidak-ada", True, "", USER)
        with pytest.raises(HTTPException) as ex:
            _jalan(jalan())
        assert ex.value.status_code == 404


class TestPerpindahanDalamLingkupTakHilang:
    """Temuan audit: buka Opname di level GEDUNG (nilai bawaan `dalam=true`),
    lalu barang yang pindah ANTAR RUANGAN di dalam gedung itu punya node buku
    DAN node scan yang sama-sama di dalam lingkup — dulu ia langsung masuk
    keranjang `sesuai` dan tak pernah bisa di-Terapkan."""

    def test_pindah_antar_ruangan_muncul_sebagai_usulan_bukan_cocok(self, dbx):
        async def jalan():
            await _seed(dbx)
            # a1 tercatat di r305; petugas memindainya di r307.
            await _scan(kode="#3.05.01.05.007-12", node_id="r307", scan_id="d1")
            return await _unwrap(rp_rekon())("gedA", True, "", USER)
        r = _jalan(jalan())
        assert [x["asset_id"] for x in r["pindah_masuk"]] == ["a1"]
        assert r["sesuai"] == []
        assert r["ringkas"]["persen_terkonfirmasi"] == 0.0

    def test_setelah_diterapkan_barulah_dihitung_cocok(self, dbx):
        # Rekap harus MENYEMBUHKAN DIRI: tanpa memeriksa `diterapkan`, keranjang
        # usulan tak pernah kosong karena status scan tetap "pindah" selamanya.
        async def jalan():
            await _seed(dbx)
            s = await _scan(kode="#3.05.01.05.007-12", node_id="r307", scan_id="d2")
            await _unwrap(ro.terapkan_perpindahan)(
                _Req(), ro.TerapkanIn(scan_ids=[s["scan"]["id"]]), USER)
            return await _unwrap(rp_rekon())("gedA", True, "", USER)
        r = _jalan(jalan())
        assert r["pindah_masuk"] == []
        assert [x["id"] for x in r["sesuai"]] == ["a1"]
        assert r["ringkas"]["persen_terkonfirmasi"] == 100.0


class TestTerapkanTidakMerusak:
    def test_location_ikut_berpindah_agar_KIR_DBR_tak_tertinggal(self, dbx):
        # reports.py mencocokkan ruangan lewat STRING `location`; tanpa ini,
        # denah diperbarui tetapi DOKUMEN RESMI menyebut ruangan lama.
        async def jalan():
            await _seed(dbx)
            await dbx.assets.update_one({"id": "a1"},
                                        {"$set": {"location": "Ruang 305"}})
            s = await _scan(kode="#3.05.01.05.007-12", node_id="r307", scan_id="l1")
            await _unwrap(ro.terapkan_perpindahan)(
                _Req(), ro.TerapkanIn(scan_ids=[s["scan"]["id"]]), USER)
            aset = await dbx.assets.find_one({"id": "a1"}, {"_id": 0})
            riwayat = await dbx.riwayat_lokasi_aset.find_one({}, {"_id": 0})
            return aset, riwayat
        aset, riwayat = _jalan(jalan())
        assert aset["location"] == "Ruang 307"
        # Nilai lama tak boleh lenyap tanpa jejak.
        assert riwayat["location_lama"] == "Ruang 305"

    def test_koordinat_presisi_tak_dihapus_oleh_scan_tanpa_lat_lon(self, dbx):
        # Pemindaian dari aplikasi memilih RUANGAN, tak mengukur titik. Menulis
        # `titik: None` apa adanya menghapus koordinat yang dikumpulkan Fase 9.
        async def jalan():
            await _seed(dbx)
            s = await _scan(kode="#3.05.01.05.007-12", node_id="r307", scan_id="k1")
            await _unwrap(ro.terapkan_perpindahan)(
                _Req(), ro.TerapkanIn(scan_ids=[s["scan"]["id"]]), USER)
            return await dbx.assets.find_one({"id": "a1"}, {"_id": 0})
        assert _jalan(jalan())["lokasi_spasial"]["titik"] == [116.7, -1.4]
