"""Penempatan otomatis dari inventarisasi — integrasi yang diminta pemilik.

Permintaan (verbatim): *"kenapa juga halaman hierarki spasial harus scan
perpindahan sendiri dan tidak melalui inventarisasi aset karena berpusat
disana semua … integrasikan saja."*

Dua kelompok penjaga, dan yang kedua yang paling mudah hilang:

1. HELPER-nya BENAR — `spasial_penempatan.penempatan_dari_inventarisasi`
   menempatkan HANYA pada kondisi yang tepat: gerbang murah dulu (tanpa
   sentuhan koordinat/status Ditemukan → nol kueri), penempatan yang sudah
   ada menang, satker fail-closed, kueri node terkurung satker+aktif+gedung.
2. WIRING-nya TERPASANG — ketiga jalur tulis aset (PATCH/POST/PUT) memanggil
   helper SEBELUM tulisan (atomik) dan menulis riwayat SETELAH tulisan
   sukses. Godaan refactor: "pindahkan panggilan ke setelah CAS biar rapi" —
   itu membuat penempatan bisa tertulis untuk CAS yang kalah, atau riwayat
   mendahului kenyataan.

Kueri $geoIntersects tak bisa dievaluasi mongomock — bentuk KUERINYA yang
diuji lewat DB palsu perekam, bukan hasil geometrinya (itu tugas MongoDB
sungguhan + indeks 2dsphere yang sudah dijaga indexes.py).
"""
import ast
import asyncio
import os

import spasial_penempatan as sp

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
with open(os.path.join(BACKEND, "routes", "assets.py"), encoding="utf-8") as f:
    SRC_ASSETS = f.read()
with open(os.path.join(BACKEND, "spasial_penempatan.py"), encoding="utf-8") as f:
    SRC_MODUL = f.read()


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


# ── DB palsu perekam ────────────────────────────────────────────────────────

class _Kursor:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, *a, **k):
        return self

    async def to_list(self, n):
        return list(self._rows)[:n]


class _Koleksi:
    def __init__(self, rows=None, satu=None):
        self.rows = rows or []
        self.satu = satu
        self.kueri_terakhir = None
        self.panggilan = 0

    def find(self, q, proj=None):
        self.panggilan += 1
        self.kueri_terakhir = q
        return _Kursor(self.rows)

    async def find_one(self, q, proj=None):
        self.panggilan += 1
        self.kueri_terakhir = q
        return self.satu


class _Db:
    def __init__(self, keg=None, node_rows=None):
        self.inventory_activities = _Koleksi(satu=keg)
        self.spasial_node = _Koleksi(rows=node_rows or [])


KEG = {"kode_satker": "111111"}
GEDUNG = {"id": "g1", "tipe": "GEDUNG", "nama": "Gedung A", "ordinal_level": 80,
          "ancestors": ["kw1"], "ancestors_nama": ["Kawasan Inti"],
          "metrik": {"luas_m2": 900.0}}
KAWASAN = {"id": "kw1", "tipe": "KAWASAN", "nama": "Kawasan Inti",
           "ordinal_level": 20, "ancestors": [], "ancestors_nama": [],
           "metrik": {"luas_m2": 90000.0}}


def _panggil(db, existing, update, username="op", now="2026-08-06T00:00:00"):
    sp_db_asli = sp.db
    sp.db = db
    try:
        return _jalan(sp.penempatan_dari_inventarisasi(
            existing, update, username, now))
    finally:
        sp.db = sp_db_asli


