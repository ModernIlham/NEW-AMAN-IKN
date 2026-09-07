"""Halaman "Analisis Lanjutan, Tim & Cakupan Data" — tanpa potongan, tanpa
kertas terbuang, tanpa baris yang hilang.

Permintaan pemilik: *"jadikan smart semua dalam mengatur posisinya
masing-masing menyesuaikan bagaimana caranya berbagi dan mengalah untuk
menampilkan informasi sebaik mungkin tanpa harus melanjutkan ke halaman kedua
dengan memaksimalkan A4 yang ada tanpa harus menggunakan '…' dan terpampang
dengan baik."*

Halaman ini dulu disusun TETAP: pasangan bloknya ditulis tangan di templat,
lebar kolom label dipatok 100px, dan yang tak muat dipotong — nama unit pada 25
huruf, nama kategori pada 20. Akibatnya berlawanan sekaligus dan sama-sama tak
berbunyi: seperlima kertas menganggur di bawah sementara "Kedeputian Bidang
Transformasi Hijau dan Digital" tercetak "Kedeputian Bidang Transfo".
"""
import asyncio
import os
import re

import pytest
from mongomock_motor import AsyncMongoMockClient

import laporan_blok as lbk
import routes.reports as rp

TPL = os.path.join(os.path.dirname(__file__), "..", "..", "templates",
                   "executive_summary.html")

#: Nama unit dan kategori yang PANJANG — di sinilah pemotongan dulu terjadi.
UNIT_A = "Kedeputian Bidang Transformasi Hijau dan Digital"
UNIT_B = "Kedeputian Bidang Pengendalian Pembangunan"
KATEGORI = [
    "Alat Laboratorium Pendidikan Kedokteran Lainnya",
    "Network Attach Storage (NAS) Kapasitas Besar",
    "Printer (Peralatan Personal Komputer)",
    "CCTV - Camera Control Television",
    "Handy Talky (HT)", "Note Book", "Kabel", "Tablet PC",
    "Papan Pengumuman", "Camera Digital", "Dehumidifier", "Televisi",
]


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
    return fake


def _anggota(n, awalan, unit=UNIT_B):
    return [{"nama": f"{awalan} Bernama Cukup Panjang Nomor {i}",
             "jabatan": "Analis Pengelolaan Barang Milik Negara Ahli Pertama",
             "nip": f"19900101202001{i:04d}", "unit": unit} for i in range(n)]


async def _seed(fake, kategori=KATEGORI, tim_inti=None, tim_pembantu=None,
                tim_peneliti=None, tim_pendukung=None):
    await fake.inventory_activities.insert_one({
        "id": "k1", "kode_satker": "691778", "nama_satker": "SATKER D",
        "nama_kegiatan": "Inventarisasi 2026", "nomor_surat": "S-1",
        "tanggal_mulai": "2026-01-01", "tanggal_selesai": "2026-06-30",
        "created_at": "2026-01-01",
        "penanggung_jawab": "Karlinus Ignasius Manek",
        "penanggung_jawab_jabatan": "Analis Kebijakan Ahli Madya",
        "penanggung_jawab_nip": "198206022001121003",
        "tim_inti": tim_inti if tim_inti is not None else _anggota(4, "Anggota Inti"),
        "tim_pembantu": tim_pembantu or [],
        "tim_peneliti": (tim_peneliti if tim_peneliti is not None
                         else _anggota(1, "Peneliti")),
        "tim_pendukung": tim_pendukung or [],
    })
    n = 0
    for i, nama in enumerate(kategori):
        for _ in range(3 + i):
            n += 1
            await fake.assets.insert_one({
                "id": f"a{n}", "activity_id": "k1", "asset_name": nama,
                "asset_code": f"3{i:02d}0101{i:03d}", "NUP": str(n),
                "purchase_price": 1000, "purchase_date": "2023-01-01",
                "category": nama, "eselon1": UNIT_A if n % 3 else UNIT_B,
                "inventory_status": "Ditemukan",
                "condition": "Baik" if n % 5 else "Rusak Ringan",
            })


