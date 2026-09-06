"""Distribusi Kategori Aset pada Laporan Eksekutif — berjenjang, tanpa batang.

Permintaan pemilik: *"pada laporan eksekutif di distribusi aset, buat agar
terbagi menjadi golongan, bidang, kelompok, sub kelompok. dimana setiap
pembagian buat tanpa bar disetiap rownya dan warna row yang masih masuk dan
samar dan cocok dengan tema dan terlihat rapi."*

Daftar sebelumnya RATA dan dikelompokkan menurut field `category` — teks bebas
dari master kategori. "Kabel" dan "Handy Talky (HT)" berdiri sejajar dengan
"Alat Laboratorium Pendidikan", padahal keduanya duduk di cabang kodefikasi
yang sama sekali berbeda; daftar itu tak dapat menjawab "berapa banyak
Peralatan dan Mesin" tanpa dijumlahkan tangan.

Tiga sifat dijaga di sini:

1. **Pohonnya utuh.** Induk berjumlah persis sama dengan anak-anaknya, dan
   totalnya diambil dari jenjang TERATAS saja — menjumlahkan seluruh baris
   menghitung tiap aset empat kali.
2. **Batang HANYA di jenjang terdalam.** Permintaan pemilik dua langkah:
   *"setiap pembagian buat tanpa bar disetiap rownya"*, lalu *"untuk barchart
   disetiap data sub sub kelompok jangan dihilangkan."* Keduanya sejalan —
   pada baris PENGELOMPOKAN batang membandingkan induk dengan anaknya, dua
   besaran yang salah satunya memuat yang lain; pada baris TERDALAM ia
   membandingkan sesama saudara, dan di sanalah panjangnya berarti.
3. **Jatah baris per halaman tak boleh berbeda** antara Python dan templat;
   kalau berbeda, nomor halaman pada kop berbohong.
"""
import asyncio
import os

import pytest
from mongomock_motor import AsyncMongoMockClient

import kodefikasi_utils as kod
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


#: Dua Golongan, tiga Bidang, cabang yang dalamnya tak seragam.
BARANG = [
    ("3100102002", "Note Book", 12),
    ("3100102006", "Tablet PC", 5),
    ("3100103001", "Printer", 2),
    ("3050104001", "Handy Talky (HT)", 32),
    ("3050203004", "Kabel", 35),
    ("6010101001", "Realitas Virtual", 1),
]
URAIAN = {"3": "Peralatan dan Mesin", "6": "Aset Tetap Lainnya",
          "305": "Alat Kantor dan Rumah Tangga", "310": "Komputer",
          "31001": "Komputer Unit", "30501": "Alat Kantor"}


async def _seed(fake, barang=BARANG, tanpa_kode=0):
    await fake.inventory_activities.insert_one(
        {"id": "k1", "kode_satker": "691778", "nama_satker": "SATKER D",
         "nama_kegiatan": "Inventarisasi 2026", "nomor_surat": "S-1",
         "tanggal_mulai": "2026-01-01", "tanggal_selesai": "2026-06-30",
         "created_at": "2026-01-01"})
    for k, u in URAIAN.items():
        await fake.kodefikasi.insert_one({"kode": k, "uraian": u})
    n = 0
    for kode, uraian, banyak in barang:
        await fake.kodefikasi.insert_one({"kode": kode[:7], "uraian": uraian})
        for _ in range(banyak):
            n += 1
            await fake.assets.insert_one(
                {"id": f"a{n}", "activity_id": "k1", "asset_name": uraian,
                 "asset_code": kode, "NUP": str(n), "purchase_price": 1000,
                 "purchase_date": "2023-01-01", "category": uraian,
                 "inventory_status": "Belum Diinventarisasi"})
    for i in range(tanpa_kode):
        n += 1
        await fake.assets.insert_one(
            {"id": f"z{i}", "activity_id": "k1", "asset_name": "Tanpa kode",
             "asset_code": "", "NUP": str(n), "purchase_price": 500,
             "purchase_date": "2023-01-01",
             "inventory_status": "Belum Diinventarisasi"})


def _data(dbx, **kw):
    _jalan(_seed(dbx, **kw))
    return _jalan(rp._build_executive_summary_data("k1", with_asset_rows=False))


# ── 1. Empat jenjang, pohon yang utuh ───────────────────────────────────

