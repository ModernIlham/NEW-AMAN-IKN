"""Daftar barang berpindah menjadi LAMPIRAN begitu tanda tangan terdesak.

Permintaan pemilik: *"ketika tanda tangan sudah menyentuh halaman ke 2 maka
langsung ubah daftar tabel menjadi sebagai lampiran, jangan masukkan ke badan
surat."*

Daftar persediaan bisa memuat ratusan baris. Dibiarkan di badan surat, ia
mendorong blok tanda tangan ke halaman berikutnya — dan naskah dinas yang
tanda tangannya terpisah dari narasinya terbaca sebagai lembar lepas: pembaca
halaman terakhir hanya melihat potongan tabel lalu sebuah tanda tangan, tanpa
tahu ia menandatangani apa.

Maka batasnya bukan cacah baris melainkan AKIBATNYA, dan keputusannya diambil
dengan MENGUKUR tinggi flowables yang sudah tersusun — tinggi baris berubah
mengikuti panjang nama barang yang membungkus, sehingga ambang berupa angka
baris akan meleset pada dokumen yang isinya panjang-panjang.
"""
import asyncio
import ctypes

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
import pytest

import persediaan_nota_utils as pnu
import routes.persediaan as rp

SETTINGS = {"nama_instansi": "OTORITA IBU KOTA NUSANTARA",
            "tempat_laporan": "Nusantara"}
KPB = {"nama": "Budi Santoso", "nip": "198001012005011001",
       "jabatan": "Kepala Biro Umum", "status_kepegawaian": "PNS"}


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _baris(n, nama="Highlighter / Stabilo - Warna"):
    return [{"id": f"b{i}", "kode_barang": f"1010301001{i:06d}",
             "nama_barang": f"{nama} {i} (Pack)", "satuan": "Pack",
             "stok": 0, "batas_kritis": 0} for i in range(1, n + 1)]


def _halaman(n=10, jenis="kritis", rows=None, **kw):
    """→ list teks per halaman."""
    data = _jalan(rp.bangun_nota_dinas_pdf(
        jenis, _baris(n) if rows is None else rows, "2026-09-06",
        SETTINGS, KPB, nomor=kw.pop("nomor", "B-7/PL.01/2026"), **kw))
    assert data[:5] == b"%PDF-"
    doc = pdfium.PdfDocument(data)
    return [doc[i].get_textpage().get_text_range() for i in range(len(doc))]


# ── Daftar pendek: tetap di badan surat ─────────────────────────────────

def test_daftar_pendek_tetap_di_badan_surat_satu_halaman():
    hal = _halaman(8)
    assert len(hal) == 1
    assert "Highlighter" in hal[0] and "Budi Santoso" in hal[0]
    assert "LAMPIRAN NOTA DINAS" not in hal[0]


def test_daftar_pendek_menulis_lampiran_tanda_hubung():
    assert "1 (satu) berkas" not in _halaman(8)[0]


def test_daftar_pendek_menyebut_daftar_BERIKUT():
    t = _halaman(8)[0]
    assert "sebagaimana daftar berikut" in t
    assert "terlampir" not in t


# ── Daftar panjang: pindah ke lampiran ──────────────────────────────────

@pytest.mark.parametrize("n", list(range(1, 31)) + [80, 300])
def test_tanda_tangan_surat_SELALU_di_halaman_pertama(n):
    """Inti permintaannya, dan sifat yang harus berlaku untuk SETIAP panjang.

    Rentangnya disapu rapat, bukan dicicipi beberapa angka: cacat ini hidup
    tepat di PITA PERBATASAN — daftar yang tabelnya masih muat sendirian
    tetapi tak lagi menyisakan ruang bagi blok tanda tangan. Versi pertama
    uji ini melompat dari 11 langsung ke 30 dan melewatkan seluruh pita itu,
    sehingga mutasi yang mengabaikan tinggi blok tanda tangan lolos utuh.

    Yang ditagih adalah tanda tangan SURATNYA, di halaman pertama bersama
    narasinya. Lampiran membawa tanda tangannya sendiri — diuji terpisah di
    bawah — sehingga menagih "tak ada tanda tangan di halaman mana pun
    selain pertama" akan salah sejak lampiran ikut ditandatangani.
    """
    hal = _halaman(n)
    assert "Budi Santoso" in hal[0], f"{n} baris: tanda tangan bukan di hal. 1"


@pytest.mark.parametrize("n", [1, 5, 8, 11])
def test_surat_sehalaman_hanya_bertanda_tangan_SEKALI(n):
    """Tanpa lampiran tak ada tanda tangan kedua di mana pun."""
    hal = _halaman(n)
    assert len(hal) == 1, n
    assert hal[0].count("Budi Santoso") == 1, n


def test_lampiran_ikut_DITANDATANGANI_di_lembar_terakhirnya():
    """Permintaan pemilik: lampirannya diberi kolom tanda tangan juga.

    Lembar daftar yang tak bertanda tangan hanyalah cetakan tabel — ia dapat
    ditukar atau ditambahi tanpa meninggalkan jejak, sementara surat induknya
    tetap sah.
    """
    hal = _halaman(80)
    assert len(hal) > 2
    assert "Budi Santoso" in hal[-1], "lembar terakhir lampiran tak bertanda tangan"


