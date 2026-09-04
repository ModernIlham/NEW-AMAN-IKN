"""Filter interaktif laporan gabungan satker.

Permintaan pemilik: *"jadikan interaktif dan dapat memilih kegiatan apa saja
yang dapat di filter sesuai seleksi yang dipilih, buat filter menjadi advanced
dan dapat memilih 2 pilihan sesuai seleksi di filter yang sama, tanggal tahun
dan lain lain."*

Empat sifat dijaga di sini:

1. **Satu filter menerima LEBIH DARI SATU pilihan** — inti permintaannya.
2. **Daftar pilihan tak menciut saat difilter.** Kalau daftar tahun disusun
   dari aset yang sudah tersaring, memilih 2023 membuat pilihan lain lenyap
   dan pengguna terkurung tanpa kotak untuk mengembalikannya.
3. **Filter kegiatan menyusutkan kartu kegiatan DAN angkanya.**
4. **Laporan tersaring mengatakan dirinya tersaring** — juga di kertas, tempat
   panel filternya tak ikut tercetak.
"""
import asyncio
import os
import re

import pytest
from mongomock_motor import AsyncMongoMockClient

import laporan_filter as lf
import routes.reports as rp

TPL = os.path.join(os.path.dirname(os.path.abspath(rp.__file__)),
                   "..", "templates", "laporan_satker_v2.html")


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _th(d):
    """Peniru `_tahun_perolehan`: ambil tahun dari tanggal, '-' bila kosong."""
    t = str(d or "")[:4]
    return t if t.isdigit() else "-"


@pytest.fixture()
def dbf(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rp, "db", fake, raising=False)
    return fake


async def _seed(fake):
    """Dua kegiatan; aset berselang-seling tahun, kondisi, dan lokasi.

    Kondisi dan lokasi sengaja BERBEDA antar kegiatan. Versi pertama fixture
    ini memberi kedua kegiatan himpunan nilai yang sama persis, sehingga
    daftar pilihan yang disempitkan menurut kegiatan kebetulan identik dengan
    daftar penuh — dan uji penyempitan lolos tanpa pernah menyentuh
    perilakunya. Tahun sengaja dibiarkan sama pada keduanya, sebagai dimensi
    pembanding yang memang tak berubah.
    """
    for i, (bulan, n) in enumerate([(5, 6), (7, 4)], 1):
        await fake.inventory_activities.insert_one({
            "id": f"k{i}", "kode_satker": "401234",
            "nama_kegiatan": f"Kegiatan {i}", "nomor_surat": f"S-{i}",
            "tanggal_mulai": f"2025-{bulan:02d}-01",
            "tanggal_selesai": f"2025-{bulan:02d}-28", "nama_satker": "Satker Uji"})
        for j in range(n):
            await fake.assets.insert_one({
                "id": f"k{i}-a{j}", "activity_id": f"k{i}", "asset_name": f"B{j}",
                "asset_code": "305", "NUP": str(j), "purchase_price": 100,
                "purchase_date": f"{2023 + (j % 2)}-01-01",
                "condition": ("Baik" if j % 2 else
                              ("Rusak Ringan" if i == 1 else "Rusak Berat")),
                "location": (f"Lantai {1 + j % 2}" if i == 1
                             else f"Gudang {'AB'[j % 2]}"),
                "inventory_status": "Ditemukan" if j < 2 else "Belum Diinventarisasi",
                "tanggal_inventarisasi": (f"2025-0{6 + i}-1{j}T00:00:00+00:00"
                                          if j < 2 else ""),
            })


# ── 1. Dua pilihan pada filter yang sama ────────────────────────────────

def test_satu_filter_menerima_dua_pilihan(dbf):
    """Inti permintaannya. Dua tahun dicentang → keduanya ikut."""
    async def jalan():
        await _seed(dbf)
        dua = await rp._build_satker_report_v2("k1", {"tahun": ["2023", "2024"]})
        satu = await rp._build_satker_report_v2("k1", {"tahun": ["2023"]})
        assert dua["total_count"] == 10, "kedua tahun harus ikut"
        assert satu["total_count"] < dua["total_count"]
    _jalan(jalan())


def test_filter_berbeda_saling_mempersempit(dbf):
    """Filter lanjutan: kegiatan DAN kondisi berlaku bersamaan (irisan),
    bukan gabungan — memilih dua dimensi harus mempersempit, bukan melebarkan."""
    async def jalan():
        await _seed(dbf)
        d = await rp._build_satker_report_v2(
            "k1", {"kegiatan": ["k1"], "kondisi": ["Baik"]})
        assert d["total_count"] == 3, d["total_count"]
    _jalan(jalan())