def test_terbagi_sampai_SUB_SUB_KELOMPOK(dbx):
    # Permintaan pemilik: *"ya langsung sampai ke sub-sub kelompoknya."*
    d = _data(dbx)
    assert d["kat_jenjang_label"] == ["Golongan", "Bidang", "Kelompok",
                                      "Sub Kelompok", "Sub-sub Kelompok"]
    assert sorted({b["depth"] for b in d["cat_hier"]}) == [0, 1, 2, 3, 4]
    # Tiap baris menyebut jenjangnya sendiri, bukan hanya kedalaman angka.
    for b in d["cat_hier"]:
        assert b["jenjang"] == kod.LEVEL_LABELS[
            rp.KAT_JENJANG_EKSEKUTIF[b["depth"]]]


def test_baris_teratas_adalah_GOLONGAN_bukan_nama_kategori_bebas(dbx):
    # Sumbernya kode aset, bukan field `category` yang diketik bebas.
    d = _data(dbx)
    puncak = [b["name"] for b in d["cat_hier"] if b["depth"] == 0]
    assert puncak == ["3 — Peralatan dan Mesin", "6 — Aset Tetap Lainnya"]


def test_INDUK_berjumlah_sama_dengan_anak_anaknya(dbx):
    d = _data(dbx)
    baris = d["cat_hier"]
    for i, b in enumerate(baris):
        anak, j = [], i + 1
        while j < len(baris) and baris[j]["depth"] > b["depth"]:
            if baris[j]["depth"] == b["depth"] + 1:
                anak.append(baris[j])
            j += 1
        if anak:
            assert sum(x["count"] for x in anak) == b["count"], b["name"]
            assert sum(x["value"] for x in anak) == b["value"], b["name"]


def test_TOTAL_dari_jenjang_teratas_saja_bukan_seluruh_baris(dbx):
    # Menjumlahkan seluruh baris menghitung tiap aset empat kali, dan angka
    # empat kali lipat pada baris berjudul "Total" adalah kekeliruan yang
    # paling mudah dipercaya.
    d = _data(dbx)
    jumlah_semua = sum(b["count"] for b in d["cat_hier"])
    assert d["cat_hier_total"]["count"] == 87
    assert jumlah_semua > d["cat_hier_total"]["count"], "pohonnya tak bersarang"
    assert d["cat_hier_total"]["count"] == sum(
        b["count"] for b in d["cat_hier"] if b["depth"] == 0)


def test_aset_TANPA_KODE_tetap_terhitung_bukan_hilang(dbx):
    # Aset yang justru paling perlu dibereskan tak boleh lenyap dari
    # distribusinya sendiri.
    d = _data(dbx, tanpa_kode=4)
    assert d["cat_hier_total"]["count"] == 91
    assert any("tanpa kode" in b["name"].lower() for b in d["cat_hier"])


def test_kegiatan_tanpa_aset_tak_menghasilkan_baris_hantu(dbx):
    d = _data(dbx, barang=[])
    assert d["cat_hier"] == []
    assert d["cat_hier_total"] == {"count": 0, "value": 0}


# ── 2. Batang hanya di daun, berwarna samar per jenjang ────────────────

def test_batang_HANYA_pada_jenjang_terdalam(dbx):
    d = _data(dbx)
    daun = len(rp.KAT_JENJANG_EKSEKUTIF) - 1
    for b in d["cat_hier"]:
        if b["depth"] == daun:
            assert "bar_pct" in b, b["name"]
        else:
            assert "bar_pct" not in b, f'{b["name"]} — batang di pengelompokan'


def test_acuan_batang_daun_TERBESAR_bukan_total_keseluruhan(dbx):
    # Dibagi total, seluruh batang menjadi sisa yang tak terbaca begitu satu
    # cabang mendominasi: 35 dari 87 masih terlihat, 35 dari 216 hampir tidak.
    d = _data(dbx)
    daun = [b for b in d["cat_hier"]
            if b["depth"] == len(rp.KAT_JENJANG_EKSEKUTIF) - 1]
    terbesar = max(daun, key=lambda b: b["count"])
    assert terbesar["bar_pct"] == 100, terbesar
    assert all(0 <= b["bar_pct"] <= 100 for b in daun)
    # Sebanding lurus dengan cacahnya — batang yang tak sebanding tak
    # membandingkan apa pun.
    for b in daun:
        assert b["bar_pct"] == round(b["count"] / terbesar["count"] * 100)


