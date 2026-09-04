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


def _aset(kid, n, ditemukan=0, tahun="2023", perolehan=None):
    """`perolehan` menimpa tanggal perolehan penuh (YYYY-MM-DD) bila diisi.

    Nilai `stiker_status` di sini WAJIB sama dengan yang benar-benar ditulis
    aplikasi — "Sudah Terpasang". Versi pertama fixture ini memakai
    "Terpasang", nilai yang tak pernah ada di basis data, sehingga ia sama
    kelirunya dengan kode yang diujinya dan uji stiker lolos tanpa pernah
    menyentuh keadaan sungguhan.
    """
    out = []
    for i in range(n):
        out.append({
            "id": f"{kid}-a{i}", "activity_id": kid,
            "asset_name": f"Barang {i}", "asset_code": "3050104001",
            "NUP": str(i), "purchase_price": 1000,
            "purchase_date": perolehan or f"{tahun}-01-01",
            "inventory_status": "Ditemukan" if i < ditemukan else "Belum Diinventarisasi",
            "stiker_status": "Sudah Terpasang" if i < ditemukan else "Belum Terpasang",
        })
    return out


# ── 1. LINIMASA ─────────────────────────────────────────────────────────

def test_linimasa_per_bulan_FLUKTUATIF_bukan_kumulatif(dbr):
    """Permintaan pemilik: linimasa per bulan harus FLUKTUATIF.

    Versi kumulatif menjawab "sudah sampai mana" — tangga yang hanya naik dan
    tak pernah turun, sehingga "bulan apa yang ramai" tak pernah terjawab.
    Kegiatan Mei (4 diperiksa) dan Juli (2 diperiksa): Juni harus KEMBALI NOL,
    bukan menyalin angka Mei."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5), _keg(2, 7)],
                    _aset("k1", 10, ditemukan=4) + _aset("k2", 5, ditemukan=2))
        d = await rp._build_satker_report_v2("k1")
        lm = d["linimasa"]
        assert len(lm) == 12
        assert [b["bulan"] for b in lm][:3] == ["JAN", "FEB", "MAR"]
        per_bulan = {b["bulan"]: b["tercatat"] for b in lm}
        assert per_bulan["MEI"] == 4, per_bulan
        assert per_bulan["JUN"] == 0, "kumulatif kembali: Juni menyalin Mei"
        assert per_bulan["JUL"] == 2, per_bulan
        assert per_bulan["DES"] == 0, "kumulatif kembali: Desember menyalin Juli"
        temu = {b["bulan"]: b["ditemukan"] for b in lm}
        assert temu["MEI"] == 4 and temu["JUL"] == 2
    _jalan(jalan())


def test_belum_diinventarisasi_ditempatkan_di_bulan_PEROLEHAN(dbr):
    """*"menyesuaikan tanggal perolehan untuk BMN yang belum diinventarisasi
    akan tetapi tercatat"* — satu-satunya tanggal yang diketahui tentang aset
    yang belum disentuh pemeriksaan adalah tanggal perolehannya. Memakai bulan
    kegiatan untuknya berarti mengaku-aku peristiwa yang belum terjadi."""
    async def jalan():
        # Kegiatan Mei; empat aset BELUM diperiksa, diperoleh Maret 2025.
        await _seed(dbr, [_keg(1, 5)],
                    _aset("k1", 4, ditemukan=0, perolehan="2025-03-09"))
        d = await rp._build_satker_report_v2("k1")
        per_bulan = {b["bulan"]: b for b in d["linimasa"]}
        assert per_bulan["MAR"]["perolehan"] == 4, "tak jatuh ke bulan perolehan"
        assert per_bulan["MAR"]["ditemukan"] == 0
        assert per_bulan["MEI"]["tercatat"] == 0, "masih ditumpuk di bulan kegiatan"
    _jalan(jalan())


def test_peristiwa_di_luar_tahun_DINYATAKAN_bukan_disembunyikan(dbr):
    """BMN perolehan tahun lampau yang belum diperiksa tak punya peristiwa apa
    pun pada tahun berjalan, jadi ia tak berbatang. Grafik yang diam soal itu
    akan terbaca sebagai "sisanya nol" — jumlahnya harus terhitung dan
    laporannya harus menyebutnya."""
    async def jalan():
        # 10 aset perolehan 2023; 4 sudah diperiksa (jatuh di bulan kegiatan
        # 2025), 6 belum (jatuh di 2023 — di luar tahun linimasa).
        await _seed(dbr, [_keg(1, 5)], _aset("k1", 10, ditemukan=4, tahun="2023"))
        d = await rp._build_satker_report_v2("k1")
        assert d["linimasa_luar_tahun"] == 6, d["linimasa_luar_tahun"]
        assert d["linimasa_jumlah"] == 4
        assert d["total_count"] == 10, "totalnya tetap utuh di tempat lain"
        t = _teks_template()
        assert "berperistiwa di luar" in t, "batasnya tak dinyatakan di laporan"
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


def test_linimasa_menyatakan_CAMPURAN_sumbernya():
    """Sejak `tanggal_inventarisasi` dicap, linimasa memakai tanggal
    pemeriksaan SUNGGUHAN — tetapi aset yang diperiksa sebelum stempel itu
    ada tetap memakai perkiraan periode kegiatan.

    Angka campuran yang diam soal campurannya adalah bentuk paling halus dari
    mengarang: pembacanya menyimpulkan seluruhnya presisi. Laporan wajib
    menyebut ketiga keadaannya — seluruhnya bercap, sebagian, atau tak satu
    pun.
    """
    t = re.sub(r"\s+", " ", _teks_template())
    assert "kumulatif" in t.lower()
    assert "linimasa_pct_stempel" in t, "porsi bercap tak pernah disebut"
    assert "tanggal pemeriksaannya sendiri" in t
    assert "sebelum tanggal itu mulai direkam" in t, (
        "keadaan campuran tak dijelaskan")


def test_linimasa_memakai_stempel_aset_bukan_bulan_kegiatan(dbr):
    """Inti dari seluruh perubahan ini: aset yang DICAP Agustus masuk Agustus,
    walau kegiatannya dimulai Mei."""
    async def jalan():
        aset = _aset("k1", 4, ditemukan=4)
        for a in aset:
            a["tanggal_inventarisasi"] = "2025-08-14T09:00:00+00:00"
        await _seed(dbr, [_keg(1, 5)], aset)
        d = await rp._build_satker_report_v2("k1")
        per_bulan = {b["bulan"]: b["tercatat"] for b in d["linimasa"]}
        assert per_bulan["MEI"] == 0, "masih memakai bulan kegiatan"
        assert per_bulan["AGU"] == 4
        assert d["linimasa_pct_stempel"] == 100.0
        assert d["linimasa_perkiraan"] == 0
    _jalan(jalan())


def test_aset_TERPERIKSA_tanpa_stempel_jatuh_ke_bulan_kegiatan(dbr):
    """Data lama tak boleh hilang dari linimasa. Tanpa cadangan ini seluruh
    riwayat sebelum stempel diperkenalkan lenyap dari grafiknya.

    Cadangan ini hanya berlaku bagi aset yang SUDAH diperiksa. Aset yang belum
    diperiksa memakai bulan perolehannya, dan itu bukan perkiraan — itu
    tanggal sungguhan untuk peristiwa yang lain."""
    async def jalan():
        aset = _aset("k1", 4, ditemukan=2, perolehan="2025-02-01")
        aset[0]["tanggal_inventarisasi"] = "2025-08-14T09:00:00+00:00"
        await _seed(dbr, [_keg(1, 5)], aset)
        d = await rp._build_satker_report_v2("k1")
        per_bulan = {b["bulan"]: b["tercatat"] for b in d["linimasa"]}
        assert per_bulan["AGU"] == 1, "aset bercap Agustus pindah bulan"
        assert per_bulan["MEI"] == 1, "aset terperiksa tanpa stempel hilang"
        assert per_bulan["FEB"] == 2, "dua aset belum diperiksa, perolehan Feb"
        # Hanya dua aset TERPERIKSA yang masuk hitungan stempel/perkiraan.
        assert d["linimasa_perkiraan"] == 1
        assert d["linimasa_pct_stempel"] == 50.0
    _jalan(jalan())


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
    """Enam bagian bernama, masing-masing menjawab satu pertanyaan.

    Bagian yang panjang (kegiatan, personil) dipaginasi, jadi judulnya muncul
    lebih dari sekali — yang dijaga adalah HIMPUNAN bagiannya, bukan jumlah
    kemunculannya.
    """
    t = _teks_template()
    judul = re.findall(r'class="no">\{\{ sec\.n \}\}</span>([^<{]+)', t)
    unik = []
    for j in (x.strip() for x in judul):
        if j and j not in unik:
            unik.append(j)
    assert unik == ["Ringkasan Eksekutif", "Capaian per Kegiatan",
                    "Kategori Hasil di Lapangan", "Analisis Data",
                    "Personil Terlibat", "Simpulan"], unik


# ── Halaman A4 tetap ────────────────────────────────────────────────────
#
# Permintaan pemilik: *"buatkan dengan fix A4 dan sudah dibagi perhalamannya
# persis seperti di tampilan preview laporan eksekutif"*.

def test_lembar_berukuran_A4_pasti():
    """794x1123px = A4 pada 96dpi, ukuran yang sama dengan pratinjau laporan
    eksekutif. Tinggi yang mengikuti isi membuat batas halaman baru terlihat
    setelah dicetak — dan saat itu sudah terlambat."""
    t = _teks_template()
    assert "width: 794px; height: 1123px" in t
    assert "@page { size: A4 portrait; margin: 0; }" in t
    assert "page-break-after: always" in t


def test_bagian_panjang_dipaginasi_bukan_dipotong():
    """Tinggi tetap + `overflow: hidden` akan MEMOTONG diam-diam. Kegiatan
    dan personil karenanya dibagi per halaman di template, bukan dibiarkan
    meluber ke luar lembar."""
    t = _teks_template()
    assert "KEG_PER_HAL" in t and "PERSONIL_PER_HAL" in t
    assert "kegiatan_list[mulai:mulai + KEG_PER_HAL]" in t
    assert "orang[mulai:mulai + PERSONIL_PER_HAL]" in t


def test_tiap_lembar_berkop_dan_berkaki():
    """Lembar tanpa kop kehilangan identitasnya begitu dicetak dan tercecer
    dari berkasnya. Kop & kaki ditulis SEKALI sebagai makro — lembar baru tak
    boleh lahir dengan kop yang sedikit berbeda."""
    t = _teks_template()
    assert "{% macro kop(" in t and "{% macro kaki(" in t
    # Setiap lembar isi memanggil keduanya.
    assert t.count("{{ kop('Bagian ' ~ sec.n) }}") >= 5
    assert t.count("{{ kaki(") >= 5


def test_sampul_menyatakan_lingkupnya():
    """Sampul adalah yang pertama dibaca dan paling sering difotokopi
    terpisah. Laporan tersaring yang sampulnya diam akan beredar sebagai
    laporan satker penuh."""
    t = _teks_template()
    i = t.index('data-testid="sampul-cap-filter"')
    assert "{% if filter_aktif %}" in t[i - 200:i]
    assert "bukan keseluruhan satker" in t


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


def test_stiker_dihitung_dengan_nilai_yang_BENAR_BENAR_dipakai_aplikasi(dbr):
    """Laporan gabungan pernah membandingkan `stiker_status` dengan
    "Terpasang" — tanpa "Sudah". Nilai itu tak pernah ada di basis data
    (formulir aset hanya menawarkan "Belum Terpasang" dan "Sudah Terpasang"),
    jadi kartu berstiker SELALU nol dan kartu belum-berstiker selalu memuat
    seluruh temuan. Tak ada galat, hanya angka yang tenang dan keliru.

    Uji ini memakai nilai sungguhan dan campuran, bukan nilai seragam: fixture
    yang seluruh asetnya berstiker akan tetap lolos meski pembandingnya
    tertukar dengan "selalu benar"."""
    from report_utils import STIKER_TERPASANG

    async def jalan():
        aset = _aset("k1", 6, ditemukan=6)
        # Dua dari enam temuan BELUM berstiker.
        aset[4]["stiker_status"] = "Belum Terpasang"
        aset[5]["stiker_status"] = ""
        await _seed(dbr, [_keg(1, 5)], aset)
        d = await rp._build_satker_report_v2("k1")
        kat = {k["label"]: k["n"] for k in d["kategori_lapangan"]}
        assert kat["BMN Ditemukan"] == 6
        assert kat["Ditemukan, Stiker Terpasang"] == 4, kat
        assert kat["Ditemukan, Belum Berstiker"] == 2, kat
        # Ringkasan utama memakai perbandingan yang SAMA.
        assert d["stiker_terpasang"] == 4 and d["stiker_belum"] == 2
    assert STIKER_TERPASANG == "Sudah Terpasang", (
        "konstanta bergeser dari nilai yang ditulis AssetForm.jsx/models.py")
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


# ── Bulan yang BELUM BERJALAN tak boleh berisi apa-apa ───────────────────
#
# Laporan pemilik: *"tahun berjalan seharusnya bulan kedepannya masih belum
# ada data tapi kenapa bisa muncul data."*
#
# Angka linimasa kumulatif, jadi tanpa batas ini bulan sisa tahun berjalan
# menyalin angka bulan terakhir dan tampil seolah pekerjaannya sudah selesai
# sampai Desember — grafik yang MERAMAL, bukan melaporkan. Pembacanya tak
# punya cara membedakan "belum terjadi" dari "tidak ada tambahan".

def _keg_pada(i, tahun, bulan):
    return {"id": f"t{i}", "kode_satker": "401234",
            "nama_kegiatan": f"Kegiatan {i}", "nomor_surat": f"S-{i}",
            "tanggal_mulai": f"{tahun}-{bulan:02d}-01",
            "tanggal_selesai": f"{tahun}-{bulan:02d}-28",
            "nama_satker": "Satker Uji", "created_at": f"{tahun}-{bulan:02d}-01"}


def test_bulan_setelah_bulan_ini_dikosongkan(dbr):
    from datetime import datetime
    kini = datetime.now()

    async def jalan():
        bulan = max(1, kini.month - 1)
        await _seed(dbr, [_keg_pada(1, kini.year, bulan)], _aset("t1", 6, ditemukan=2))
        d = await rp._build_satker_report_v2("t1")
        assert d["tahun_linimasa"] == kini.year
        assert d["linimasa_bulan_terakhir"] == kini.month
        for i, b in enumerate(d["linimasa"], start=1):
            if i > kini.month:
                assert b["belum_berjalan"] is True, b["bulan"]
                assert b["tercatat"] == 0, (b["bulan"], b["tercatat"])
                assert b["ditemukan"] == 0, b["bulan"]
            else:
                assert b["belum_berjalan"] is False, b["bulan"]
    _jalan(jalan())


def test_tahun_lampau_ditampilkan_PENUH(dbr):
    """Di tahun yang sudah lewat, angka bulan Desember memang bermakna
    'sampai akhir tahun sekian' — mengosongkannya justru menghapus fakta."""
    from datetime import datetime

    async def jalan():
        lalu = datetime.now().year - 1
        await _seed(dbr, [_keg_pada(1, lalu, 3)], _aset("t1", 5, ditemukan=2))
        d = await rp._build_satker_report_v2("t1")
        assert d["tahun_linimasa"] == lalu
        assert d["linimasa_bulan_terakhir"] == 12
        assert all(not b["belum_berjalan"] for b in d["linimasa"])
        # Dua aset terperiksa jatuh di bulan kegiatan (Maret); tiga sisanya
        # belum diperiksa dan berperolehan tahun lain, jadi di luar grafik.
        per_bulan = {b["bulan"]: b["tercatat"] for b in d["linimasa"]}
        assert per_bulan["MAR"] == 2, per_bulan
        assert d["linimasa_luar_tahun"] == 3
    _jalan(jalan())


def test_salah_ketik_tahun_tak_menyandera_seluruh_grafik(dbr):
    """Satu "2062" alih-alih "2026" akan memindahkan linimasa ke tahun itu dan
    menyisakan grafik kosong, sementara pekerjaan tahun ini tak terlihat sama
    sekali. Kekeliruan datanya tetap tampak di daftar kegiatan."""
    from datetime import datetime
    kini = datetime.now()

    async def jalan():
        await _seed(dbr, [_keg_pada(1, kini.year, max(1, kini.month - 1)),
                          _keg_pada(2, 2062, 5)],
                    _aset("t1", 4, ditemukan=2) + _aset("t2", 3, ditemukan=1))
        d = await rp._build_satker_report_v2("t1")
        assert d["tahun_linimasa"] == kini.year, d["tahun_linimasa"]
        assert d["linimasa_ada"] is True, "grafik tahun ini ikut hilang"
        # Kegiatan bertahun ganjil TETAP tercatat di daftarnya.
        assert len(d["kegiatan_list"]) == 2
    _jalan(jalan())


def test_seluruh_kegiatan_bertahun_depan_tak_menggambar_apa_pun(dbr):
    from datetime import datetime

    async def jalan():
        depan = datetime.now().year + 1
        await _seed(dbr, [_keg_pada(1, depan, 2)], _aset("t1", 5, ditemukan=2))
        d = await rp._build_satker_report_v2("t1")
        assert d["tahun_linimasa"] == datetime.now().year
        assert d["linimasa_ada"] is False, "menggambar tahun yang belum terjadi"
    _jalan(jalan())


def test_bulan_belum_berjalan_dibedakan_secara_VISUAL():
    """Kalau bulan belum-berjalan digambar sama dengan bulan tanpa tambahan,
    salah bacanya kembali — hanya lebih halus."""
    t = _teks_template()
    assert "{% if b.belum_berjalan %}" in t
    assert ".lm-belum" in t, "tak ada penanda khusus"
    assert "belum berjalan, bukan berarti tanpa tambahan" in t


def test_linimasa_memakai_jam_yang_SAMA_dengan_tanggal_cetak():
    """Jam berbeda membuat laporan bertanggal 1 Oktober memuat grafik yang
    berhenti di September — dua tanggal pada satu dokumen, tanpa penjelasan."""
    import inspect
    src = inspect.getsource(rp._build_satker_report_v2)
    assert "sekarang = datetime.now()" in src
    assert "datetime.now(timezone.utc)" not in src.split("sekarang =")[1][:200]
