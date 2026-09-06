"""Jenjang unit organisasi di laporan mengikuti puncak satkernya.

Dua patokan Eselon I tersisa setelah pohon unit dibuat berakar di tingkat
satkernya. Keduanya bekerja tanpa satu pun pesan galat:

1. **Ringkasan eksekutif mengelompokkan menurut `eselon1`.** Pada satker
   Eselon III seluruh asetnya jatuh ke satu keranjang "Tanpa Eselon I" — satu
   batang yang tak mengabarkan apa pun kecuali bahwa pertanyaannya salah
   alamat.

2. **Panel analisis unit berjenjang bawaan Eselon II.** Pada satker Eselon III
   itu bukan tingkat yang lebih halus melainkan tingkat milik instansi
   induknya, yang tak berisi apa pun; panelnya terbuka kosong, dan panel
   kosong terbaca sebagai laporan yang gagal dimuat.

Alasan bawaan lamanya TETAP berlaku — Eselon I terlalu kasar untuk menunjuk
siapa yang bertanggung jawab atas barangnya — jadi yang diubah patokannya,
bukan aturannya: satu jenjang DI BAWAH puncak satkernya.
"""
import laporan_jenjang as ljj


# ── 1. Tingkat mana yang benar-benar berisi ─────────────────────────────

def test_level_berdata_membaca_kolom_yang_TERISI_saja():
    aset = [{"eselon3": "Lapas Kelas IIA", "eselon4": "Subbagian TU"},
            {"eselon3": "Lapas Kelas IIA", "eselon4": "   "},
            {"eselon1": "", "eselon5": None}]
    assert ljj.level_eselon_berdata(aset) == (3, 4)
    assert ljj.level_eselon_berdata([]) == ()
    assert ljj.level_eselon_berdata(None) == ()
    assert ljj.level_eselon_berdata([None, {}]) == ()


# ── 2. Jenjang panel analisis ───────────────────────────────────────────

def test_satker_kantor_pusat_TETAP_berbawaan_Eselon_II():
    # Perilaku lama harus utuh: tetapannya diganti aturan yang menghasilkan
    # angka yang sama untuk satker yang memang berpuncak Eselon I.
    sah, bawaan = ljj.jenjang_eselon_satker(1, (1, 2, 3))
    assert bawaan == 2
    assert sah == (1, 2, 3, 4, 5)


def test_satker_lama_yang_belum_menyatakan_tingkatnya_juga_tetap():
    sah, bawaan = ljj.jenjang_eselon_satker(None, (1, 2))
    assert (sah, bawaan) == ((1, 2, 3, 4, 5), 2)


def test_lapas_berbawaan_satu_jenjang_DI_BAWAH_puncaknya():
    sah, bawaan = ljj.jenjang_eselon_satker(3, (3, 4))
    assert bawaan == 4, "bawaan masih dipatok Eselon II"
    assert sah == (3, 4, 5)


def test_bawaan_TAK_menunjuk_jenjang_yang_kosong():
    # Lapas yang baru mencatat unit puncaknya saja: menyodorkan Eselon IV
    # berarti membuka panel kosong — kekeliruan yang sama, berpindah tempat.
    _, bawaan = ljj.jenjang_eselon_satker(3, (3,))
    assert bawaan == 3


def test_satker_Eselon_V_tak_menunjuk_jenjang_keenam():
    _, bawaan = ljj.jenjang_eselon_satker(5, (5,))
    assert bawaan == 5


def test_jenjang_di_ATAS_puncak_tetap_ditawarkan_bila_berisi():
    # Satker yang baru menyatakan dirinya Eselon III masih menyimpan aset
    # ber-`eselon1`. Menutup jenjang itu membuat datanya tak dapat dilihat
    # sama sekali — hilang dari laporan tetapi tetap hidup di basis data.
    sah, _ = ljj.jenjang_eselon_satker(3, (1, 3, 4))
    assert sah == (1, 3, 4, 5)


def test_jenjang_di_atas_puncak_TAK_ditawarkan_bila_kosong():
    sah, _ = ljj.jenjang_eselon_satker(3, (3, 4))
    assert 1 not in sah and 2 not in sah


def test_seluruh_datanya_di_atas_puncak_tetap_dapat_dibaca():
    # Satker menyatakan Eselon III, tetapi asetnya semua warisan ber-eselon1.
    # Bawaan Eselon IV akan membuka panel kosong padahal datanya ada; aturannya
    # diterapkan pada puncak EFEKTIF (Eselon I), jadi bawaannya Eselon II.
    sah, bawaan = ljj.jenjang_eselon_satker(3, (1, 2))
    assert bawaan == 2
    assert 1 in sah and 2 in sah


