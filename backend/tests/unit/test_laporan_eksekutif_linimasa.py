"""Linimasa pada halaman 2 Laporan Eksekutif.

Permintaan pemilik: *"pada laporan eksekutif aset berikan linimasa seperti di
laporan gabungan, persis seperti tampilan Progres Inventarisasi-nya, hanya
ditempatkan di bagian halaman 2 Ringkasan Eksekutif."*

Dua sifat dijaga di sini:

1. **Grafiknya dihitung modul yang SAMA** dengan laporan gabungan. Dua
   perhitungan untuk satu grafik adalah dua angka yang harus sama selamanya,
   dan yang kedua tak pernah ikut diperbaiki.
2. **Ia benar-benar berada di halaman 2**, bukan sekadar ada di datanya.
   Halaman 2 ber-`overflow: hidden` pada lembar A4: isi yang berlebih terpotong
   tanpa bersuara, jadi plotnya sengaja lebih pendek daripada milik laporan
   gabungan.
"""
import asyncio
import os
import re

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.reports as rp

TPL = os.path.join(os.path.dirname(__file__), "..", "..", "templates",
                   "executive_summary.html")
TPL_GABUNGAN = os.path.join(os.path.dirname(__file__), "..", "..", "templates",
                            "laporan_satker_v2.html")


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    # `shared_utils` ikut ditambal: `pengaturan_kop` membaca `db` dari sana,
    # dan pemanggilnya di laporan eksekutif tak menelan galatnya.
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    return fake