def _data(dbx, **kw):
    _jalan(_seed(dbx, **kw))
    return _jalan(rp._build_executive_summary_data("k1", with_asset_rows=False))


def _render(d):
    return rp._jinja_env().get_template("executive_summary.html").render(
        preview=False, **d)


def _halaman_analisis(html):
    """Potongan HTML seluruh lembar Analisis — dirender, bukan dibaca sumber."""
    awal = html.index("<h1>Analisis Lanjutan")
    # Lembar analisis selalu yang terakhir pada laporan ini.
    return html[awal:]


# ── 1. Tak ada satu pun nama yang dipotong ──────────────────────────────

def test_nama_unit_dan_kategori_TERCETAK_UTUH(dbx):
    """Potongan membuang justru bagian yang membedakan: dua Kedeputian
    berawalan sama menjadi teks yang sama persis, dan pada cetakan tak ada
    tooltip yang mengembalikannya."""
    d = _data(dbx)
    blok = _halaman_analisis(_render(d))
    for nama in (UNIT_A, UNIT_B):
        assert nama in blok, f"nama unit terpotong: {nama}"
    for nama in KATEGORI[:8]:
        assert nama in blok, f"nama kategori terpotong: {nama}"


def test_payload_TIDAK_memotong_nama(dbx):
    # Pemotongan di Python tak meninggalkan "…" sama sekali — ia hanya
    # memendekkan, jadi memeriksa "…" saja tak pernah menangkapnya.
    d = _data(dbx)
    assert {e["name"] for e in d["eselon_chart"]} == {UNIT_A, UNIT_B}
    for c in d["cond_by_cat"]:
        assert c["name"] in KATEGORI, c["name"]


def test_label_TIDAK_dipotong_dengan_ellipsis():
    with open(TPL, encoding="utf-8") as f:
        tpl = f.read()
    for kelas in (".hbar-label {", ".sbar-label {"):
        awal = tpl.index(kelas)
        blok = tpl[awal:tpl.index("}", awal)]
        assert "text-overflow" not in blok, f"{kelas} masih memotong"
        assert "white-space: normal" in blok, kelas


def test_lebar_label_DIHITUNG_dari_isinya(dbx):
    """Dipatok 100px nama unit terpotong; dipatok selebar nama terpanjang
    palangnya tinggal secuil. Karena itu ia isi-yang-dibutuhkan, dibatasi
    bagian dari lebar yang tersisa."""
    d = _data(dbx)
    # Label tahun ("2023") jauh lebih pendek daripada label unit.
    assert d["lbl_tahun_px"] < d["lbl_eselon_px"]
    # …dan tak satu pun memakan seluruh baris.
    assert d["lbl_eselon_px"] < lbk.lebar_lajur(2)
    assert d["lbl_kondisi_px"] < lbk.LEBAR_ISI / 2


# ── 2. Kertas dipakai, bukan dibiarkan putih ────────────────────────────

def _jarak_isi_ke_kaki(d):
    """Jarak bawah-isi ke kaki halaman pada tiap lembar analisis."""
    import weasyprint

    doc = weasyprint.HTML(string=_render(d),
                          base_url=os.path.dirname(TPL)).render()

    def kelas(b):
        e = b.element
        return (e.get("class") or "").split() if e is not None else []

    def kumpul(b, out, nama):
        if nama in kelas(b):
            out.append(b)
        for c in getattr(b, "children", []):
            kumpul(c, out, nama)

    jarak = []
    for p in doc.pages:
        baris, kaki = [], []
        kumpul(p._page_box, baris, "blok-baris")
        kumpul(p._page_box, kaki, "exec-footer")
        if baris and kaki:
            jarak.append(min(f.position_y for f in kaki)
                         - max(b.position_y + b.height for b in baris))
    return jarak