def test_lembar_lampiran_di_TENGAH_tak_bertanda_tangan():
    """Yang ditandatangani adalah lampirannya, bukan tiap lembarnya.

    Tanda tangan di setiap lembar membuat pembaca tak dapat mengetahui di mana
    daftarnya sebenarnya berakhir.
    """
    hal = _halaman(300)
    tengah = hal[1:-1]
    assert tengah, "kasus ujinya tak menghasilkan lembar tengah"
    assert not any("Budi Santoso" in t for t in tengah)


def test_surat_dan_lampiran_menyebut_penanda_tangan_yang_SAMA():
    # Diambil dari `kpb` beku yang sama, sehingga mustahil menyebut dua
    # pejabat berbeda pada satu berkas.
    hal = _halaman(80)
    for lembar in (hal[0], hal[-1]):
        assert "Budi Santoso" in lembar
        assert "Kuasa Pengguna Barang" in lembar


def test_daftar_panjang_pindah_ke_lampiran_dan_hilang_dari_badan_surat():
    hal = _halaman(80)
    assert len(hal) > 1
    assert "Highlighter" not in hal[0], "tabel masih di badan surat"
    assert "LAMPIRAN NOTA DINAS" in hal[1]
    assert "Highlighter" in hal[1]


def test_lampiran_membawa_nomor_induknya():
    """Halaman lampiran tak membawa blok kepala; tanpa nomor di sana, lembar
    yang terlepas dari induknya tak dapat dikembalikan ke berkasnya."""
    hal = _halaman(80)
    assert "B-7/PL.01/2026" in hal[1]
    assert "6 September 2026" in hal[1]


def test_lampiran_menyebut_berapa_baris_yang_dibawanya():
    # Lampiran yang tak menyebut jumlahnya membuat halaman yang hilang tak
    # pernah ketahuan hilang.
    assert "80 baris" in _halaman(80)[1]


def test_kepala_surat_mengaku_punya_lampiran():
    t = _halaman(80)[0]
    assert "1 (satu) berkas" in t
    assert "sebagaimana daftar terlampir" in t


# ── Ambang diukur, bukan ditebak dari cacah baris ───────────────────────

def test_nama_barang_panjang_menggeser_ambangnya():
    """Cacah baris yang sama, tinggi berbeda: nama panjang membungkus menjadi
    beberapa baris. Ambang berupa angka baris akan menyimpulkan keduanya sama.
    """
    pendek = _halaman(rows=_baris(10, "Pena"))
    panjang = _halaman(rows=_baris(
        10, "Kertas HVS A4 80 gram merek tertentu untuk keperluan pencetakan "
            "dokumen resmi kantor sehari-hari"))
    assert len(pendek) == 1, "daftar 10 baris bernama pendek seharusnya muat"
    assert len(panjang) > 1, "daftar 10 baris bernama panjang seharusnya tidak"


def test_narasi_yang_lebih_panjang_ikut_diperhitungkan():
    """Nota "seleksi" membawa satu paragraf tambahan, jadi ambangnya turun.

    Pada 11 baris, nota biasa masih muat sementara nota tersaring tidak —
    bukti bahwa yang diukur adalah SELURUH naskah, bukan tabelnya saja.
    """
    assert len(_halaman(11, seleksi=False)) == 1
    assert len(_halaman(11, seleksi=True)) > 1


# ── Nota kosong ─────────────────────────────────────────────────────────

def test_nota_tanpa_barang_tak_mengaku_punya_lampiran():
    hal = _halaman(rows=[])
    assert len(hal) == 1
    assert "Tidak ada barang yang memenuhi kriteria" in hal[0]
    assert "1 (satu) berkas" not in hal[0]
    assert "LAMPIRAN NOTA DINAS" not in hal[0]


# ── Judul & nomor ───────────────────────────────────────────────────────

def test_judul_permohonan_dan_nomor_tepat_di_bawahnya():
    t = _halaman(8)[0]
    assert "PERMOHONAN USULAN PENGADAAN PERSEDIAAN" in t
    judul = t.index("PERMOHONAN USULAN PENGADAAN PERSEDIAAN")
    nomor = t.index("Nomor: B-7/PL.01/2026")
    yth = t.index("Yth.")
    assert judul < nomor < yth, "nomor tidak berada antara judul dan blok kepala"


def test_kedua_jenis_punya_judul_yang_berbeda():
    # Judul yang sama membuat nota kritis dan nota kedaluwarsa tak dapat
    # dibedakan di layar arsip.
    assert pnu.judul("kritis") != pnu.judul("kedaluwarsa")
    for jenis in pnu.JENIS_NOTA:
        assert "PERMOHONAN" in pnu.judul(jenis), jenis


def test_belum_bernomor_memakai_garis_isian():
    t = _halaman(8, nomor="")[0]
    assert "Nomor: ......." in t