class TestGerbangMurah:
    """PATCH foto/harga/dll. tidak boleh membayar kueri geo apa pun."""

    def test_tanpa_koordinat_tanpa_ditemukan_nol_kueri(self):
        db = _Db(keg=KEG, node_rows=[GEDUNG])
        hasil = _panggil(db, {"activity_id": "k1"}, {"purchase_price": "1"})
        assert hasil is None
        assert db.inventory_activities.panggilan == 0
        assert db.spasial_node.panggilan == 0

    def test_penempatan_yang_ada_menang(self):
        """Manual, hasil opname, maupun otomatis sebelumnya — GPS yang
        bergetar antar pemotretan tak boleh jadi 'perpindahan'."""
        db = _Db(keg=KEG, node_rows=[GEDUNG])
        hasil = _panggil(
            db,
            {"activity_id": "k1",
             "lokasi_spasial": {"node_id": "r9", "titik": [116.7, -0.97]}},
            {"koordinat_latitude": "-0.975", "koordinat_longitude": "116.709"})
        assert hasil is None
        assert db.spasial_node.panggilan == 0

    def test_koordinat_tak_sah_dilewati(self):
        db = _Db(keg=KEG, node_rows=[GEDUNG])
        hasil = _panggil(db, {"activity_id": "k1"},
                         {"koordinat_latitude": "abc",
                          "koordinat_longitude": "116.709"})
        assert hasil is None
        assert db.spasial_node.panggilan == 0


class TestSatkerFailClosed:
    def test_tanpa_kegiatan_dilewati(self):
        db = _Db(keg=KEG, node_rows=[GEDUNG])
        hasil = _panggil(db, {"activity_id": ""},
                         {"koordinat_latitude": "-0.975",
                          "koordinat_longitude": "116.709"})
        assert hasil is None
        assert db.spasial_node.panggilan == 0

    def test_kegiatan_tanpa_kode_dilewati(self):
        """JANGAN meniru cabang kode-kosong-tanpa-filter milik
        scope_query_field_satker — itu privilese super-admin; di hook artinya
        menempatkan aset ke gedung satker lain."""
        db = _Db(keg={"kode_satker": ""}, node_rows=[GEDUNG])
        hasil = _panggil(db, {"activity_id": "k1"},
                         {"koordinat_latitude": "-0.975",
                          "koordinat_longitude": "116.709"})
        assert hasil is None
        assert db.spasial_node.panggilan == 0


class TestKueriDanHasil:
    def test_kueri_terkurung_satker_aktif_dan_berhenti_di_gedung(self):
        db = _Db(keg=KEG, node_rows=[KAWASAN, GEDUNG])
        _panggil(db, {"activity_id": "k1"},
                 {"koordinat_latitude": "-0.975",
                  "koordinat_longitude": "116.709"})
        q = db.spasial_node.kueri_terakhir
        assert q["kode_satker"] == {"$in": ["111111", "", None]}
        assert q["status"] == "aktif"
        assert q["ordinal_level"] == {"$lte": 80}
        geom = q["geometry"]["$geoIntersects"]["$geometry"]
        assert geom["type"] == "Point"
        assert geom["coordinates"] == [116.709, -0.975]   # lon-first (GeoJSON)

    def test_lokasi_dari_node_terdalam_dengan_jejak_sumber(self):
        db = _Db(keg=KEG, node_rows=[KAWASAN, GEDUNG])
        hasil = _panggil(db, {"activity_id": "k1"},
                         {"koordinat_latitude": "-0.975",
                          "koordinat_longitude": "116.709"},
                         username="petugas", now="2026-08-06T01:02:03")
        assert hasil["node_id"] == "g1"
        assert hasil["jalur_nama"] == "Kawasan Inti / Gedung A"
        assert hasil["titik"] == [116.709, -0.975]
        assert hasil["sumber"] == "inventarisasi"
        assert hasil["ditandai_oleh"] == "petugas"
        assert hasil["ditandai_pada"] == "2026-08-06T01:02:03"

    def test_di_luar_semua_poligon_dilewati_diam(self):
        """Aset lapangan terbuka itu sah — tanpa node, tanpa riwayat palsu."""
        db = _Db(keg=KEG, node_rows=[])
        hasil = _panggil(db, {"activity_id": "k1"},
                         {"koordinat_latitude": "-0.975",
                          "koordinat_longitude": "116.709"})
        assert hasil is None

    def test_status_ditemukan_memakai_koordinat_tersimpan(self):
        """Koordinat direkam kemarin, status Ditemukan hari ini — pemicu
        kedua ini yang membuat 'setiap kegiatan diinventarisasi' benar-benar
        menempatkan."""
        db = _Db(keg=KEG, node_rows=[GEDUNG])
        hasil = _panggil(db,
                         {"activity_id": "k1",
                          "koordinat_latitude": "-0.975",
                          "koordinat_longitude": "116.709"},
                         {"inventory_status": "Ditemukan"})
        assert hasil is not None and hasil["node_id"] == "g1"