def test_templat_menggambar_batang_hanya_bila_barisnya_membawanya():
    tpl = _teks_tpl()
    awal = tpl.index("{% macro sel_dist(")
    makro = tpl[awal:tpl.index("{%- endmacro %}", awal)]
    assert "dist-mini-bar" not in makro, "masih memakai batang daftar rata"
    assert "{% if b.bar_pct is defined %}" in makro
    assert 'class="hier-bar-cell"' in makro


# Judul <h1> ketiga distribusi, berurutan seperti di templat. Dipakai untuk
# mengiris satu blok distribusi dari halaman berikutnya — bukan mencari nama
# jenjang, sebab justru nama itulah yang diuji.
_JUDUL_DIST = ("Distribusi Kategori Aset", "Distribusi Lokasi Aset",
               "Distribusi Per Pengguna", "Analisis Lanjutan")


def _render_dist(d, judul="Distribusi Kategori Aset"):
    """HTML satu blok distribusi — DIRENDER, bukan dibaca dari sumbernya.

    Irisannya dibatasi judul distribusi berikutnya: uji yang mengiris sampai
    akhir berkas ikut menangkap halaman lain, lalu lulus/gagal karena baris
    yang bukan urusannya.
    """
    import os
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(
        os.path.join(os.path.dirname(__file__), "..", "..", "templates")))
    html = env.get_template("executive_summary.html").render(**d)
    awal = html.index("<h1>" + judul)
    # Blok distribusi bisa kosong (tak ada datanya) sehingga judulnya tak
    # pernah tergambar — maka batasnya judul BERIKUTNYA yang benar-benar ada.
    sisa = _JUDUL_DIST[_JUDUL_DIST.index(judul) + 1:]
    for j in sisa:
        akhir = html.find("<h1>" + j, awal)
        if akhir >= 0:
            return html[awal:akhir]
    return html[awal:]


def _render_halaman_kategori(d):
    return _render_dist(d, "Distribusi Kategori Aset")


def test_tiap_baris_berkolom_SAMA_BANYAK(dbx):
    """Sel batang tetap ada di baris pengelompokan — kosong, bukan hilang.

    Sel yang hilang menggeser NUP dan Nilai pada baris itu saja: angka
    Golongan mendarat di kolom batang sementara nilainya di kolom NUP. Tabel
    tetap tergambar, hanya tiga barisnya berbohong.

    Ditemukan uji mutasi: membungkus selnya dengan `{% if %}` lolos dari
    seluruh penjaga struktural, sebab sumbernya tetap MEMUAT kelas itu.
    """
    import re
    potongan = _render_halaman_kategori(_data(dbx))
    # Tag `<tr>`-nya ikut ditangkap: kelas baris ada DI SANA, dan baris total
    # (ber-`colspan`) memang berkolom lebih sedikit dengan sengaja.
    baris = re.findall(r"<tr[^>]*>.*?</tr>", potongan, re.S)
    isi = [b for b in baris if "<td" in b and "summary-row" not in b]
    assert len(isi) > 4, "data ujinya terlalu kecil"
    jumlah = {b.count("<td") for b in isi}
    assert jumlah == {4}, f"kolom tak seragam: {sorted(jumlah)}"


def test_hanya_baris_TERDALAM_yang_benar_benar_menggambar_batang(dbx):
    import re
    potongan = _render_halaman_kategori(_data(dbx))
    baris = re.findall(r'<tr class="d(\d)">(.*?)</tr>', potongan, re.S)
    assert baris, "tak ada baris berjenjang yang dirender"
    daun = str(len(rp.KAT_JENJANG_EKSEKUTIF) - 1)
    for depth, isi in baris:
        ada = 'class="hier-bar"' in isi
        assert ada == (depth == daun), f"depth {depth}: batang={ada}"


def test_tiap_baris_membawa_kelas_jenjangnya():
    # Kedalaman DIJEPIT: jenjang denah bisa lebih dalam daripada warna yang
    # ditetapkan, dan kelas `d9` yang tak punya aturan membuat barisnya
    # kehilangan warna sama sekali — tanpa satu pun tanda.
    assert 'class="d{{ [b.depth, 5]|min }}' in _teks_tpl()


def test_tiap_kedalaman_yang_MUNGKIN_punya_warna():
    tpl = _teks_tpl()
    for d in range(6):
        assert f".hier-table tr.d{d} td {{" in tpl, d
        assert f".hier-table tr.d{d} td:first-child {{ border-left" in tpl, d