def _teks(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


async def _seed(fake, n_aset=6, ditemukan=4):
    await fake.inventory_activities.insert_one({
        "id": "k1", "kode_satker": "401234", "nama_satker": "Satker Uji",
        "nama_kegiatan": "Inventarisasi", "nomor_surat": "S-1",
        "tanggal_mulai": "2026-03-01", "tanggal_selesai": "2026-06-30",
        "created_at": "2026-03-01",
    })
    for i in range(n_aset):
        await fake.assets.insert_one({
            "id": f"a{i}", "activity_id": "k1", "asset_name": f"Aset {i}",
            "asset_code": "3050105007", "NUP": str(i),
            "purchase_date": "2026-02-10", "purchase_price": 1000,
            "inventory_status": ("Ditemukan" if i < ditemukan
                                 else "Belum Diinventarisasi"),
            "tanggal_inventarisasi": "2026-04-05" if i < ditemukan else "",
            "condition": "Baik", "status": "Aktif",
        })


# ── 1. Satu perhitungan, dipakai dua laporan ────────────────────────────

def test_data_eksekutif_membawa_linimasa(dbx):
    async def jalan():
        await _seed(dbx)
        d = await rp._build_executive_summary_data("k1", with_asset_rows=False)
        assert d["linimasa_ada"] is True
        assert len(d["linimasa"]) == 12
        assert d["tahun_linimasa"] == 2026
        # Rumahnya BMN tercatat; isinya capaian pemeriksaan.
        feb = d["linimasa"][1]
        assert feb["tercatat"] == 6 and feb["tambahan"] == 6
        apr = d["linimasa"][3]
        assert apr["ditemukan"] == 4 and apr["belum"] == 2
    _jalan(jalan())


def test_angkanya_SAMA_dengan_laporan_gabungan(dbx):
    # Kedua laporan memanggil modul yang sama; kalau salah satu menyalinnya,
    # perbedaannya muncul justru saat datanya tak sepele — karena itu fixture
    # ini memuat STOK AWAL (perolehan tahun sebelumnya) dan aset bertanggal
    # perolehan tak terbaca, dua hal yang paling mudah tertinggal pada salinan.
    async def jalan():
        await _seed(dbx, n_aset=9, ditemukan=5)
        for i, beli in enumerate(("2019-04-01", "2023-11-30", "", "entah")):
            await dbx.assets.insert_one({
                "id": f"lama{i}", "activity_id": "k1", "asset_name": "Warisan",
                "asset_code": "3050105007", "NUP": f"9{i}",
                "purchase_date": beli, "purchase_price": 500,
                "inventory_status": "Ditemukan" if i < 2 else "Belum Diinventarisasi",
                "tanggal_inventarisasi": "2026-05-01" if i < 2 else "",
                "condition": "Baik", "status": "Aktif"})
        eks = await rp._build_executive_summary_data("k1", with_asset_rows=False)
        gab = await rp._build_satker_report_v2("k1")
        assert eks["linimasa_stok_awal"] == gab["linimasa_stok_awal"] > 0
        for i in range(12):
            for k in ("tercatat", "ditemukan", "periksa_lain", "belum",
                      "tambahan", "h_tercatat", "belum_berjalan"):
                assert eks["linimasa"][i][k] == gab["linimasa"][i][k], (i, k)
    _jalan(jalan())


def test_kegiatan_tanpa_aset_tak_menggambar_grafik_kosong(dbx):
    async def jalan():
        await dbx.inventory_activities.insert_one({
            "id": "k9", "kode_satker": "401234", "nama_satker": "Satker Uji",
            "nama_kegiatan": "Kosong", "nomor_surat": "S-9",
            "tanggal_mulai": "2026-03-01", "created_at": "2026-03-01"})
        d = await rp._build_executive_summary_data("k9", with_asset_rows=False)
        assert d["linimasa_ada"] is False
    _jalan(jalan())


# ── 2. Benar-benar di halaman 2, dan muat ───────────────────────────────

def test_grafik_ditempatkan_di_halaman_2(t=None):
    t = _teks(TPL)
    # Halaman 2 adalah blok `exec-page` PERTAMA setelah sampul.
    awal = t.index('<div class="exec-page">')
    akhir = t.index("Halaman 2 dari", awal)
    hal2 = t[awal:akhir]
    # Dicari pada ELEMEN judulnya, bukan sekadar ada di dalam blok: komentar
    # Jinja di blok yang sama juga memuat kata "Progres Inventarisasi", dan
    # mencocokkan blok apa adanya membuat uji ini lolos walau judulnya diganti.
    judul = re.search(r'<div class="lm-judul">([^<]*)</div>', hal2)
    assert judul, "elemen judul linimasa tak ada di halaman 2"
    assert "Progres Inventarisasi" in judul.group(1), judul.group(1)
    assert "lm-plot" in hal2 and "lm-rumah" in hal2


def test_plot_lebih_pendek_daripada_laporan_gabungan():
    # Halaman 2 sudah memuat kartu, batang capaian, tabel rekapitulasi,
    # simpulan, dan dua kotak info. `overflow: hidden` pada lembar A4 memotong
    # kelebihannya tanpa bersuara — plot setinggi milik laporan gabungan tak
    # akan muat.
    def tinggi_plot(path):
        m = re.search(r"\.lm-plot\s*\{[^}]*height:\s*(\d+)px", _teks(path))
        assert m, path
        return int(m.group(1))
    assert tinggi_plot(TPL) < tinggi_plot(TPL_GABUNGAN)


def test_tampilannya_memakai_kelas_yang_sama_dengan_laporan_gabungan():
    # "Persis seperti tampilan Progres Inventarisasi-nya": rumah, rongga
    # bergaris, irisan hijau/jingga, penanda bulan belum berjalan.
    t = _teks(TPL)
    for kelas in ("lm-rumah", "lm-rongga", "lm-temu", "lm-lain", "lm-atas",
                  "lm-tambah", "lm-belum", "lm-kosong", "lm-x", "lm-nota",
                  "i-rumah", "i-rongga"):
        assert kelas in t, kelas


def test_legendanya_menyebut_keempat_bagiannya():
    t = _teks(TPL)
    hal2 = t[t.index('<div class="exec-page">'):]
    for label in ("BMN Tercatat", "Ditemukan", "Diperiksa, tak ditemukan",
                  "Belum diperiksa"):
        assert label in hal2, label
