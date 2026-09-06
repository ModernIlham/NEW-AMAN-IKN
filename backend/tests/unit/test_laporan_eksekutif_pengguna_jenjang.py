"""Distribusi Per Pengguna pada Laporan Eksekutif — dibagi jalur eselon.

Permintaan pemilik: *"pada data distribusi per pengguna buat sama seperti
sebelumnya dengan, pada bagian unit kerja menjadi pembagi row langsung mulai
dari eselon I-V sesuai satker menginduk kemana karena mengingat juga tergantung
kondisi satkernya. dan pada bagian kolom unit kerjanya nanti digantikan dengan
jabatan … apabila menjadi 2 kolom, maka gabungkan kolom Nama dan NIP/NIK agar
menghemat ruang juga."*

Daftar sebelumnya RATA dengan kolom "Unit Kerja" yang mencetak nama Direktorat
yang sama dua puluh kali — lebar terpakai tanpa satu pun keterangan tambahan.
Sebagai PEMBAGI baris nama itu tercetak sekali, dan lebarnya kembali kepada
nama serta jabatan.
"""
import asyncio
import os

import pytest
from mongomock_motor import AsyncMongoMockClient

import laporan_jenjang as ljj
import routes.reports as rp

TPL = os.path.join(os.path.dirname(__file__), "..", "..", "templates",
                   "executive_summary.html")


def _teks_tpl():
    with open(TPL, encoding="utf-8") as f:
        return f.read()


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


#: (nip, nama, jabatan, eselon1, eselon2, eselon3, banyak aset)
PEGAWAI = [
    ("1990", "Budi Santoso", "Analis Barang Milik Negara", "SEKRETARIAT JENDERAL",
     "BIRO UMUM", "BAGIAN RUMAH TANGGA", 4),
    ("1991", "Siti Aminah", "Pengelola Barang Persediaan", "SEKRETARIAT JENDERAL",
     "BIRO UMUM", "BAGIAN PERLENGKAPAN", 3),
    ("1992", "Andi Wijaya", "Kepala Subbagian", "SEKRETARIAT JENDERAL",
     "BIRO KEUANGAN", "BAGIAN AKUNTANSI", 2),
    ("1993", "Rina Marlina", "Pranata Komputer", "DIREKTORAT JENDERAL A",
     "DIREKTORAT B", "SUBDIREKTORAT C", 1),
]


async def _seed(fake, eselon_satker=1, pegawai=PEGAWAI, tanpa_nip=0,
                tak_terdaftar=0):
    await fake.inventory_activities.insert_one(
        {"id": "k1", "kode_satker": "691778", "nama_satker": "SATKER D",
         "nama_kegiatan": "Inventarisasi 2026", "nomor_surat": "S-1",
         "tanggal_mulai": "2026-01-01", "tanggal_selesai": "2026-06-30",
         "created_at": "2026-01-01"})
    await fake.satker.insert_one(
        {"kode_satker": "691778", "nama_satker": "SATKER D",
         "eselon_satker": eselon_satker})
    n = 0
    for nip, nama, jabatan, e1, e2, e3, banyak in pegawai:
        await fake.pegawai.insert_one(
            {"nip": nip, "nama": nama, "jabatan": jabatan,
             "unit_kerja": e3, "kode_satker": "691778",
             "eselon1": e1, "eselon2": e2, "eselon3": e3})
        for _ in range(banyak):
            n += 1
            await fake.assets.insert_one(
                {"id": f"a{n}", "activity_id": "k1", "asset_name": "Meja",
                 "asset_code": "3050104001", "NUP": str(n),
                 "purchase_price": 1000 * banyak, "purchase_date": "2023-01-01",
                 "pengguna_nip": nip, "user": nama,
                 "eselon1": e1, "eselon2": e2, "eselon3": e3,
                 "inventory_status": "Belum Diinventarisasi"})
    for i in range(tanpa_nip):
        n += 1
        await fake.assets.insert_one(
            {"id": f"t{i}", "activity_id": "k1", "asset_name": "Kursi",
             "asset_code": "3050104002", "NUP": str(n), "purchase_price": 100,
             "purchase_date": "2023-01-01",
             "inventory_status": "Belum Diinventarisasi"})
    for i in range(tak_terdaftar):
        n += 1
        await fake.assets.insert_one(
            {"id": f"x{i}", "activity_id": "k1", "asset_name": "Lemari",
             "asset_code": "3050104003", "NUP": str(n), "purchase_price": 200,
             "purchase_date": "2023-01-01", "pengguna_nip": f"88{i}",
             "user": "Pegawai Luar Master",
             "inventory_status": "Belum Diinventarisasi"})