def test_warna_barisnya_SAMAR_bukan_blok_pekat():
    # "warna row yang masih masuk dan samar": latar tiap jenjang harus tetap
    # terang — teks 7px di atas blok pekat tak terbaca pada cetakan.
    import re
    tpl = _teks_tpl()
    for d in range(6):
        baris = re.search(rf"\.hier-table tr\.d{d} td \{{ background: (#[0-9a-fA-F]{{6}})",
                          tpl)
        assert baris, d
        r, g, b = (int(baris.group(1)[i:i + 2], 16) for i in (1, 3, 5))
        terang = (r + g + b) / 3
        assert terang > 220, f"d{d} terlalu pekat: {baris.group(1)} ({terang})"


def test_legenda_dibangun_dari_daftar_jenjang_yang_SAMA(dbx):
    # Legenda yang namanya ditulis tangan adalah legenda yang suatu saat
    # menerangkan jenjang yang sudah tak dipakai. Ia dirakit dari daftar yang
    # sama dengan yang membentuk barisnya — dan kini SATU makro merakit
    # legenda ketiga halaman, jadi ketiganya mustahil berbeda cara.
    tpl = _teks_tpl()
    assert "{% for lb in jenjang_label %}" in tpl
    assert tpl.count('<div class="hier-legend') == 1, "legenda tak lagi satu"
    potongan = _render_halaman_kategori(_data(dbx))
    for nama in ("Golongan", "Bidang", "Kelompok", "Sub Kelompok",
                 "Sub-sub Kelompok"):
        assert nama in potongan, nama


# ── 3. Jatah baris per halaman tak boleh bergeser sendiri ───────────────

def test_templat_TIDAK_memutuskan_paginasinya_sendiri():
    """Dulu templat memotong daftarnya dengan angkanya sendiri sementara Python
    menghitung jumlah halaman dengan angka lain. Kalau keduanya berbeda,
    "Hal 2 dari 3" pada kop berbohong — tanpa galat, hanya nomor yang keliru.

    Kini irisan tiap halaman DATANG dari Python (`rencana.halaman`), dan
    templat hanya membacanya."""
    tpl = _teks_tpl()
    assert "hier_per_page" not in tpl, "templat masih memotong sendiri"
    assert "{% for hal in rencana.halaman %}" in tpl
    assert "{% set awal = hal.awal %}" in tpl


def test_kolom_kedua_yang_MULAI_di_tengah_pohon_menyebut_induknya(dbx):
    """Dua kolom memecah pohonnya: sebuah baris bisa berdiri di kolom kanan
    sementara induknya ada di kolom kiri. Kepala kolomnya karenanya menyebut
    jalur induk baris pertamanya — tanpa itu hubungan yang justru menjadi
    alasan pohonnya dibuat hilang di situ."""
    tpl = _teks_tpl()
    assert "jalur_induk(baris, pisah)" in tpl
    assert 'class="lanjutan-jalur"' in tpl
    # Fungsinya dititipkan dari Python, bukan dihitung ulang di Jinja.
    d = _data(dbx)
    assert callable(d["jalur_induk"])


# ── 4. Distribusi LOKASI: denah berjenjang, teks bebas sebagai daun ─────
#
# Permintaan pemilik: *"lakukan hal yang sama disemua distribusi lokasi sesuai
# hierarki di peta denah juga dari awal hingga akhir, dan terakhir data lokasi
# sekarang."*
#
# Denah menjawab "di gedung mana"; field teks `location` menjawab "tertulis di
# mana" — dan keduanya kerap tak sama. Selisihnya hanya terbaca bila keduanya
# berada di satu pohon.

async def _seed_denah(fake):
    """Menara A › Lantai 1 › R. Rapat, plus aset yang belum ditempatkan."""
    await fake.spasial_node.insert_many([
        {"id": "g1", "nama": "Menara A", "tipe": "GEDUNG", "ancestors": []},
        {"id": "l1", "nama": "Lantai 1", "tipe": "LANTAI", "ancestors": ["g1"]},
        {"id": "r1", "nama": "R. Rapat", "tipe": "RUANGAN",
         "ancestors": ["g1", "l1"]},
    ])
    ditempat = [("r1", "Lt.1 R.Rapat"), ("r1", "Lantai 1 Ruang Rapat"),
                ("g1", "Lobi")]
    n = 100
    for node, teks in ditempat:
        n += 1
        await fake.assets.insert_one(
            {"id": f"d{n}", "activity_id": "k1", "asset_name": "Meja",
             "asset_code": "3050104001", "NUP": str(n), "purchase_price": 1000,
             "purchase_date": "2023-01-01", "location": teks,
             "lokasi_spasial": {"node_id": node},
             "inventory_status": "Belum Diinventarisasi"})