def test_isi_TIDAK_menindih_kaki_halaman(dbx):
    d = _data(dbx, tim_pembantu=_anggota(30, "Anggota Pembantu"))
    jarak = _jarak_isi_ke_kaki(d)
    assert jarak, "tak satu lembar analisis pun terukur"
    assert min(jarak) > 0, f"isi menindih kaki halaman: {min(jarak):.0f}px"


def test_daftar_kategori_MEMANJANG_mengisi_ruang_yang_tersisa(dbx):
    """Kertas yang tersisa lebih berguna diisi baris data daripada dibiarkan
    putih. Daftarnya mulai dari 8 dan memanjang selama ruangnya ada."""
    d = _data(dbx)
    assert len(d["cond_by_cat"]) > 8, "daftar kategori tak memanjang sama sekali"
    assert len(d["cond_by_cat"]) <= len(KATEGORI)


#: Kategori bernama SANGAT panjang: begitu daftarnya memanjang, baris-baris
#: barunya membungkus dua-tiga kali dan memakan ruang jauh melebihi taksiran
#: "satu baris per kategori" yang dipakai menghitung berapa yang muat.
KATEGORI_PANJANG = [f"Kabel {i}" for i in range(8)] + [
    "Alat Laboratorium Pendidikan Kedokteran Bedah Perawatan Intensif dan "
    f"Rehabilitasi Medik Terpadu Bergerak Nomor Seri {i:02d}" for i in range(14)]


def test_memanjangnya_daftar_TIDAK_menambah_lembar(dbx):
    """Penjaga yang membatalkan pertumbuhan bukan hiasan.

    Berapa baris yang muat ditaksir dari baris SEBARIS; kategori bernama
    panjang membungkus dua-tiga kali, sehingga tambahannya memakan lebih
    banyak daripada ruang yang ada. Tanpa penjaga, laporan yang seharusnya
    selembar menjadi dua lembar — persis yang diminta pemilik untuk dihindari.
    """
    d = _data(dbx, kategori=KATEGORI_PANJANG)
    assert len(d["rencana_analisis"]["halaman"]) == 1, (
        "daftar kategori memanjang sampai menambah lembar")


def test_memanjangnya_daftar_TIDAK_mendorong_blok_ke_lembar_lain(dbx):
    """Menambah baris kategori dengan harga mendorong Tim Inventarisasi ke
    lembar berikutnya bukan memaksimalkan kertas, melainkan menukar satu
    kekosongan dengan kekosongan yang lebih besar."""
    d = _data(dbx, tim_pembantu=_anggota(6, "Anggota Pembantu"))
    hal = d["rencana_analisis"]["halaman"]
    id_lembar1 = [x["id"] for b in hal[0] for x in b["blok"]]
    # Blok tim TETAP di lembar pertama meski daftar kategorinya memanjang.
    assert "tim_internal" in id_lembar1, id_lembar1


# ── 3. Blok berbagi baris, dan lembar kedua hanya bila perlu ────────────

def test_blok_pendek_BERBAGI_baris(dbx):
    d = _data(dbx)
    pasangan = [[x["id"] for x in b["blok"]]
                for hal in d["rencana_analisis"]["halaman"] for b in hal]
    assert ["tahun", "eselon"] in pasangan
    assert ["status", "cakupan"] in pasangan
    # Penanggung Jawab dan Tim Peneliti sama-sama kartu pendek.
    assert ["pj", "peneliti"] in pasangan


def test_data_yang_MUAT_tetap_satu_lembar(dbx):
    d = _data(dbx)
    assert len(d["rencana_analisis"]["halaman"]) == 1


def test_lembar_kedua_hanya_saat_memang_tak_muat(dbx):
    d = _data(dbx, tim_pembantu=_anggota(60, "Anggota Pembantu"))
    assert len(d["rencana_analisis"]["halaman"]) > 1


