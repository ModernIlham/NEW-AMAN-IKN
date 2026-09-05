"""Nota Dinas persediaan sebagai NASKAH DINAS, bukan cetakan daftar.

Permintaan pemilik: *"buat permohonan barang persediaan lebih formal dan resmi
lagi, sertakan juga tempat dan tanggal pembuatannya."*

Sebelumnya dokumennya hanya judul lalu tabel, dengan baris tempat/tanggal
berupa titik-titik kosong. Dokumen yang tak menyebut kepada siapa ia ditujukan
tak dapat diagendakan, tak dapat ditindaklanjuti penerimanya, dan tak dapat
diarsipkan sebagai naskah dinas.

Dua sifat dijaga di sini:

1. **Kepala naskahnya lengkap dan urut baku** — dan barisnya SELALU ada,
   termasuk yang belum terisi. Kepala yang barisnya muncul-hilang mengikuti
   data membuat dua nota dinas dari satker yang sama terlihat sebagai dua
   jenis dokumen.
2. **Tempat dan tanggal benar-benar tercetak**, dan yang tak diketahui
   ditulis sebagai garis isian — ruang kosong terbaca sebagai bagian yang
   lupa dicetak, garis isian menyatakan "diisi tangan".
"""
import persuratan_utils as psu


# ── Tempat penandatanganan ──────────────────────────────────────────────

def test_tempat_diambil_dari_profil_satker():
    assert psu.tempat_dokumen({"tempat_laporan": "Nusantara"}) == "Nusantara"


def test_alamat_dipakai_bila_tempat_kosong():
    assert psu.tempat_dokumen({"alamat_instansi": "Jakarta Selatan"}) == "Jakarta Selatan"
    assert psu.tempat_dokumen({"tempat_laporan": "  ",
                               "alamat_instansi": "Balikpapan"}) == "Balikpapan"


def test_hanya_BARIS_PERTAMA_alamat_yang_dipakai():
    # Alamat lengkap kerap memuat beberapa baris; menempelkan seluruhnya ke
    # belakang tanggal membuat blok tanda tangan meluber.
    banyak = "Gedung Kantor Otorita IKN\nJalan Sudirman Kav 54-55\nJakarta"
    assert psu.tempat_dokumen({"alamat_instansi": banyak}) == "Gedung Kantor Otorita IKN"


def test_tanpa_profil_apa_pun_mengembalikan_kosong():
    assert psu.tempat_dokumen({}) == ""
    assert psu.tempat_dokumen(None) == ""


# ── Baris tempat, tanggal ───────────────────────────────────────────────

def test_baris_tempat_tanggal_tercetak_lengkap():
    assert psu.tempat_tanggal({"tempat_laporan": "Nusantara"},
                              "2026-09-05") == "Nusantara, 5 September 2026"


def test_yang_tak_diketahui_jadi_GARIS_ISIAN_bukan_kosong():
    # Garis isian menyatakan "diisi tangan saat penandatanganan"; ruang kosong
    # terbaca sebagai bagian yang lupa dicetak.
    baris = psu.tempat_tanggal({}, "")
    assert "..." in baris and baris.count(",") == 1
    assert psu.tempat_tanggal({"tempat_laporan": "Nusantara"}, "").startswith("Nusantara, ..")


# ── Kepala Nota Dinas ───────────────────────────────────────────────────

def test_kepala_urut_baku_dan_lengkap():
    kepala = psu.kepala_nota_dinas(hal="Usulan Pengadaan")
    assert [k for k, _ in kepala] == list(psu.URUT_KEPALA_NOTA)
    assert [k for k, _ in kepala] == ["Yth.", "Dari", "Nomor", "Sifat",
                                      "Lampiran", "Hal", "Tanggal"]


def test_baris_yang_belum_terisi_TETAP_dicetak():
    isi = dict(psu.kepala_nota_dinas())
    assert isi["Yth."] == "-" and isi["Dari"] == "-" and isi["Hal"] == "-"
    assert isi["Sifat"] == "Biasa", "sifat baku hilang"