def test_satker_yang_BELUM_menyatakan_tingkatnya_tetap_dapat_jenjang_berguna():
    # Lapas yang belum mengisi tingkat satkernya terbaca berpuncak Eselon I
    # sementara datanya mulai di Eselon III. Aturan "satu jenjang di bawah
    # puncak" diterapkan pada puncak EFEKTIF, jadi bawaannya Eselon IV —
    # Seksi/Subbagiannya, bukan satu baris nama Lapasnya.
    _, bawaan = ljj.jenjang_eselon_satker(None, (3, 4))
    assert bawaan == 4


def test_tingkat_tak_sah_pada_data_diabaikan_bukan_meledak():
    sah, bawaan = ljj.jenjang_eselon_satker(1, (0, 9, "x", None, 2))
    assert sah == (1, 2, 3, 4, 5) and bawaan == 2


# ── 3. Tingkat pengelompokan ringkasan eksekutif ────────────────────────

def test_ringkasan_kantor_pusat_TETAP_mengelompokkan_di_Eselon_I():
    assert ljj.level_kelompok_eselon(1, (1, 2)) == 1
    assert ljj.level_kelompok_eselon(None, (1, 2)) == 1


def test_ringkasan_lapas_mengelompokkan_di_PUNCAKNYA():
    assert ljj.level_kelompok_eselon(3, (3, 4)) == 3


def test_ringkasan_jatuh_ke_jenjang_BERDATA_saat_puncaknya_kosong():
    # Lapas yang BELUM menyatakan tingkatnya: puncaknya terbaca Eselon I,
    # yang tak berisi apa pun. Tanpa cabang ini seluruh asetnya jadi satu
    # batang "Tanpa Eselon I" — persis cacat yang dilaporkan.
    assert ljj.level_kelompok_eselon(1, (3, 4)) == 3


def test_ringkasan_memakai_puncaknya_saat_tak_ada_data_sama_sekali():
    assert ljj.level_kelompok_eselon(3, ()) == 3
    assert ljj.level_kelompok_eselon(None, ()) == 1


def test_ringkasan_membaca_sisa_data_lama_di_atas_puncak():
    assert ljj.level_kelompok_eselon(4, (2,)) == 2


def test_kelompok_dan_bawaan_panel_berpangkal_pada_puncak_yang_SAMA():
    # Keduanya menjawab pertanyaan berbeda dari titik tolak yang sama; bila
    # berbeda, ringkasan dan panel analisis bercerita tentang dua struktur.
    for akar, berdata in ((1, (1, 2)), (3, (3, 4)), (None, (3, 4)), (3, (1, 2))):
        kelompok = ljj.level_kelompok_eselon(akar, berdata)
        _, bawaan = ljj.jenjang_eselon_satker(akar, berdata)
        assert bawaan in (kelompok, kelompok + 1), (akar, berdata)


# ── 4. Laporannya benar-benar memakainya ────────────────────────────────
#
# Modul murni di atas dapat benar sementara laporannya tetap memanggil tetapan
# lama. Bagian ini menempuh jalur yang sama dengan laporan sungguhan.

import asyncio  # noqa: E402

import pytest  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