def _data_denah(dbx):
    _jalan(_seed(dbx, barang=[("3050104001", "Handy Talky (HT)", 2)]))
    _jalan(_seed_denah(dbx))
    return _jalan(rp._build_executive_summary_data("k1", with_asset_rows=False))


def test_lokasi_berjenjang_mengikuti_denah_lalu_teksnya(dbx):
    d = _data_denah(dbx)
    assert d["loc_jenjang_label"][-1] == "Lokasi tercatat"
    assert "Gedung" in d["loc_jenjang_label"][0]
    nama = [b["name"] for b in d["loc_hier"]]
    assert "Menara A" in nama and "Lantai 1" in nama and "R. Rapat" in nama
    # Dua tulisan berbeda untuk satu ruangan denah — persis selisih yang
    # hanya terbaca bila keduanya berada di satu pohon.
    assert "Lt.1 R.Rapat" in nama and "Lantai 1 Ruang Rapat" in nama


def test_lokasi_INDUK_berjumlah_sama_dengan_anak_anaknya(dbx):
    d = _data_denah(dbx)
    baris = d["loc_hier"]
    for i, b in enumerate(baris):
        anak, j = [], i + 1
        while j < len(baris) and baris[j]["depth"] > b["depth"]:
            if baris[j]["depth"] == b["depth"] + 1:
                anak.append(baris[j])
            j += 1
        if anak:
            assert sum(x["count"] for x in anak) == b["count"], b["name"]


def test_lokasi_TOTAL_dari_jenjang_teratas_saja(dbx):
    d = _data_denah(dbx)
    assert d["loc_hier_total"]["count"] == d["asset_count"]
    assert d["loc_hier_total"]["count"] == sum(
        b["count"] for b in d["loc_hier"] if b["depth"] == 0)


def test_batang_lokasi_hanya_pada_jenjang_TERDALAM(dbx):
    d = _data_denah(dbx)
    daun = max(b["depth"] for b in d["loc_hier"])
    for b in d["loc_hier"]:
        assert ("bar_pct" in b) == (b["depth"] == daun), b["name"]


def test_rantai_BELUM_DITEMPATKAN_dirapatkan_bukan_berulang(dbx):
    """Aset tanpa denah melahirkan satu baris "(belum ditempatkan)" pada SETIAP
    jenjang — baris beruntun yang cacahnya persis sama dan tak menyatakan satu
    pun hal baru. Yang menyatakan sesuatu hanya yang pertama."""
    d = _data_denah(dbx)
    from laporan_jenjang import TANPA_DENAH
    kosong = [b for b in d["loc_hier"] if b["name"] == TANPA_DENAH]
    # Satu di jenjang teratas (aset yang tak berdenah sama sekali) dan satu di
    # bawah Menara A (aset berdenah Gedung tetapi tanpa Lantai) — yang kedua
    # PUNYA saudara, jadi ia memang menyatakan sesuatu.
    assert len(kosong) == 2, [b["name"] + f"@{b['depth']}" for b in d["loc_hier"]]
    assert sorted(b["depth"] for b in kosong) == [0, 1]


def test_kelompok_TANPA_selalu_terakhir_di_antara_saudaranya(dbx):
    """Sifat yang disandari perapatan rantai: pencarian saudaranya hanya
    menengok ke BELAKANG, dan itu cukup justru karena kelompok "(tanpa …)"
    selalu diurutkan paling akhir. Kalau urutannya berubah, baris yang
    sebenarnya punya saudara akan ikut terbuang."""
    from laporan_jenjang import TANPA_DENAH
    d = _data_denah(dbx)
    baris = d["loc_hier"]
    for i, b in enumerate(baris):
        if b["name"] != TANPA_DENAH:
            continue
        # Tak boleh ada saudara SESUDAHnya di bawah induk yang sama.
        for j in range(i + 1, len(baris)):
            if baris[j]["depth"] < b["depth"]:
                break
            assert baris[j]["depth"] != b["depth"], (
                f'{b["name"]} punya saudara sesudahnya: {baris[j]["name"]}')


def test_kedalaman_lokasi_tetap_RAPAT_setelah_dirapatkan(dbx):
    # Kedalaman yang melompat membuat sebuah baris menjorok tiga tingkat di
    # bawah induk yang cuma satu tingkat di atasnya.
    d = _data_denah(dbx)
    sebelum = 0
    for b in d["loc_hier"]:
        assert b["depth"] <= sebelum + 1, b["name"]
        sebelum = b["depth"]