def test_belum_bernomor_memakai_garis_isian_bukan_tanda_hubung():
    # Nomornya MENUNGGU diisi — berbeda maksud dengan bagian yang memang
    # kosong. Pola yang sama dengan BAST belum bernomor.
    isi = dict(psu.kepala_nota_dinas())
    assert "..." in isi["Nomor"]
    assert "..." in isi["Tanggal"]


def test_nomor_dan_tanggal_yang_ada_dipakai_apa_adanya():
    isi = dict(psu.kepala_nota_dinas(nomor="B-12/PL.01/2026",
                                     tanggal_iso="2026-09-05"))
    assert isi["Nomor"] == "B-12/PL.01/2026"
    assert isi["Tanggal"] == "5 September 2026"


def test_seluruh_isian_dirapikan_spasi_tepinya():
    isi = dict(psu.kepala_nota_dinas(yth="  Pejabat Pengadaan  ",
                                     hal="\tUsulan\t"))
    assert isi["Yth."] == "Pejabat Pengadaan"
    assert isi["Hal"] == "Usulan"


# ── Dokumen yang BENAR-BENAR tercetak ───────────────────────────────────
#
# Helper murni di atas dapat benar sementara dokumennya tak memakainya sama
# sekali. Yang di bawah merender PDF-nya sungguhan lalu membaca teksnya.

import asyncio

import pypdfium2 as pdfium
import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persediaan as rp

USER = {"username": "admin", "role": "admin", "kode_satker": "401234"}


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
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    _jalan(fake.report_settings.insert_one({
        "type": "global", "nama_instansi": "Otorita Ibu Kota Nusantara",
        "tempat_laporan": "Nusantara"}))
    # Koleksi `persediaan` — BUKAN `persediaan_items`. Semaian ke koleksi yang
    # salah membuat `peringatan_persediaan` tak menemukan apa pun, dan nota
    # yang dirender jadi nota KOSONG: kepala naskah dan tempat/tanggalnya
    # tetap tercetak sehingga seluruh assertion di bawah tetap hijau, tapi
    # tabel barangnya tak pernah diuji sama sekali.
    _jalan(fake.persediaan.insert_one({
        "id": "b1", "kode_barang": "1010309001000001", "kode_satker": "401234",
        "nama_barang": "E-Meterai Rp 10.000", "satuan": "Pcs",
        "stok": 0, "batas_kritis": 0}))
    return fake


def _teks_pdf(resp):
    potongan = b"".join(_jalan(_kumpul(resp.body_iterator))) if hasattr(
        resp, "body_iterator") else resp
    doc = pdfium.PdfDocument(potongan)
    return "\n".join(doc[i].get_textpage().get_text_range()
                     for i in range(len(doc)))


async def _kumpul(it):
    return [b async for b in it] if hasattr(it, "__aiter__") else list(it)


def _nota(dbx):
    return _teks_pdf(_jalan(rp.nota_dinas_persediaan(
        jenis="kritis", horizon_hari=30, ids="", _user=USER)))


def test_kepala_naskah_dinas_tercetak_di_dokumennya(dbx):
    t = _nota(dbx)
    for label in ("Yth.", "Dari", "Nomor", "Sifat", "Lampiran", "Hal",
                  "Tanggal"):
        assert label in t, label


def test_tempat_dan_tanggal_tercetak_bukan_titik_titik_kosong(dbx):
    t = _nota(dbx)
    assert "Nusantara," in t, t[:400]
    # Baris titik-titik lama tak boleh tersisa.
    assert ".................., ......................." not in t


def test_hal_menyebut_perihal_notanya(dbx):
    assert "Usulan Pengadaan Persediaan" in _nota(dbx)


def test_barang_peringatan_benar_benar_masuk_ke_tabelnya(dbx):
    """Penjaga semaian: bila fixture menyemai koleksi yang salah, notanya
    kosong dan seluruh test di atas TETAP hijau."""
    t = _nota(dbx)
    assert "E-Meterai Rp 10.000" in t, t[:600]
    assert "Tidak ada barang yang memenuhi kriteria" not in t


def test_lampiran_menyebut_berkas_saat_ada_daftarnya(dbx):
    # "1 (satu) berkas" hanya benar bila tabelnya memang terisi — nota kosong
    # harus menulis "-". Tanpa daftar yang sungguhan, cabang ini tak teruji.
    assert "1 (satu) berkas" in _nota(dbx)