def test_filter_kosong_berarti_semua(dbf):
    """Halaman yang dibuka tanpa parameter harus utuh seperti sebelumnya."""
    async def jalan():
        await _seed(dbf)
        for f in (None, {}, {"tahun": [], "kegiatan": []}, {"tahun": [""]}):
            d = await rp._build_satker_report_v2("k1", f)
            assert d["total_count"] == 10, f
            assert d["filter_aktif"] is False, f
    _jalan(jalan())


# ── 2. Daftar pilihan tak menciut ───────────────────────────────────────

def _nilai(opsi):
    return [o["nilai"] for o in opsi]


def test_dimensi_tak_menyempitkan_daftarnya_SENDIRI(dbf):
    """Jebakan klasik filter bertingkat: memilih satu nilai membuat nilai lain
    lenyap dari daftarnya, dan pengguna terkurung — tak ada lagi kotak untuk
    mengembalikannya. Hanya terlihat setelah seseorang benar-benar terjebak."""
    async def jalan():
        await _seed(dbf)
        penuh = await rp._build_satker_report_v2("k1")
        for dimensi, nilai in (("tahun", "2023"), ("kondisi", "Baik"),
                               ("lokasi", "Lantai 1"),
                               ("status", "Ditemukan")):
            sempit = await rp._build_satker_report_v2("k1", {dimensi: [nilai]})
            assert _nilai(sempit["pilihan"][dimensi]) == _nilai(penuh["pilihan"][dimensi]), dimensi
            assert sempit["total_count"] < penuh["total_count"], dimensi
    _jalan(jalan())


def test_memilih_KEGIATAN_menyempitkan_pilihan_dimensi_lain(dbf):
    """Permintaan pemilik: *"ketika kegiatan dipilih maka dapat mempengaruhi
    data filter lainnya yang menyesuaikan dengan pilihan kegiatan yang
    terpilih."*

    Kegiatan adalah puncak hierarki: satu kegiatan memang punya himpunan
    lokasi dan kondisinya sendiri, dan menawarkan lokasi milik kegiatan lain
    hanya menawarkan hasil kosong."""
    async def jalan():
        await _seed(dbf)
        penuh = await rp._build_satker_report_v2("k1")
        assert set(_nilai(penuh["pilihan"]["lokasi"])) == {
            "Lantai 1", "Lantai 2", "Gudang A", "Gudang B"}

        satu = await rp._build_satker_report_v2("k1", {"kegiatan": ["k1"]})
        assert set(_nilai(satu["pilihan"]["lokasi"])) == {"Lantai 1", "Lantai 2"}
        assert set(_nilai(satu["pilihan"]["kondisi"])) == {"Baik", "Rusak Ringan"}
        assert "Rusak Berat" not in _nilai(satu["pilihan"]["kondisi"])

        dua = await rp._build_satker_report_v2("k1", {"kegiatan": ["k2"]})
        assert set(_nilai(dua["pilihan"]["lokasi"])) == {"Gudang A", "Gudang B"}
    _jalan(jalan())


def test_daftar_KEGIATAN_tak_pernah_menyempit(dbf):
    """Jalan pulangnya. Kalau daftar kegiatan ikut menyempit menurut kegiatan
    yang dipilih, pengguna terkunci pada pilihan pertamanya."""
    async def jalan():
        await _seed(dbf)
        penuh = await rp._build_satker_report_v2("k1")
        for f in ({"kegiatan": ["k1"]}, {"kegiatan": ["k2"]},
                  {"kegiatan": ["k1"], "lokasi": ["Lantai 1"]}):
            d = await rp._build_satker_report_v2("k1", f)
            assert _nilai(d["pilihan"]["kegiatan"]) == _nilai(penuh["pilihan"]["kegiatan"]), f
    _jalan(jalan())


def test_pilihan_tercentang_di_luar_kegiatan_TETAP_TAMPIL_bertanda(dbf):
    """Pindah dari kegiatan 1 ke kegiatan 2 sementara "Lantai 1" masih
    tercentang: filternya tetap berlaku dan mengosongkan laporan. Kalau
    kotaknya dihapus dari daftar, sebabnya lenyap dari layar dan tak ada lagi
    kotak untuk membatalkannya — laporan kosong tanpa penjelasan."""
    async def jalan():
        await _seed(dbf)
        d = await rp._build_satker_report_v2(
            "k1", {"kegiatan": ["k2"], "lokasi": ["Lantai 1"]})
        lok = {o["nilai"]: o["di_luar"] for o in d["pilihan"]["lokasi"]}
        assert "Lantai 1" in lok, "kotaknya lenyap; tak bisa dilepas lagi"
        assert lok["Lantai 1"] is True, "tak ditandai sebagai di luar lingkup"
        assert lok["Gudang A"] is False
        assert d["total_count"] == 0, "filternya memang mengosongkan hasil"
        with open(TPL, encoding="utf-8") as f:
            assert "tanda-luar" in f.read(), "penandanya tak digambar di panel"
    _jalan(jalan())