def _data(dbx, **kw):
    _jalan(_seed(dbx, **kw))
    return _jalan(rp._build_executive_summary_data("k1", with_asset_rows=False))


# ── 1. Unit kerja jadi PEMBAGI, bukan kolom yang berulang ───────────────

def test_pengguna_dibagi_menurut_jalur_eselon(dbx):
    d = _data(dbx)
    kelompok = [b["name"] for b in d["pengguna_hier"] if not b.get("daun")]
    assert "SEKRETARIAT JENDERAL" in kelompok
    assert "BIRO UMUM" in kelompok and "BIRO KEUANGAN" in kelompok
    assert "BAGIAN RUMAH TANGGA" in kelompok
    # Nama unitnya tercetak SEKALI sebagai pembagi — bukan sekali per pegawai.
    assert kelompok.count("SEKRETARIAT JENDERAL") == 1


def test_tiap_pengguna_muncul_TEPAT_SEKALI_sebagai_daun(dbx):
    """Cabang yang dirapatkan pernah menelan penggunanya tanpa satu pun tanda.

    Daun ditempelkan pada baris TERDALAM cabangnya; menempelkannya pada
    kedalaman tetap membuat pegawai di cabang yang lebih pendek lenyap dari
    laporan sementara datanya tetap hidup di basis data.
    """
    d = _data(dbx, tanpa_nip=2, tak_terdaftar=1)
    daun = [b["name"] for b in d["pengguna_hier"] if b.get("daun")]
    for _, nama, *_rest in PEGAWAI:
        assert daun.count(nama) == 1, nama
    assert "Pegawai Luar Master" in daun
    assert any("Tanpa Pengguna" in n for n in daun)


def test_induk_berjumlah_PERSIS_sama_dengan_keturunannya(dbx):
    d = _data(dbx)
    baris = d["pengguna_hier"]
    for i, b in enumerate(baris):
        if b.get("daun"):
            continue
        anak = [x for j, x in enumerate(baris[i + 1:], i + 1)
                if x["depth"] == b["depth"] + 1
                and all(y["depth"] > b["depth"] for y in baris[i + 1:j])]
        assert sum(a["count"] for a in anak) == b["count"], b["name"]


def test_total_diambil_dari_jenjang_TERATAS_saja(dbx):
    # Menjumlahkan SELURUH baris menghitung tiap aset sekali per jenjang.
    d = _data(dbx, tanpa_nip=2)
    assert d["pengguna_total"]["count"] == d["total_count"]
    assert sum(b["count"] for b in d["pengguna_hier"]) > d["total_count"]


# ── 2. Jenjangnya mengikuti tingkat satkernya ───────────────────────────

def test_satker_ESELON_III_tak_dibagi_mulai_dari_Eselon_I(dbx):
    """Satker Eselon III tak punya Eselon I sendiri.

    Membaginya mulai dari Eselon I melahirkan satu kelompok yang memuat seluruh
    pegawainya — sebaris pembagi yang tak membagi apa pun, memakan tinggi
    halaman tanpa menerangkan apa pun.
    """
    d = _data(dbx, eselon_satker=3)
    assert d["pengguna_jenjang_label"][-1] == "Pengguna"
    assert "Eselon I" not in d["pengguna_jenjang_label"][:-1]
    assert "Eselon III" in d["pengguna_jenjang_label"]


def test_satker_kantor_pusat_tetap_dibagi_dari_Eselon_I(dbx):
    d = _data(dbx, eselon_satker=1)
    assert d["pengguna_jenjang_label"][0] == "Eselon I"


def test_label_jenjang_MENYEBUT_jenjang_yang_benar_benar_dipakai(dbx):
    # Legenda yang menyebut lima jenjang untuk pohon berjenjang tiga menerangkan
    # warna yang tak pernah tergambar.
    d = _data(dbx)
    dalam = max(b["depth"] for b in d["pengguna_hier"])
    assert len(d["pengguna_jenjang_label"]) == dalam + 1


