"""Laporan Inventarisasi GABUNGAN satker — bentuk & isinya.

Permintaan pemilik: *"laporan hasil inventarisasi BMN yang gabungan dari
kegiatan-kegiatan masih tidak menggunakan font yang cocok, tata letak antar
kegiatan masih tidak jelas dan berantakan tidak terkategori dengan baik, dan
tidak ada time line ... yang rapi terkategori dengan baik walaupun datanya
tercampur agar singkat padat dan terorganisir ... tidak perlu detail sampai ke
barang karena itu tugasnya nanti di dalam masing-masing kegiatan."*

Empat hal dijaga di sini:

1. **Linimasa ada, dan jujur.** Aset TIDAK menyimpan kapan ia diinventarisasi;
   `updated_at` ter-cap pada setiap penyuntingan. Linimasa karenanya diturunkan
   dari PERIODE KEGIATAN, dan laporannya wajib mengatakan itu.
2. **Tiap kegiatan membawa capaiannya sendiri**, bukan terkubur sebagai satu
   batang di antara grafik lain.
3. **Tak ada rincian per barang.** Itu tugas laporan per kegiatan.
4. **Satu keluarga huruf.**
"""
import asyncio
import os
import re

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.reports as rp

TPL = os.path.join(os.path.dirname(os.path.abspath(rp.__file__)),
                   "..", "templates", "laporan_satker_v2.html")


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _teks_template():
    with open(TPL, encoding="utf-8") as f:
        return f.read()


@pytest.fixture()
def dbr(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rp, "db", fake, raising=False)
    return fake


async def _seed(fake, kegiatan, aset):
    for k in kegiatan:
        await fake.inventory_activities.insert_one(dict(k))
    for a in aset:
        await fake.assets.insert_one(dict(a))


def _keg(i, bulan, n_id="k"):
    return {"id": f"{n_id}{i}", "kode_satker": "401234",
            "nama_kegiatan": f"Kegiatan {i}", "nomor_surat": f"S-{i}",
            "tanggal_mulai": f"2025-{bulan:02d}-01",
            "tanggal_selesai": f"2025-{bulan:02d}-28",
            "nama_satker": "Satker Uji", "created_at": f"2025-{bulan:02d}-01"}


def _aset(kid, n, ditemukan=0, tahun="2023"):
    out = []
    for i in range(n):
        out.append({
            "id": f"{kid}-a{i}", "activity_id": kid,
            "asset_name": f"Barang {i}", "asset_code": "3050104001",
            "NUP": str(i), "purchase_price": 1000,
            "purchase_date": f"{tahun}-01-01",
            "inventory_status": "Ditemukan" if i < ditemukan else "Belum Diinventarisasi",
            "stiker_status": "Terpasang" if i < ditemukan else "Belum Terpasang",
        })
    return out


# ── 1. LINIMASA ─────────────────────────────────────────────────────────

def test_linimasa_dua_belas_bulan_dan_kumulatif(dbr):
    """Kegiatan Mei (10 aset) lalu Juli (5 aset): Mei..Jun = 10, Jul..Des = 15.
    Kumulatif, sebab yang ditanyakan adalah PROGRES, bukan tambahan bulanan."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5), _keg(2, 7)],
                    _aset("k1", 10, ditemukan=4) + _aset("k2", 5, ditemukan=2))
        d = await rp._build_satker_report_v2("k1")
        lm = d["linimasa"]
        assert len(lm) == 12
        assert [b["bulan"] for b in lm][:3] == ["JAN", "FEB", "MAR"]
        per_bulan = {b["bulan"]: b["tercatat"] for b in lm}
        assert per_bulan["APR"] == 0
        assert per_bulan["MEI"] == 10 and per_bulan["JUN"] == 10
        assert per_bulan["JUL"] == 15 and per_bulan["DES"] == 15
        temu = {b["bulan"]: b["ditemukan"] for b in lm}
        assert temu["MEI"] == 4 and temu["JUL"] == 6
    _jalan(jalan())


def test_linimasa_menandai_bulan_kegiatan_dimulai(dbr):
    """Tanpa penanda ini, batang bulan Juni (yang hanya membawa angka Mei)
    terbaca seolah ada kegiatan baru di Juni."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5)], _aset("k1", 3))
        lm = (await rp._build_satker_report_v2("k1"))["linimasa"]
        mulai = [b["bulan"] for b in lm if b["mulai"]]
        assert mulai == ["MEI"], mulai
    _jalan(jalan())