# ── 3. Kegiatan menyusutkan kedua sisi ──────────────────────────────────

def test_kegiatan_tak_dipilih_hilang_dari_kartu_DAN_angka(dbf):
    """Kalau hanya asetnya yang disaring, kartu kegiatan kosong tetap
    tercetak dan terbaca sebagai "kegiatan ini nol" — bukan "tak dipilih"."""
    async def jalan():
        await _seed(dbf)
        d = await rp._build_satker_report_v2("k1", {"kegiatan": ["k1"]})
        assert d["total_kegiatan"] == 1
        assert [k["nama_kegiatan"] for k in d["kegiatan_list"]] == ["Kegiatan 1"]
        assert d["total_count"] == 6
    _jalan(jalan())


# ── 4. Rentang tanggal pemeriksaan ──────────────────────────────────────

def test_rentang_tanggal_menyaring_menurut_stempel(dbf):
    async def jalan():
        await _seed(dbf)
        d = await rp._build_satker_report_v2(
            "k1", {"dari": "2025-07-01", "sampai": "2025-07-31"})
        assert d["total_count"] == 2, d["total_count"]
        assert d["filter_aktif"] is True
    _jalan(jalan())


def test_aset_tanpa_stempel_keluar_saat_rentang_diisi(dbf):
    """Menanyakan "yang diperiksa Agustus" lalu menerima aset yang tanggal
    periksanya tak diketahui akan menjawab pertanyaan yang berbeda."""
    async def jalan():
        await _seed(dbf)
        d = await rp._build_satker_report_v2("k1", {"dari": "2020-01-01"})
        assert d["total_count"] == 4, "hanya yang bercap"
    _jalan(jalan())


# ── Helper murni ────────────────────────────────────────────────────────

def test_nilai_kosong_dibuang_bukan_dianggap_pilihan():
    """`?tahun=` dari formulir tanpa centang tak boleh berubah makna menjadi
    'hanya aset tanpa tahun'."""
    assert lf.bersihkan(["", "  ", None]) == []
    assert lf.bersihkan(["2023", "2023", " 2024 "]) == ["2023", "2024"]
    assert lf.bersihkan("2023") == ["2023"]
    assert lf.bersihkan(None) == []


def test_ada_yang_aktif_mengenali_setiap_dimensi():
    for f in ({"kegiatan": ["k1"]}, {"tahun": ["2023"]}, {"status": ["Ditemukan"]},
              {"kondisi": ["Baik"]}, {"lokasi": ["L1"]}, {"dari": "2025-01-01"},
              {"sampai": "2025-12-31"}):
        assert lf.ada_yang_aktif(f) is True, f
    for f in (None, {}, {"tahun": []}, {"dari": "", "sampai": ""}):
        assert lf.ada_yang_aktif(f) is False, f


# ── Layar ───────────────────────────────────────────────────────────────

def _tpl():
    with open(TPL, encoding="utf-8") as f:
        return f.read()


def test_panel_filter_hanya_di_pratinjau():
    """Panel tak boleh ikut tercetak — kotak centang di atas kertas adalah
    ruang terbuang, dan pembaca kertas tak bisa menekannya.

    Yang diuji SIFATNYA, bukan nama kelasnya: perombakan tampilan boleh
    mengganti nama, tetapi tak boleh menghilangkan `no-print` dari formulir
    maupun dari bilah aksinya.
    """
    t = _tpl()
    form = re.search(r"<form[^>]*id=\"form-filter\"[^>]*>", t)
    assert form, "formulir filter hilang"
    assert "no-print" in form.group(0), "panel filter akan ikut tercetak"
    bilah = re.search(r'<div class="bilah[^"]*"', t)
    assert bilah and "no-print" in bilah.group(0), "bilah aksi akan ikut tercetak"


def test_penyaringan_di_server_bukan_di_peramban():
    """Menyaring di sisi peramban membuat PDF dan layar berbeda tanpa gejala:
    tombol Cetak memanggil endpoint lain yang tak tahu apa-apa soal filternya."""
    t = _tpl()
    form = re.search(r"<form[^>]*id=\"form-filter\"[^>]*>", t)
    assert form and 'method="get"' in form.group(0)


def test_laporan_tersaring_menyatakan_dirinya_DI_KERTAS():
    """Di layar ada panel filter yang membantah salah baca; di kertas tidak
    ada. Justru di sanalah penandanya paling dibutuhkan."""
    t = _tpl()
    i = t.index('data-testid="pita-filter"')
    assert "no-print" not in t[i - 400:i], "penanda ikut disembunyikan saat cetak"
    assert "bukan keseluruhan satker" in t