def test_jenjang_KOSONG_tak_ditawarkan(dbx):
    # Eselon IV dan V tak diisi satu pegawai pun — menawarkannya hanya
    # melahirkan kelompok "(tanpa unit organisasi)" berisi semua orang.
    d = _data(dbx)
    assert "Eselon IV" not in d["pengguna_jenjang_label"]
    assert "Eselon V" not in d["pengguna_jenjang_label"]


def test_tanpa_jenjang_berdata_daftarnya_RATA_bukan_kosong(dbx):
    # Pegawai tanpa jalur eselon sama sekali tetap harus terlihat.
    peg = [("1990", "Budi Santoso", "Analis", "", "", "", 3)]
    d = _data(dbx, pegawai=peg)
    daun = [b for b in d["pengguna_hier"] if b.get("daun")]
    assert [b["name"] for b in daun] == ["Budi Santoso"]
    assert all(b["depth"] == 0 for b in daun)


# ── 3. Kolom Jabatan menggantikan Unit Kerja ────────────────────────────

def test_baris_pengguna_membawa_JABATAN_bukan_unit_kerja(dbx):
    d = _data(dbx)
    daun = {b["name"]: b for b in d["pengguna_hier"] if b.get("daun")}
    assert daun["Budi Santoso"]["jabatan"] == "Analis Barang Milik Negara"
    assert daun["Andi Wijaya"]["jabatan"] == "Kepala Subbagian"


def test_templat_mencetak_kolom_Jabatan_bukan_Unit_Kerja():
    tpl = _teks_tpl()
    awal = tpl.index("{% macro kepala_dist(")
    kepala = tpl[awal:tpl.index("{%- endmacro %}", awal)]
    assert ">Jabatan</th>" in kepala
    assert "Unit Kerja" not in kepala, "kolom lama masih memakan lebar"


def test_lebar_kolom_dipasang_di_BARIS_KEPALA():
    """`table-layout: fixed` membaca lebar kolom dari baris PERTAMA saja.

    Selama lebarnya hanya tertulis pada `<td>`, tak satu pun terpakai: ketiga
    kolom dibagi rata dan kolom nama tinggal sepertiga tabel — terukur 106px
    dari 226px yang semestinya. Namanya lalu membungkus dua sampai tiga kali
    lebih sering, halaman terisi baris yang seharusnya sebaris, dan tak ada
    satu pun galat yang menyebutkannya. Ia hanya tampak sebagai laporan yang
    boros kertas.
    """
    tpl = _teks_tpl()
    awal = tpl.index("{% macro kepala_dist(")
    kepala = tpl[awal:tpl.index("{%- endmacro %}", awal)]
    for kelas in ("hier-name", "sel-nip", "sel-jabatan", "val-cell",
                  "money-cell", "hier-bar-cell"):
        assert kelas in kepala, f"kepala tabel tak membawa kelas {kelas}"


def test_kolom_nama_mendapat_lebar_TERBESAR_saat_dirender(dbx):
    """Diukur pada render sungguhan, bukan dibaca dari CSS.

    Aturan lebarnya tersebar di beberapa selektor dan bergantung pada baris
    mana yang dibaca `table-layout: fixed`; satu-satunya jawaban yang dapat
    dipercaya datang dari kotak yang benar-benar tergambar.
    """
    import weasyprint
    d = _data(dbx)
    html = rp._jinja_env().get_template("executive_summary.html").render(
        preview=False, **d)
    doc = weasyprint.HTML(string=html, base_url=os.path.dirname(TPL)).render()

    lebar = {}

    def jalan(b):
        e = b.element
        k = (e.get("class") or "") if e is not None else ""
        for nama in ("hier-name", "val-cell", "money-cell"):
            if nama in k.split():
                lebar.setdefault(nama, b.width)
        for c in getattr(b, "children", []):
            jalan(c)

    for p in doc.pages:
        jalan(p._page_box)
    assert lebar.get("hier-name", 0) > 300, (
        f"kolom nama cuma {lebar.get('hier-name')}px — lebarnya tak terpakai")
    assert lebar["hier-name"] > lebar["money-cell"] * 3