# ── 4. Tak satu anggota tim pun hilang dari cetakan ─────────────────────

@pytest.mark.parametrize("banyak", [6, 60, 120])
def test_anggota_tim_TIDAK_hilang_dari_cetakan(dbx, banyak):
    """Blok yang tak dapat dipecah ditempatkan utuh pada satu lembar, dan
    sisanya terpotong senyap oleh `overflow: hidden` — tanpa satu pun galat,
    tanpa satu pun tanda di HTML-nya. Diuji dengan merender ke PDF lalu
    mencari tiap nama di teksnya."""
    import tempfile

    import pypdfium2
    import weasyprint

    pembantu = _anggota(banyak, "Anggota Pembantu")
    d = _data(dbx, tim_pembantu=pembantu)
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        weasyprint.HTML(string=_render(d),
                        base_url=os.path.dirname(TPL)).write_pdf(f.name)
        teks = re.sub(r"\s+", " ", "\n".join(
            p.get_textpage().get_text_range()
            for p in pypdfium2.PdfDocument(f.name)))
    hilang = [t["nama"] for t in pembantu
              if re.sub(r"\s+", " ", t["nama"]) not in teks]
    assert not hilang, f"{len(hilang)} anggota hilang dari cetakan: {hilang[:3]}"


def test_halaman_PDF_sama_banyak_dengan_lembar_HTML(dbx):
    import tempfile

    import pypdfium2
    import weasyprint

    d = _data(dbx, tim_pembantu=_anggota(40, "Anggota Pembantu"),
              tim_pendukung=_anggota(5, "Pendukung"))
    html = _render(d)
    lembar = len(re.findall(r'<div class="(?:exec|cover)-page"', html))
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        weasyprint.HTML(string=html,
                        base_url=os.path.dirname(TPL)).write_pdf(f.name)
        halaman = len(pypdfium2.PdfDocument(f.name))
    assert lembar == halaman, f"{halaman - lembar} halaman yatim"


# ── 5. Tinggi yang dimodelkan harus sama dengan yang tergambar ──────────

def test_tinggi_blok_SESUAI_yang_tergambar(dbx):
    """Tetapan geometri di `laporan_blok` adalah pasangan dari CSS-nya.

    Begitu CSS-nya digeser — satu piksel padding, satu baris judul — angka di
    modul itu diam-diam berbohong, dan penata halaman memutuskan dengan tinggi
    yang bukan tinggi sebenarnya. Tak ada galat yang muncul; yang muncul
    halaman yang meluber atau kertas yang menganggur.
    """
    import weasyprint

    d = _data(dbx, tim_pembantu=_anggota(3, "Anggota Pembantu"))
    doc = weasyprint.HTML(string=_render(d),
                          base_url=os.path.dirname(TPL)).render()

    def kelas(b):
        e = b.element
        return (e.get("class") or "").split() if e is not None else []

    tergambar = []
    for p in doc.pages:
        def cari(b):
            if "blok-baris" in kelas(b):
                tergambar.append(b.height)
                return
            for c in getattr(b, "children", []):
                cari(c)
        cari(p._page_box)

    dimodelkan = [b["tinggi"] for hal in d["rencana_analisis"]["halaman"]
                  for b in hal]
    assert len(tergambar) == len(dimodelkan), (
        f"{len(tergambar)} baris tergambar, {len(dimodelkan)} dimodelkan")
    for nyata, model in zip(tergambar, dimodelkan):
        assert model >= nyata - 2, (
            f"taksiran {model:.1f}px lebih pendek daripada yang tergambar "
            f"{nyata:.1f}px — halamannya akan meluber")
        assert model <= nyata + 30, (
            f"taksiran {model:.1f}px jauh melebihi yang tergambar "
            f"{nyata:.1f}px — kertas terbuang")