def _fungsi_assets(nama: str) -> str:
    pohon = ast.parse(SRC_ASSETS)
    for simpul in ast.walk(pohon):
        if (isinstance(simpul, (ast.FunctionDef, ast.AsyncFunctionDef))
                and simpul.name == nama):
            return ast.get_source_segment(SRC_ASSETS, simpul) or ""
    raise AssertionError(f"fungsi {nama} tidak ditemukan")


class TestWiringTerpasang:
    """Urutan panggilan = kontrak atomisitas. Diuji per-fungsi via AST."""

    def test_patch_menempatkan_sebelum_cas_dan_riwayat_sesudahnya(self):
        fn = _fungsi_assets("patch_asset")
        i_hook = fn.index("penempatan_dari_inventarisasi")
        i_cas = fn.index("db.assets.update_one")
        i_riwayat = fn.index("sp.catat_penempatan(")
        assert i_hook < i_cas < i_riwayat
        # Aksi auditnya kini hidup di helper bersama (satu tempat untuk
        # ketiga jalur) — dan namanya harus persis yang disaring Timeline
        # lewat AKSI_SUDAH_DI_BAGIAN_LOKASI, kalau tidak tiap penempatan
        # otomatis tampil dua kali di riwayat aset.
        assert '"aset_lokasi_otomatis"' in SRC_MODUL
        from routes.timeline import AKSI_SUDAH_DI_BAGIAN_LOKASI
        assert "aset_lokasi_otomatis" in AKSI_SUDAH_DI_BAGIAN_LOKASI

    def test_create_menempatkan_sebelum_insert_dan_riwayat_sesudahnya(self):
        fn = _fungsi_assets("create_asset")
        i_hook = fn.index("penempatan_dari_inventarisasi")
        i_insert = fn.index("db.assets.insert_one")
        i_riwayat = fn.index("sp.catat_penempatan(")
        assert i_hook < i_insert < i_riwayat

    def test_hasil_hook_benar_benar_ditulis_ke_dokumen(self):
        """Celah uji yang ditemukan tinjauan: seluruh suite tetap hijau saat
        baris yang MENEMPATKAN aset dicabut. Hook boleh dipanggil, urutannya
        boleh benar, tapi bila hasilnya tak pernah masuk ke dokumen/update
        maka fiturnya tak melakukan apa pun — dan tak ada yang berteriak."""
        assert 'update_data["lokasi_spasial"] = lokasi_otomatis' in \
            _fungsi_assets("patch_asset")
        assert 'asset_doc["lokasi_spasial"] = lokasi_otomatis' in \
            _fungsi_assets("create_asset")
        assert 'update_data["lokasi_spasial"] = lokasi_otomatis' in \
            _fungsi_assets("update_asset")

    def test_jejak_pasca_simpan_lewat_helper_best_effort(self):
        """Aset SUDAH tersimpan saat jejak ditulis. Insert riwayat telanjang
        (tanpa try/except) membalas 500 atas tulisan yang BERHASIL — dan
        antrean luring akan mengirim ulang permintaan yang sudah sukses."""
        for nama in ("patch_asset", "create_asset", "update_asset"):
            fn = _fungsi_assets(nama)
            assert "sp.catat_penempatan(" in fn, nama
            # Insert riwayat telanjang tak boleh kembali ke jalur ini.
            assert "db.riwayat_lokasi_aset.insert_one" not in fn, nama
        assert "except Exception" in SRC_MODUL

    def test_put_menutup_celah_geo_dan_ikut_menempatkan(self):
        """Celah lama: PUT full-replace tak pernah menghitung ulang `geo` —
        indeks 2dsphere menyimpan titik basi setelah koordinat diedit."""
        fn = _fungsi_assets("update_asset")
        assert "sisip_geo_ke_update(existing, update_data)" in fn
        assert '_ops["$unset"] = _geo_unset' in fn
        i_hook = fn.index("penempatan_dari_inventarisasi")
        i_cas = fn.index("db.assets.update_one")
        assert i_hook < i_cas
        assert "sp.catat_penempatan(" in fn