def test_batang_hanya_pada_baris_PENGGUNA_bukan_pembagi(dbx):
    d = _data(dbx)
    for b in d["pengguna_hier"]:
        # Pada baris pembagi, batang membandingkan induk dengan anaknya — dua
        # besaran yang salah satunya memuat yang lain.
        assert ("bar_pct" in b) == bool(b.get("daun")), b["name"]


# ── 4. Dua kolom: Nama & NIP menyatu, batang menghilang ─────────────────

def test_daftar_pendek_tetap_SATU_kolom_berbatang(dbx):
    d = _data(dbx)
    assert d["rencana_peg"]["kolom"] == 1
    assert d["rencana_peg"]["batang"] is True


def test_daftar_panjang_pindah_DUA_kolom_dan_batangnya_hilang(dbx):
    banyak = [(f"20{i:03d}", f"Pegawai Dengan Nama Panjang Sekali {i}",
               "Pengelola Barang Milik Negara Tingkat Ahli Pertama",
               "SEKRETARIAT JENDERAL", f"BIRO {i % 3}", f"BAGIAN {i % 5}", 1)
              for i in range(60)]
    d = _data(dbx, pegawai=banyak)
    assert d["rencana_peg"]["kolom"] == 2
    assert d["rencana_peg"]["batang"] is False


def test_templat_MENGGABUNG_Nama_dan_NIP_hanya_saat_dua_kolom():
    tpl = _teks_tpl()
    assert "{% set gabung = (jenis == 'pengguna' and rencana.kolom == 2) %}" in tpl
    awal = tpl.index("{% macro sel_dist(")
    sel = tpl[awal:tpl.index("{%- endmacro %}", awal)]
    # Satu kolom: NIP punya selnya sendiri. Dua kolom: ia turun ke bawah nama.
    assert '{%- if not gabung %}<td class="sel-nip">' in sel
    assert '<span class="sel-nip-gabung">' in sel


def test_tinggi_baris_dua_kolom_MEMPERHITUNGKAN_NIP_yang_turun(dbx):
    """NIP yang turun ke bawah nama menambah satu baris teks per pengguna.

    Menaksir tingginya dengan angka satu kolom membuat halamannya meluber, dan
    lembar `overflow: hidden` memotongnya tanpa satu pun galat — kaki halaman
    terdorong ke lembar berikutnya dan lahirlah halaman berisi kaki saja.
    """
    import laporan_kolom as lkl
    nama = "Budi Santoso"
    daun = {"name": nama, "jabatan": "", "depth": 1, "daun": True}
    grup = {"name": nama, "jabatan": "", "depth": 1}
    assert lkl.tinggi_pengguna(daun, 2) == lkl.tinggi_pengguna(grup, 2) + 1
    assert lkl.tinggi_pengguna(daun, 1) == lkl.tinggi_pengguna(grup, 1), \
        "satu kolom: NIP punya selnya sendiri, tak menambah tinggi"
    assert lkl.KAR_NAMA_2 < lkl.KAR_NAMA_1


def test_tinggi_baris_pengguna_diambil_dari_kolom_TERTINGGI(dbx):
    # Jabatan bisa lebih panjang daripada namanya. Menaksir tinggi baris dari
    # nama saja membuat halaman berjabatan panjang meluber diam-diam.
    import laporan_kolom as lkl
    pendek = {"name": "Budi", "jabatan": "Analis", "depth": 1, "daun": True}
    panjang = {"name": "Budi", "daun": True, "depth": 1,
               "jabatan": "Pengelola Barang Milik Negara Tingkat Ahli Pertama "
                          "pada Bagian Rumah Tangga"}
    assert lkl.tinggi_pengguna(panjang, 1) > lkl.tinggi_pengguna(pendek, 1)


# ── 5. Nama panjang DIBUNGKUS, bukan dipotong "…" ───────────────────────

def test_nama_dibungkus_ke_bawah_bukan_dipotong(dbx):
    tpl = _teks_tpl()
    for aturan in (".hier-table .hier-name {", ".hier-table .sel-jabatan {"):
        awal = tpl.index(aturan)
        blok = tpl[awal:tpl.index("}", awal)]
        assert "white-space: normal" in blok, aturan
        assert "overflow-wrap: break-word" in blok, aturan
        assert "text-overflow" not in blok, f"{aturan} masih memotong"
    # Teks rata tengah atas-bawah supaya baris satu dan dua baris tetap rapi.
    awal = tpl.index(".hier-table td {")
    assert "vertical-align: middle" in tpl[awal:tpl.index("}", awal)]