def test_tinggi_batang_dihitung_di_server_bukan_di_template(dbr):
    """Aritmetika di dalam Jinja mudah membagi nol tanpa terlihat — pada
    satker tanpa aset seluruh laporan akan gagal render."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5)], [])
        d = await rp._build_satker_report_v2("k1")
        assert d["linimasa_ada"] is False
        assert all(b["h_tercatat"] == 0 for b in d["linimasa"])
    _jalan(jalan())


def test_linimasa_menyatakan_sumbernya_periode_kegiatan():
    """Aset tak menyimpan kapan ia diinventarisasi. Linimasa yang diam soal
    itu mengaku punya ketelitian per-barang yang tak pernah ia miliki."""
    t = re.sub(r"\s+", " ", _teks_template())
    assert "kumulatif" in t.lower()
    assert "bukan per tanggal pemeriksaan tiap barang" in t


# ── 2. PER KEGIATAN ─────────────────────────────────────────────────────

def test_tiap_kegiatan_membawa_capaiannya_sendiri(dbr):
    async def jalan():
        await _seed(dbr, [_keg(1, 5), _keg(2, 7)],
                    _aset("k1", 10, ditemukan=4) + _aset("k2", 5, ditemukan=5))
        kl = {k["nama_kegiatan"]: k
              for k in (await rp._build_satker_report_v2("k1"))["kegiatan_list"]}
        assert kl["Kegiatan 1"]["count"] == 10
        assert kl["Kegiatan 1"]["ditemukan"] == 4
        assert kl["Kegiatan 1"]["pct"] == 40.0
        assert kl["Kegiatan 1"]["belum"] == 6
        assert kl["Kegiatan 2"]["pct"] == 100.0
    _jalan(jalan())


def test_kegiatan_dirender_sebagai_kartu_bukan_baris_tabel():
    """Baris tabel datar adalah bentuk yang dikeluhkan: angka kegiatan ada,
    tetapi capaiannya tak terbaca di tempat kegiatannya disebut."""
    t = _teks_template()
    assert 'class="keg-grid"' in t
    assert "kegiatan-tbl" not in t, "tabel kegiatan lama masih ada"


def test_grafik_per_kegiatan_lama_dibuang():
    """Bagian 2 sudah memberi tiap kegiatan kartunya sendiri. Menyisakan
    grafik lamanya berarti angka yang sama muncul dua kali dalam bentuk
    berbeda — persis 'berantakan dan tidak terkategori'."""
    assert "chart_per_kegiatan" not in _teks_template()


# ── 3. TIDAK RINCI SAMPAI BARANG ────────────────────────────────────────

def test_tak_ada_tabel_per_barang():
    """Permintaan pemilik, harfiah. Pada satker ribuan NUP, tabel per barang
    menenggelamkan ringkasannya di antara puluhan halaman — dan mengulang isi
    yang sudah ada di LHI/DBHI per kegiatan."""
    t = _teks_template()
    for penanda in ("{% for a in assets %}", "{% for d in dok_rows %}"):
        assert penanda not in t, penanda


def test_bagian_laporan_ringkas_dan_terkategori():
    """Enam bagian bernama, masing-masing menjawab satu pertanyaan."""
    t = _teks_template()
    judul = re.findall(r'class="section-title">([^<]+)<', t)
    assert judul == ["Ringkasan Eksekutif", "Capaian per Kegiatan",
                     "Kategori Hasil di Lapangan", "Analisis Data",
                     "Personil Terlibat", "Simpulan"], judul


# ── 4. KATEGORI LAPANGAN & TAHUN PEROLEHAN ──────────────────────────────

def test_kategori_lapangan_dari_data_sistem_bukan_daftar_karangan(dbr):
    """Kategori yang tak punya sumber data akan selalu nol dan hanya membuat
    pembaca mengira ada yang belum terisi."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5)], _aset("k1", 10, ditemukan=4))
        kat = {k["label"]: k["n"]
               for k in (await rp._build_satker_report_v2("k1"))["kategori_lapangan"]}
        assert kat["BMN Ditemukan"] == 4
        assert kat["Ditemukan, Stiker Terpasang"] == 4
        assert kat["Ditemukan, Belum Berstiker"] == 0
    _jalan(jalan())