class TestInvarianYangMenopangKeamanannya:
    """Dua fakta di luar modul ini yang membuat hook-nya AMAN. Keduanya
    mudah berubah diam-diam oleh perubahan yang tampak tak berhubungan,
    dan tak satu pun akan ketahuan dari uji perilaku helper."""

    def test_put_tak_bisa_menghapus_penempatan_karena_model_tak_punya_fieldnya(self):
        """PUT adalah full-replace: `update_data = {**asset.model_dump(), …}`.
        Ia aman HANYA karena `AssetCreate` tidak memuat `lokasi_spasial` —
        seandainya field itu ditambahkan ke model masukan, setiap PUT dari
        klien yang tak mengirimkannya akan mengirim `lokasi_spasial: None`
        dan MENGHAPUS penempatan denah yang tersimpan (kehilangan data
        senyap, termasuk yang dibuat operator lewat dialog Denah)."""
        import ast as _ast
        with open(os.path.join(BACKEND, "models.py"), encoding="utf-8") as fh:
            pohon = _ast.parse(fh.read())
        for simpul in _ast.walk(pohon):
            if isinstance(simpul, _ast.ClassDef) and simpul.name == "AssetCreate":
                medan = [getattr(f.target, "id", "") for f in simpul.body
                         if isinstance(f, _ast.AnnAssign)]
                assert "lokasi_spasial" not in medan, (
                    "AssetCreate kini memuat lokasi_spasial — PUT akan "
                    "menghapus penempatan denah; kecualikan field itu dari "
                    "update_data di update_asset sebelum menambahkannya.")
                return
        raise AssertionError("kelas AssetCreate tidak ditemukan")

    def test_replay_idempoten_keluar_sebelum_hook_sehingga_riwayat_tak_dobel(self):
        """Antrean luring MENGIRIM ULANG permintaan yang sama (Idempotency-Key).
        Bila cabang replay dipindah ke bawah hook, satu penempatan yang sama
        akan mencetak DUA baris riwayat custody — bukti penatausahaan BMN
        yang mengaku barang berpindah padahal tidak."""
        for nama in ("patch_asset", "create_asset"):
            fn = _fungsi_assets(nama)
            i_replay = fn.index("get_idempotent_response")
            i_hook = fn.index("penempatan_dari_inventarisasi")
            i_riwayat = fn.index("sp.catat_penempatan(")
            assert i_replay < i_hook < i_riwayat, nama


class TestModulTetapSederhana:
    """Afordansi interaktif TIDAK boleh menyusup ke jalur otomatis."""

    def test_fail_closed_tertulis_di_kueri_node(self):
        assert '"$in": [kode_satker, "", None]' in SRC_MODUL
        assert "if not kode_satker:" in SRC_MODUL

    def test_tanpa_afordansi_interaktif(self):
        # Hitung-draft dan cari-terdekat milik endpoint interaktif; di hook
        # keduanya berarti kueri ekstra pada SETIAP patch inventarisasi.
        assert "$near" not in SRC_MODUL
        assert '"status": "draft"' not in SRC_MODUL

    def test_berhenti_di_gedung(self):
        assert "ORDINAL_GEDUNG = 80" in SRC_MODUL

    def test_null_island_ditolak(self):
        """(0,0) adalah penanda de-facto parsing koordinat gagal, bukan
        posisi — invarian yang sama ditegakkan `spasial_utils`."""
        db = _Db(keg=KEG, node_rows=[GEDUNG])
        hasil = _panggil(db, {"activity_id": "k1"},
                         {"koordinat_latitude": "0", "koordinat_longitude": "0"})
        assert hasil is None
        assert db.spasial_node.panggilan == 0