import routes.reports as rp  # noqa: E402


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def dbr(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    return fake


#: Lapas: satker Eselon III. Pegawai & asetnya mengisi eselon3–4, membiarkan
#: eselon1–2 kosong sebab keduanya milik Ditjen di kementeriannya.
async def _seed_lapas(fake, eselon_satker="3"):
    await fake.satker.insert_one(
        {"kode_satker": "333333", "nama_satker": "Lapas Kelas IIA Nusantara",
         **({"eselon_satker": eselon_satker} if eselon_satker else {})})
    await fake.inventory_activities.insert_one(
        {"id": "k1", "kode_satker": "333333",
         "nama_satker": "Lapas Kelas IIA Nusantara",
         "nama_kegiatan": "Inventarisasi 2025", "nomor_surat": "S-1",
         "tanggal_mulai": "2025-05-01", "tanggal_selesai": "2025-05-28",
         "created_at": "2025-05-01"})
    for i, seksi in enumerate(["Subbagian Tata Usaha", "Seksi Pembinaan"]):
        for j in range(3):
            await fake.assets.insert_one(
                {"id": f"a{i}{j}", "activity_id": "k1",
                 "asset_name": f"Barang {i}{j}", "asset_code": "3050104001",
                 "NUP": str(j), "purchase_price": 1000,
                 "purchase_date": "2023-01-01",
                 "inventory_status": "Belum Diinventarisasi",
                 "eselon3": "Lapas Kelas IIA Nusantara", "eselon4": seksi})


def test_ringkasan_eksekutif_lapas_TAK_lagi_satu_batang_tanpa_Eselon_I(dbr):
    _jalan(_seed_lapas(dbr))
    d = _jalan(rp._build_executive_summary_data("k1", with_asset_rows=False))
    nama = [b[0] for b in d["eselon1_breakdown"]]
    assert nama == ["Lapas Kelas IIA Nusantara"], nama
    assert not any(n.startswith("Tanpa") for n in nama)
    # Judul panelnya ikut menyebut tingkat yang benar-benar dikelompokkan.
    assert d["eselon_label"] == "Eselon III"


def test_ringkasan_kantor_pusat_TIDAK_berubah(dbr):
    async def siap():
        await dbr.satker.insert_one(
            {"kode_satker": "111111", "nama_satker": "Setjen"})
        await dbr.inventory_activities.insert_one(
            {"id": "k9", "kode_satker": "111111", "nama_satker": "Setjen",
             "nama_kegiatan": "Inventarisasi", "nomor_surat": "S-9",
             "tanggal_mulai": "2025-05-01", "tanggal_selesai": "2025-05-28",
             "created_at": "2025-05-01"})
        await dbr.assets.insert_one(
            {"id": "z1", "activity_id": "k9", "asset_name": "Meja",
             "asset_code": "3050104001", "NUP": "1", "purchase_price": 1000,
             "purchase_date": "2023-01-01",
             "inventory_status": "Belum Diinventarisasi",
             "eselon1": "Sekretariat Jenderal", "eselon2": "Biro Umum"})
    _jalan(siap())
    d = _jalan(rp._build_executive_summary_data("k9", with_asset_rows=False))
    assert [b[0] for b in d["eselon1_breakdown"]] == ["Sekretariat Jenderal"]
    assert d["eselon_label"] == "Eselon I"


def test_ringkasan_lapas_yang_BELUM_menyatakan_tingkatnya_tetap_terbaca(dbr):
    # Justru keadaan yang dilaporkan pemilik: tanpa cabang jatuh-ke-berdata,
    # keenam asetnya jadi satu batang "Tanpa Eselon I".
    _jalan(_seed_lapas(dbr, eselon_satker=""))
    d = _jalan(rp._build_executive_summary_data("k1", with_asset_rows=False))
    assert [b[0] for b in d["eselon1_breakdown"]] == ["Lapas Kelas IIA Nusantara"]
    assert d["eselon_label"] == "Eselon III"


def test_panel_lapas_yang_BELUM_menyatakan_tingkatnya_tetap_berisi(dbr):
    _jalan(_seed_lapas(dbr, eselon_satker=""))
    d = _jalan(rp._build_satker_report_v2("k1"))
    assert d["label_es_bawaan"] == "Eselon IV"
    nama = [b["name"] for b in d["chart_eselon"]]
    assert "Subbagian Tata Usaha" in nama and "Seksi Pembinaan" in nama, nama


def test_panel_analisis_lapas_berjenjang_bawaan_Eselon_IV(dbr):
    _jalan(_seed_lapas(dbr))
    d = _jalan(rp._build_satker_report_v2("k1"))
    # Bawaannya satu jenjang di bawah puncak: Seksi/Subbagian, bukan panel
    # kosong pada tingkat milik instansi induknya.
    assert d["label_es_bawaan"] == "Eselon IV"
    nama = [b["name"] for b in d["chart_eselon"]]
    assert "Subbagian Tata Usaha" in nama and "Seksi Pembinaan" in nama, nama


def test_pemilih_jenjang_lapas_tak_menawarkan_Eselon_I_dan_II(dbr):
    # Menawarkannya hanya menawarkan grafik kosong.
    _jalan(_seed_lapas(dbr))
    d = _jalan(rp._build_satker_report_v2("k1"))
    assert [p["nilai"] for p in d["pilihan_es_level"]] == ["3", "4", "5"]


def test_panel_analisis_kantor_pusat_TETAP_bawaan_Eselon_II(dbr):
    async def siap():
        await dbr.satker.insert_one({"kode_satker": "111111"})
        await dbr.inventory_activities.insert_one(
            {"id": "k9", "kode_satker": "111111", "nama_satker": "Setjen",
             "nama_kegiatan": "Inventarisasi", "nomor_surat": "S-9",
             "tanggal_mulai": "2025-05-01", "tanggal_selesai": "2025-05-28",
             "created_at": "2025-05-01"})
        await dbr.assets.insert_one(
            {"id": "z1", "activity_id": "k9", "asset_name": "Meja",
             "asset_code": "3050104001", "NUP": "1", "purchase_price": 1000,
             "purchase_date": "2023-01-01",
             "inventory_status": "Belum Diinventarisasi",
             "eselon1": "Sekretariat Jenderal", "eselon2": "Biro Umum"})
    _jalan(siap())
    d = _jalan(rp._build_satker_report_v2("k9"))
    assert d["label_es_bawaan"] == "Eselon II"
    assert [b["name"] for b in d["chart_eselon"]] == ["Biro Umum"]