def test_pdf_memakai_filter_yang_sama():
    """Tombol Cetak pada laporan tersaring tak boleh menghasilkan PDF berisi
    seluruh satker — dokumen yang isinya berbeda dari yang barusan dibaca."""
    import inspect
    src = inspect.getsource(rp.laporan_satker_pdf)
    assert "_filter_laporan_satker(" in src


# ── Bilah aksi melekat: navigasi ────────────────────────────────────────

def test_tombol_terapkan_selalu_terjangkau():
    """Pada satker dengan puluhan lokasi, panel filternya panjang. Tombol
    Terapkan yang ikut tergulir memaksa pengguna menggulir balik ke atas
    hanya untuk menekannya — dan itu terasa seperti alat yang melawan."""
    t = _tpl()
    assert "position: sticky" in t, "bilah aksi tidak melekat"
    # Tombol di bilah menyerahkan formulir yang berada DI LUAR dirinya;
    # tanpa atribut `form` ia hanya tombol mati yang tampak bisa ditekan.
    assert 'form="form-filter"' in t


def test_panel_filter_dapat_dilipat():
    """Laporan dibaca lebih sering daripada disaring; panel yang selalu
    terbuka mendorong halaman pertama ke bawah setiap kali dibuka."""
    t = _tpl()
    assert 'id="lipat-filter"' in t
    assert "panel.hidden" in t


# ── Token autentikasi harus SELAMAT saat filter diterapkan ──────────────
#
# Cacat nyata di produksi: menekan "Terapkan Filter" menghasilkan
# {"detail":"Autentikasi diperlukan"}. Pratinjau dibuka lewat `window.open`
# yang tak bisa mengirim header Authorization, jadi tokennya dititip di
# `?token=<jwt>&sa=<satker>`. Formulir `method="get"` MENGGANTI seluruh query
# string dengan isiannya sendiri — perilaku HTML, bukan kekeliruan peramban —
# sehingga tokennya terbuang dan server menolak permintaannya.

class _QueryPalsu:
    def __init__(self, pasangan):
        self._p = list(pasangan)

    def multi_items(self):
        return list(self._p)


class _PermintaanPalsu:
    def __init__(self, pasangan):
        self.query_params = _QueryPalsu(pasangan)


def test_parameter_di_luar_filter_ikut_terbawa():
    """Daftarnya UMUM, bukan nama yang dihafal: parameter baru yang
    ditambahkan kelak ikut selamat tanpa memperbaiki cacat yang sama untuk
    kedua kalinya."""
    req = _PermintaanPalsu([
        ("token", "jwt-abc"), ("sa", "401234"),
        ("tahun", "2023"), ("kegiatan", "k1"), ("dari", "2025-01-01"),
        ("param_baru_kelak", "x"),
    ])
    bawaan = rp._param_bukan_filter(req)
    assert ("token", "jwt-abc") in bawaan
    assert ("sa", "401234") in bawaan
    assert ("param_baru_kelak", "x") in bawaan
    # Isian filter TIDAK boleh ikut jadi input tersembunyi — kalau ikut, ia
    # terkirim dua kali dan centang yang dilepas tak pernah benar-benar lepas.
    for nama in ("tahun", "kegiatan", "dari"):
        assert all(k != nama for k, _ in bawaan), nama


def test_formulir_menitipkan_kembali_parameter_bawaan():
    t = _tpl()
    assert '{% for nama, nilai in (param_bawaan or []) %}' in t
    assert 'type="hidden"' in t


def test_tautan_tampilkan_semua_tak_membuang_token():
    """`href="?"` polos membuang token yang sama — cacat yang persis serupa,
    hanya di tombol yang berbeda."""
    t = _tpl()
    i = t.index('data-testid="filter-reset"')
    potongan = t[i - 400:i]
    assert "param_bawaan" in potongan, "tautan reset masih memakai ? polos"


def test_rute_html_meneruskan_request():
    """Tanpa `request`, rute tak punya cara membaca parameter bawaan."""
    import inspect
    tanda = inspect.signature(rp.laporan_satker_html)
    assert "request" in tanda.parameters
    assert "_param_bukan_filter(request)" in inspect.getsource(rp.laporan_satker_html)


# ── Panel filter selebar lembar A4 ─────────────────────────────────────

def test_panel_filter_selebar_lembar_A4():
    """Umpan balik pemilik: *"bagian filter juga masih belum responsive
    menyesuaikan A4nya"*. Panel yang melebar mengikuti layar akan lebih sempit
    dari lembarnya di ponsel dan lebih lebar di monitor — terbaca sebagai dua
    dokumen yang kebetulan bertumpuk, bukan satu laporan."""
    t = _tpl()
    assert ".panel-filter { width: 794px;" in t
    assert re.search(r"\.bilah \{[^}]*width: 794px", t), "bilah tak selebar lembar"
    assert "max-width: 794px" not in t, "masih ada yang melebar mengikuti layar"