@pytest.mark.parametrize("jenis", list(pnu.JENIS_NOTA))
def test_kedua_jenis_menempuh_jalur_lampiran_yang_sama(jenis):
    rows = ([{"id": f"b{i}", "kode_barang": f"K{i:04d}",
              "nama_barang": f"Hand Sanitizer 500ml Varian {i}", "qty": 4,
              "expired": "2026-08-01"} for i in range(1, 81)]
            if jenis == "kedaluwarsa" else None)
    hal = _halaman(80, jenis=jenis, rows=rows)
    assert "Budi Santoso" in hal[0]
    assert "LAMPIRAN NOTA DINAS" in hal[1]


# ── Tipografi ──────────────────────────────────────────────────────────
#
# Keluhan pemilik: *"sesuaikan ukuran font dan tebal tidaknya kata yang harus
# tebal karena saat ini masih jelek dan tidak terlihat profesional."*
#
# Yang di bawah membaca ukuran dan nama font LANGSUNG dari PDF yang tercetak,
# bukan dari kode yang menyusunnya: gaya yang benar di sumber tetapi tak
# sampai ke halaman adalah persis kegagalan yang hendak dicegah.


def _halaman_teks_dan_font(n=6):
    data = _jalan(rp.bangun_nota_dinas_pdf(
        "kritis", _baris(n), "2026-09-06", SETTINGS, KPB,
        nomor="B-7/PL.01/2026"))
    tp = pdfium.PdfDocument(data)[0].get_textpage()
    return tp, tp.get_text_range()


def _ukuran(tp, teks, frasa) -> float:
    return round(pdfium_raw.FPDFText_GetFontSize(tp.raw, teks.index(frasa)), 2)


def _nama_font(tp, teks, frasa) -> str:
    buf = ctypes.create_string_buffer(128)
    bendera = ctypes.c_int()
    n = pdfium_raw.FPDFText_GetFontInfo(
        tp.raw, teks.index(frasa), buf, 128, ctypes.byref(bendera))
    return buf.raw[:max(0, n - 1)].decode("utf-8", "replace")


def test_narasi_TIDAK_lebih_kecil_daripada_kepalanya_sendiri():
    """Prosa surat yang lebih kecil daripada label kepalanya terbaca sebagai
    catatan kaki, bukan sebagai isi naskah."""
    tp, t = _halaman_teks_dan_font()
    assert _ukuran(tp, t, "Dalam rangka menjaga") == \
        _ukuran(tp, t, "Pejabat Pengadaan Barang/Jasa")


def test_judul_lebih_besar_dan_TEBAL():
    tp, t = _halaman_teks_dan_font()
    assert _ukuran(tp, t, "PERMOHONAN USULAN") > \
        _ukuran(tp, t, "Dalam rangka menjaga")
    assert "Bold" in _nama_font(tp, t, "PERMOHONAN USULAN")


def test_label_kepala_tebal_dan_nilainya_tidak():
    # Label yang setebal nilainya membuat kolomnya tak terbaca sebagai kolom.
    tp, t = _halaman_teks_dan_font()
    assert "Bold" in _nama_font(tp, t, "Yth.")
    assert "Bold" not in _nama_font(tp, t, "Pejabat Pengadaan Barang/Jasa")


def test_narasi_dan_nomor_TIDAK_tebal():
    # Prosa yang seluruhnya tebal menghapus penekanan yang memang disengaja.
    tp, t = _halaman_teks_dan_font()
    assert "Bold" not in _nama_font(tp, t, "Dalam rangka menjaga")
    assert "Bold" not in _nama_font(tp, t, "Nomor: B-7")


def test_kepala_tabel_tebal_agar_terbaca_sebagai_kepala():
    tp, t = _halaman_teks_dan_font()
    assert "Bold" in _nama_font(tp, t, "Kode Barang")


# ── Jumlah usulan sampai ke naskah ─────────────────────────────────────

def _rapat(teks) -> str:
    """Rapatkan spasi/baris — kepala kolom sempit membungkus jadi dua baris
    ("Jumlah\nDiusulkan"), dan itu memang wajar pada tabel resmi."""
    return " ".join(str(teks or "").split())


def test_jumlah_usulan_tercetak_di_kolomnya():
    rows = _baris(4)
    rows[0]["jumlah_diusulkan"] = 25
    hal = _halaman(rows=rows)
    assert "Jumlah Diusulkan" in _rapat(hal[0])
    assert "25" in hal[0]


def test_yang_tak_diisi_tercetak_tanda_hubung_bukan_nol():
    """"0" terbaca sebagai permintaan NOL unit — dan itu tercetak pada naskah
    resmi yang ditandatangani."""
    hal = _halaman(rows=_baris(3))
    kolom = [b for b in hal[0].splitlines() if "Pack 0 0" in b]
    assert kolom, hal[0]
    assert all(b.rstrip().endswith("-") for b in kolom), kolom


def test_kolom_jumlah_ikut_ke_lampiran():
    rows = _baris(80)
    rows[0]["jumlah_diusulkan"] = 40
    hal = _halaman(rows=rows)
    assert "Jumlah Diusulkan" in _rapat(hal[1])
    assert "40" in hal[1]