def test_nama_panjang_TIDAK_dipotong_saat_dirender(dbx):
    panjang = ("Muhammad Abdurrahman Wahid Syahputra Nasution Harahap "
               "Siregar Pohan")
    d = _data(dbx, pegawai=[("1990", panjang, "Analis Barang Milik Negara",
                             "SEKRETARIAT JENDERAL", "BIRO UMUM",
                             "BAGIAN RUMAH TANGGA", 2)])
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(
        os.path.join(os.path.dirname(__file__), "..", "..", "templates")))
    html = env.get_template("executive_summary.html").render(**d)
    awal = html.index("<h1>Distribusi Per Pengguna")
    blok = html[awal:html.index("<h1>Analisis Lanjutan", awal)]
    assert panjang in blok, "nama terpotong di suatu tempat"
    assert "&hellip;" not in blok and "\u2026" not in blok


# ── 6. Tak ada lembar yang meluber sampai melahirkan halaman kaki ───────

def _lembar_vs_halaman(d):
    """(jumlah lembar HTML, jumlah halaman PDF) — DIRENDER sungguhan."""
    import re
    import tempfile

    import pypdfium2
    import weasyprint

    html = rp._jinja_env().get_template("executive_summary.html").render(
        preview=False, **d)
    # Sampulnya berkelas sendiri (`cover-page`) — menghitung `exec-page` saja
    # membuat selisihnya SELALU satu, dan ujinya lalu menuduh lembar meluber
    # padahal tak satu pun meluber.
    lembar = len(re.findall(r'<div class="(?:exec|cover)-page"', html))
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        weasyprint.HTML(string=html, base_url=os.path.dirname(TPL)).write_pdf(
            f.name)
        return lembar, len(pypdfium2.PdfDocument(f.name))


@pytest.mark.parametrize("banyak", [4, 34, 90])
def test_tak_ada_halaman_yatim(dbx, banyak):
    """Lembar `overflow: hidden` yang meluber TIDAK memotong kakinya.

    Kaki halaman (`margin-top: auto`) terdorong keluar lembar dan mendarat
    sendirian di halaman berikutnya: satu lembar A4 berisi satu baris kaki,
    tanpa satu pun galat, tanpa satu pun tanda di HTML-nya. Jumlah lembar HTML
    yang tak sama dengan jumlah halaman PDF adalah tanda pastinya.

    Diuji pada tiga ukuran daftar: muat satu kolom, pindah dua kolom, dan
    berlanjut ke halaman berikutnya — tiga jalur yang tingginya dihitung
    dengan cara berbeda-beda.
    """
    peg = [(f"20{i:04d}",
            f"Muhammad Abdurrahman Wahid Syahputra Nasution {i}",
            "Analis Pengelolaan Barang Milik Negara Ahli Pertama pada "
            "Bagian Rumah Tangga",
            "Kedeputian Bidang Transformasi Hijau dan Digital",
            f"Direktorat Pengendalian Penyelenggaraan Pemerintahan {i % 4}",
            f"Subdirektorat {i % 6}", 1)
           for i in range(banyak)]
    lembar, halaman = _lembar_vs_halaman(_data(dbx, pegawai=peg))
    assert lembar == halaman, (
        f"{halaman - lembar} halaman yatim: ada lembar yang meluber")


#: Tinggi yang benar-benar tersedia untuk isi satu lembar A4 laporan ini:
#: 1122px dikurangi kop, kaki, dan padding `.exec-body`. Diukur dari render,
#: bukan dihitung dari CSS.
JATAH_ISI_SELEMBAR = 969.0


