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

def test_terbagi_menjadi_EMPAT_jenjang(dbx):
    d = _data(dbx)
    assert d["kat_jenjang_label"] == ["Golongan", "Bidang", "Kelompok",
                                      "Sub Kelompok"]
    assert sorted({b["depth"] for b in d["cat_hier"]}) == [0, 1, 2, 3]
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
    awal = tpl.index("{% if cat_hier|length > 0 %}")
    halaman = tpl[awal:tpl.index("{% if loc_chart|length > 0 %}")]
    # Batang lama (`dist-mini-bar`) tak dipakai lagi; yang baru bersyarat.
    assert "dist-mini-bar" not in halaman, "masih memakai batang daftar rata"
    assert "{% if c.bar_pct is defined %}" in halaman
    assert 'class="hier-bar-cell"' in halaman


def _render_halaman_kategori(d):
    """HTML halaman kategori saja — dirender, bukan dibaca dari sumber."""
    import os
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(
        os.path.join(os.path.dirname(__file__), "..", "..", "templates")))
    html = env.get_template("executive_summary.html").render(**d)
    awal = html.index("Kodefikasi BMN Berjenjang")
    return html[awal:html.index("</table>", awal)]


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
    assert 'class="d{{ c.depth }}"' in _teks_tpl()


def test_keempat_jenjang_punya_warna_yang_ditetapkan():
    tpl = _teks_tpl()
    for d in range(4):
        assert f".hier-table tr.d{d} td {{" in tpl, d
        assert f".hier-table tr.d{d} td:first-child {{ border-left" in tpl, d


def test_warna_barisnya_SAMAR_bukan_blok_pekat():
    # "warna row yang masih masuk dan samar": latar tiap jenjang harus tetap
    # terang — teks 7px di atas blok pekat tak terbaca pada cetakan.
    import re
    tpl = _teks_tpl()
    for d in range(4):
        baris = re.search(rf"\.hier-table tr\.d{d} td \{{ background: (#[0-9a-fA-F]{{6}})",
                          tpl)
        assert baris, d
        r, g, b = (int(baris.group(1)[i:i + 2], 16) for i in (1, 3, 5))
        terang = (r + g + b) / 3
        assert terang > 220, f"d{d} terlalu pekat: {baris.group(1)} ({terang})"


def test_legenda_menyebut_keempat_jenjang():
    # Tanpa legenda, warna baris hanya terbaca sebagai hiasan.
    tpl = _teks_tpl()
    awal = tpl.index('<div class="hier-legend">')
    legenda = tpl[awal:tpl.index("</div>", awal)]
    for nama in ("Golongan", "Bidang", "Kelompok", "Sub Kelompok"):
        assert nama in legenda, nama


# ── 3. Jatah baris per halaman tak boleh bergeser sendiri ───────────────

def test_jatah_baris_per_halaman_SAMA_di_python_dan_templat():
    # Kalau berbeda, "Hal 2 dari 3" pada kop berbohong: Python menghitung
    # halaman dengan satu angka sementara templat memotongnya dengan angka
    # lain. Tak ada galat, hanya nomor yang keliru.
    import re
    m = re.search(r"\{% set hier_per_page = (\d+) %\}", _teks_tpl())
    assert m, "jatah baris templat tak ditemukan"
    assert int(m.group(1)) == rp.KAT_HIER_PER_HALAMAN


def test_halaman_kategori_SATU_kolom(dbx):
    # Pohon yang dipecah dua kolom menaruh anak di kolom kanan sementara
    # induknya di kiri, dan hubungan yang justru menjadi alasan pohonnya
    # dibuat hilang di situ.
    tpl = _teks_tpl()
    awal = tpl.index("{% if cat_hier|length > 0 %}")
    halaman = tpl[awal:tpl.index("{% if loc_chart|length > 0 %}")]
    assert "use_two_cols" not in halaman
    assert "grid-template-columns" not in halaman