def test_tanpa_denah_sama_sekali_daftarnya_RATA(dbx):
    # Belum ada satu pun aset yang ditempatkan: yang tersisa hanya jenjang
    # teksnya, dan panelnya jatuh menjadi daftar rata seperti sebelumnya.
    d = _data(dbx)
    assert d["loc_jenjang_label"] == ["Lokasi tercatat"]
    assert {b["depth"] for b in d["loc_hier"]} == {0}


def test_KETIGA_halaman_memakai_makro_yang_SAMA():
    """Dua tabel yang menjawab pertanyaan sejenis tak boleh berbeda cara
    dibaca. Tiga salinan tata letak sudah pernah berbeda isi; satu makro
    membuatnya mustahil."""
    tpl = _teks_tpl()
    assert tpl.count("{% macro halaman_dist(") == 1
    for pemanggil in ("halaman_dist(cat_hier", "halaman_dist(loc_hier",
                      "halaman_dist(pengguna_hier"):
        assert pemanggil in tpl, pemanggil
    assert "dist-mini-bar" not in tpl[tpl.index("{% macro halaman_dist("):]


# ── 4. Halaman kategori harus MUAT pada A4 ──────────────────────────────

#: Tinggi yang benar-benar tersedia untuk isi satu lembar A4 laporan ini —
#: 1122px dikurangi kop, kaki, dan padding `.exec-body`.
JATAH_ISI_SELEMBAR = 969.0

#: Kodefikasi padat: tiga Golongan, banyak cabang, uraian panjang. Halaman
#: kategori adalah lembar TERPADAT laporan ini — jenjangnya lima dan barisnya
#: sebanyak jenis barangnya — jadi ia yang menentukan batas jatah sehalaman.
BARANG_PADAT = [
    (f"{gol}{bid:02d}{kel:02d}{sub:02d}{ss:03d}",
     f"Alat {'Laboratorium Pendidikan Kedokteran' if ss % 3 else 'Kantor'} "
     f"Lainnya {gol}{bid}{kel}{sub}{ss}", 1)
    for gol in (3, 5, 6) for bid in (1, 5) for kel in (1, 2)
    for sub in (1, 2, 3) for ss in (1, 2, 3)
]


def _tinggi_isi_tiap_lembar(d):
    """Tinggi `.exec-body` tiap lembar TANPA kekangan tinggi lembarnya.

    Lembar aslinya `min-height: 1122px; overflow: hidden`, sehingga kotaknya
    SELALU melaporkan 1122px entah isinya muat atau meluber. Kekangan itu
    dilepas dulu supaya yang terukur adalah tinggi yang sungguh dibutuhkan.
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


@pytest.mark.parametrize("barang", [BARANG, BARANG_PADAT])
def test_isi_lembar_kategori_MUAT_pada_A4(dbx, barang):
    """Jatah baris sehalaman tak boleh melebihi yang sungguh muat.

    Luberan kecil TIDAK menambah halaman PDF — ia hanya mendorong kaki
    halaman keluar lembar, dan `overflow: hidden` memotongnya tanpa suara.
    Yang diukur di sini tinggi isinya sendiri, jadi luberan sekecil apa pun
    ketahuan.
    """
    d = _data(dbx, barang=barang)
    luber = [t for t in _tinggi_isi_tiap_lembar(d) if t > JATAH_ISI_SELEMBAR]
    assert not luber, f"isi melebihi jatah selembar: {luber}"


def test_lembar_kategori_TIDAK_menyisakan_separuh_kertas(dbx):
    """Permintaan pemilik: *"pastikan benar-benar tidak ada batas terbuang
    sia-sia di ukuran A4 hingga mencapai footer terlebih dahulu."*

    Jatah yang terlalu kecil tak menimbulkan galat apa pun — ia hanya
    mencetak dua kali lebih banyak kertas, dan itu persis keluhan yang
    hendak dijawab.
    """
    d = _data(dbx, barang=BARANG_PADAT)
    tinggi = _tinggi_isi_tiap_lembar(d)
    # Lembar ke-2 (indeks 1) selalu halaman kategori pertama: indeks 0 adalah
    # ringkasan eksekutif. Sampul tak punya `.exec-body`.
    assert tinggi[1] > JATAH_ISI_SELEMBAR * 0.7, (
        f"lembar kategori cuma terisi {tinggi[1]:.0f}px dari "
        f"{JATAH_ISI_SELEMBAR:.0f}px — kertas terbuang")