def _tinggi_isi_tiap_lembar(d):
    """Tinggi `.exec-body` tiap lembar TANPA kekangan tinggi lembarnya.

    Lembar aslinya `min-height: 1122px; overflow: hidden`, sehingga kotaknya
    SELALU melaporkan 1122px entah isinya muat atau meluber — mengukurnya di
    sana selalu menjawab "muat". Di sini kekangan itu dilepas dulu supaya
    tinggi yang terukur adalah tinggi yang sungguh dibutuhkan isinya.
    """
    import weasyprint

    html = rp._jinja_env().get_template("executive_summary.html").render(
        preview=False, **d)
    bebas = (html.replace("width: 794px; min-height: 1122px;", "width: 794px;")
                 .replace("background: #fff; overflow: hidden;",
                          "background: #fff;")
                 .replace("size: A4 portrait;", "size: 794px 9000px;"))
    assert bebas != html, "penanda CSS-nya berubah — pengukurannya jadi palsu"
    doc = weasyprint.HTML(string=bebas, base_url=os.path.dirname(TPL)).render()
    tinggi = []

    def jalan(b):
        e = b.element
        if e is not None and "exec-body" in (e.get("class") or "").split():
            tinggi.append(b.height)
            return
        for c in getattr(b, "children", []):
            jalan(c)

    for p in doc.pages:
        jalan(p._page_box)
    return tinggi


@pytest.mark.parametrize("banyak", [4, 34, 90])
def test_isi_tiap_lembar_MUAT_pada_A4(dbx, banyak):
    """Jatah baris sehalaman tak boleh melebihi yang sungguh muat.

    Ini penjaga sesungguhnya bagi `BARIS_TEKS_SEHALAMAN`: jumlah halaman PDF
    baru bertambah ketika luberannya cukup besar, sementara luberan kecil
    hanya mendorong kaki halaman keluar. Yang diukur di sini tinggi isinya
    sendiri, jadi luberan sekecil apa pun ketahuan.
    """
    peg = [(f"20{i:04d}",
            f"Muhammad Abdurrahman Wahid Syahputra Nasution {i}",
            "Analis Pengelolaan Barang Milik Negara Ahli Pertama pada "
            "Bagian Rumah Tangga",
            "Kedeputian Bidang Transformasi Hijau dan Digital",
            f"Direktorat Pengendalian Penyelenggaraan Pemerintahan {i % 4}",
            f"Subdirektorat {i % 6}", 1)
           for i in range(banyak)]
    tinggi = _tinggi_isi_tiap_lembar(_data(dbx, pegawai=peg))
    assert tinggi, "tak satu lembar pun terukur"
    luber = [t for t in tinggi if t > JATAH_ISI_SELEMBAR]
    assert not luber, f"isi melebihi jatah selembar: {luber}"


def test_lembar_distribusi_TIDAK_menyisakan_separuh_kertas(dbx):
    """Permintaan pemilik: *"pastikan benar-benar tidak ada batas terbuang
    sia-sia di ukuran A4 hingga mencapai footer terlebih dahulu."*

    Jatah yang terlalu kecil tak menimbulkan galat apa pun — ia hanya
    mencetak dua kali lebih banyak kertas. Yang diperiksa lembar distribusi
    yang MASIH ADA sambungannya: lembar terakhir tiap distribusi memang boleh
    setengah kosong, sebab datanya memang habis di situ.
    """
    peg = [(f"20{i:04d}", f"Pegawai Nomor {i}", f"Analis Jenjang {i % 5}",
            "Kedeputian Bidang Transformasi Hijau dan Digital",
            f"Direktorat {i % 4}", f"Subdirektorat {i % 6}", 1)
           for i in range(120)]
    d = _data(dbx, pegawai=peg)
    assert len(d["rencana_peg"]["halaman"]) > 1, "data ujinya kurang panjang"
    tinggi = _tinggi_isi_tiap_lembar(d)
    # Lembar pengguna ada di antara halaman lokasi dan halaman analisis;
    # yang dinilai hanya yang BUKAN lembar terakhir distribusi itu.
    peg_hal = len(d["rencana_peg"]["halaman"])
    sambungan = tinggi[-(peg_hal + 1):-2]
    assert len(sambungan) == peg_hal - 1, (
        f"irisan lembar pengguna meleset: {len(sambungan)} dari {peg_hal - 1}")
    for t in sambungan:
        assert t > JATAH_ISI_SELEMBAR * 0.6, (
            f"lembar sambungan cuma terisi {t:.0f}px dari "
            f"{JATAH_ISI_SELEMBAR:.0f}px — kertas terbuang")