def test_per_tahun_perolehan_urut_kronologis(dbr):
    """Laporan dibaca kiri-ke-kanan sebagai perjalanan waktu, bukan sebagai
    peringkat — mengurutkannya menurut jumlah membuat sumbu waktunya kacau.

    Tahun yang LEBIH LAMA sengaja diberi aset LEBIH SEDIKIT. Versi pertama
    uji ini memberi tahun lama lebih banyak, sehingga urutan kronologis dan
    urutan-menurut-jumlah kebetulan sama — dan mutasi yang mengurutkan
    menurut jumlah lolos tanpa satu pun uji berbunyi.
    """
    async def jalan():
        await _seed(dbr, [_keg(1, 5)],
                    _aset("k1", 3, ditemukan=2, tahun="2023")
                    + [dict(a, id=a["id"] + "b") for a in
                       _aset("k1", 9, ditemukan=1, tahun="2024")])
        pt = (await rp._build_satker_report_v2("k1"))["per_tahun"]
        assert [t["tahun"] for t in pt] == ["2023", "2024"], (
            "sumbu waktu tak boleh diurutkan menurut jumlah")
        assert pt[0]["tercatat"] == 3 and pt[0]["ditemukan"] == 2
        assert pt[0]["sisa"] == 1
        assert pt[1]["tercatat"] == 9
    _jalan(jalan())


def test_aset_tanpa_tanggal_perolehan_tak_mengarang_tahun(dbr):
    async def jalan():
        aset = _aset("k1", 4, ditemukan=2)
        for a in aset:
            a["purchase_date"] = ""
        await _seed(dbr, [_keg(1, 5)], aset)
        assert (await rp._build_satker_report_v2("k1"))["per_tahun"] == []
    _jalan(jalan())


# ── 5. HURUF ────────────────────────────────────────────────────────────

def test_satu_keluarga_huruf_untuk_badan_dokumen():
    """Versi sebelumnya memakai Georgia untuk badan, sans-serif untuk label
    kecil, dan Courier untuk kode — tiga rasa huruf dalam satu halaman."""
    t = _teks_template()
    # DUA ejaan diperiksa. Versi pertama uji ini hanya mencari yang BERSPASI
    # dan lulus, padahal masih ada dua deklarasi inline tanpa spasi yang
    # menimpa tumpukan huruf badan — cacat yang justru sedang dijaga.
    tanpa_spasi = re.sub(r"font-family:\s+", "font-family:", t)
    lolos = [b for b in tanpa_spasi.splitlines()
             if "font-family:sans-serif" in b and not b.lstrip().startswith(("*", "/*"))
             and "'Inter'" not in b]
    assert not lolos, (
        "deklarasi generik membuang tumpukan huruf pilihan: %r" % lolos[:2])
    assert t.count("'Georgia', serif") <= 1, (
        "serif hanya boleh tersisa di sampul")
    assert "font-variant-numeric: tabular-nums" in t, (
        "angka bertumpuk perlu digit selebar sama agar berbaris")
