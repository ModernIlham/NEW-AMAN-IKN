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


# ── 1. LINIMASA: RUMAH = BMN TERCATAT, ISI = CAPAIAN ────────────────────
#
# Permintaan pemilik: *"pada progres inventarisasi jadikan grafik rumah adalah
# BMN tercatat dan setiap kali ada tambahan BMN tercatat maka akan terlihat,
# dan di dalamnya baru informasi data sekarang."*
#
# Versi sebelumnya menggambar PERISTIWA per bulan. Grafiknya fluktuatif, tetapi
# tak pernah menjawab pertanyaan yang paling sering diajukan atas laporan
# berjudul "Progres Inventarisasi": berapa yang harus diperiksa, dan berapa
# yang sudah. Jarak antara keduanya adalah tunggakannya, dan pada grafik
# peristiwa jarak itu tak punya bentuk sama sekali.

def _lm(d):
    return {b["bulan"]: b for b in d["linimasa"]}


def test_RUMAH_adalah_BMN_tercatat_dan_isinya_capaian(dbr):
    """Rumah = stok yang harus diperiksa; isinya = yang sudah diperiksa;
    rongganya = tunggakan. Ketiganya harus berjumlah tepat."""
    async def jalan():
        # 15 aset perolehan 2023 (stok awal 2025); 6 di antaranya diperiksa —
        # 4 pada kegiatan Mei, 2 pada kegiatan Juli.
        await _seed(dbr, [_keg(1, 5), _keg(2, 7)],
                    _aset("k1", 10, ditemukan=4) + _aset("k2", 5, ditemukan=2))
        d = await rp._build_satker_report_v2("k1")
        lm = _lm(d)
        # RUMAHNYA TETAP 15 sepanjang tahun — tak ada perolehan baru di 2025.
        assert [b["tercatat"] for b in d["linimasa"]] == [15] * 12
        # ISINYA tumbuh mengikuti pemeriksaan.
        assert lm["APR"]["ditemukan"] == 0 and lm["APR"]["belum"] == 15
        assert lm["MEI"]["ditemukan"] == 4 and lm["MEI"]["belum"] == 11
        assert lm["JUN"]["ditemukan"] == 4, "capaian tak boleh mundur"
        assert lm["JUL"]["ditemukan"] == 6 and lm["JUL"]["belum"] == 9
        assert lm["DES"]["ditemukan"] == 6 and lm["DES"]["belum"] == 9
        # Rumah = isi + rongga, tiap bulan, tanpa kecuali.
        for b in d["linimasa"]:
            assert b["ditemukan"] + b["periksa_lain"] + b["belum"] == b["tercatat"], b
    _jalan(jalan())


def test_TAMBAHAN_BMN_tercatat_terlihat_sebagai_rumah_yang_tumbuh(dbr):
    """*"setiap kali ada tambahan BMN tercatat maka akan terlihat."* Rumah yang
    datar tak memberi tahu apa pun tentang stok yang bertambah."""
    async def jalan():
        aset = (_aset("k1", 4, ditemukan=0, perolehan="2025-03-09")
                + _aset("k2", 6, ditemukan=0, perolehan="2025-08-20"))
        await _seed(dbr, [_keg(1, 5), _keg(2, 7)], aset)
        d = await rp._build_satker_report_v2("k1")
        lm = _lm(d)
        assert lm["FEB"]["tercatat"] == 0
        assert lm["MAR"]["tercatat"] == 4 and lm["MAR"]["tambahan"] == 4
        assert lm["JUL"]["tercatat"] == 4 and lm["JUL"]["tambahan"] == 0
        assert lm["AGU"]["tercatat"] == 10 and lm["AGU"]["tambahan"] == 6
        assert lm["DES"]["tercatat"] == 10, "rumah menyusut setelah tumbuh"
        assert d["linimasa_tambah_tahun"] == 10
        t = _teks_template()
        assert "b.tambahan" in t, "tambahannya tak digambar di atas atap"
    _jalan(jalan())


def test_STOK_AWAL_ikut_dihitung_bukan_dibuang(dbr):
    """BMN perolehan tahun sebelumnya tetap menjadi tanggungan tahun ini.
    Rumah yang dimulai dari nol menggambarkan satker seolah baru berdiri, dan
    tunggakan terbesarnya — justru yang warisan — lenyap dari grafik."""
    async def jalan():
        aset = (_aset("k1", 12, ditemukan=0, tahun="2019")
                + _aset("k2", 3, ditemukan=0, perolehan="2025-06-01"))
        await _seed(dbr, [_keg(1, 5), _keg(2, 7)], aset)
        d = await rp._build_satker_report_v2("k1")
        lm = _lm(d)
        assert d["linimasa_stok_awal"] == 12
        assert lm["JAN"]["tercatat"] == 12, "stok warisan hilang dari Januari"
        assert lm["JUN"]["tercatat"] == 15
        assert d["total_count"] == 15
        t = _teks_template()
        assert "stok awal" in t, "stok awalnya tak dijelaskan"
    _jalan(jalan())


def test_aset_TANPA_tanggal_perolehan_masuk_stok_awal(dbr):
    """Ia jelas sudah tercatat; hanya kapannya yang tak diketahui. Membuangnya
    berarti menyusutkan stok yang nyata."""
    async def jalan():
        aset = _aset("k1", 5, ditemukan=0)
        for a in aset[:2]:
            a["purchase_date"] = ""
        await _seed(dbr, [_keg(1, 5)], aset)
        d = await rp._build_satker_report_v2("k1")
        assert d["linimasa_stok_awal"] == 5
        assert _lm(d)["JAN"]["tercatat"] == 5
    _jalan(jalan())


def test_perolehan_bertahun_DEPAN_tak_masuk_stok_tahun_ini(dbr):
    """Menaruhnya di stok awal akan menyatakan barang yang belum ada sebagai
    sudah ada."""
    async def jalan():
        aset = (_aset("k1", 4, ditemukan=0, tahun="2019")
                + _aset("k2", 7, ditemukan=0, perolehan="2030-01-01"))
        await _seed(dbr, [_keg(1, 5), _keg(2, 7)], aset)
        d = await rp._build_satker_report_v2("k1")
        assert d["linimasa_stok_awal"] == 4
        assert [b["tercatat"] for b in d["linimasa"]] == [4] * 12
    _jalan(jalan())


def test_linimasa_menandai_bulan_kegiatan_dimulai(dbr):
    """Tanpa penanda ini, bulan yang hanya meneruskan angka bulan sebelumnya
    terbaca seolah ada kegiatan baru di sana."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5)], _aset("k1", 3))
        lm = (await rp._build_satker_report_v2("k1"))["linimasa"]
        mulai = [b["bulan"] for b in lm if b["mulai"]]
        assert mulai == ["MEI"], mulai
    _jalan(jalan())


def test_tinggi_batang_dihitung_di_server_bukan_di_template(dbr):
    """Aritmetika di dalam Jinja mudah membagi nol tanpa terlihat."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5)], _aset("k1", 8, ditemukan=4))
        d = await rp._build_satker_report_v2("k1")
        assert all("h_tercatat" in b for b in d["linimasa"])
        assert max(b["h_tercatat"] for b in d["linimasa"]) == 100
    _jalan(jalan())


def test_satker_tanpa_aset_tak_membagi_nol(dbr):
    async def jalan():
        await _seed(dbr, [_keg(1, 5)], [])
        d = await rp._build_satker_report_v2("k1")
        assert d["linimasa_ada"] is False
        assert all(b["h_tercatat"] == 0 for b in d["linimasa"])
    _jalan(jalan())


def test_ISI_mengikuti_stempel_aset_bukan_bulan_kegiatan(dbr):
    """Aset yang DICAP Agustus mengisi rumah mulai Agustus, walau kegiatannya
    dimulai Mei."""
    async def jalan():
        aset = _aset("k1", 4, ditemukan=4)
        for a in aset:
            a["tanggal_inventarisasi"] = "2025-08-14T09:00:00+00:00"
        await _seed(dbr, [_keg(1, 5)], aset)
        d = await rp._build_satker_report_v2("k1")
        lm = _lm(d)
        assert lm["MEI"]["ditemukan"] == 0, "masih memakai bulan kegiatan"
        assert lm["MEI"]["belum"] == 4
        assert lm["AGU"]["ditemukan"] == 4 and lm["AGU"]["belum"] == 0
        assert d["linimasa_pct_stempel"] == 100.0
        assert d["linimasa_perkiraan"] == 0
    _jalan(jalan())


def test_aset_TERPERIKSA_tanpa_stempel_jatuh_ke_bulan_kegiatan(dbr):
    """Data lama tak boleh hilang dari isian rumah. Tanpa cadangan ini seluruh
    riwayat sebelum stempel diperkenalkan lenyap dari capaiannya."""
    async def jalan():
        aset = _aset("k1", 4, ditemukan=2, perolehan="2025-02-01")
        aset[0]["tanggal_inventarisasi"] = "2025-08-14T09:00:00+00:00"
        await _seed(dbr, [_keg(1, 5)], aset)
        d = await rp._build_satker_report_v2("k1")
        lm = _lm(d)
        assert lm["FEB"]["tercatat"] == 4, "rumahnya berdiri sejak perolehan"
        assert lm["MEI"]["ditemukan"] == 1, "aset terperiksa tanpa stempel hilang"
        assert lm["AGU"]["ditemukan"] == 2, "aset bercap Agustus tak masuk"
        assert lm["DES"]["belum"] == 2
        assert d["linimasa_perkiraan"] == 1
        assert d["linimasa_pct_stempel"] == 50.0
    _jalan(jalan())


def test_pemeriksaan_MENDAHULUI_perolehan_digencet_dan_DIHITUNG(dbr):
    """Isi tak mungkin melampaui rumahnya; kalau terjadi, itu kekeliruan data.
    Digencet supaya batangnya tetap terbaca, lalu DIHITUNG — grafik yang
    menggencet diam-diam menyembunyikan justru baris yang perlu dibetulkan."""
    async def jalan():
        # Diperoleh Oktober, tetapi diperiksa Maret tahun yang sama.
        aset = _aset("k1", 5, ditemukan=5, perolehan="2025-10-01")
        for a in aset:
            a["tanggal_inventarisasi"] = "2025-03-05T09:00:00+00:00"
        await _seed(dbr, [_keg(1, 5)], aset)
        d = await rp._build_satker_report_v2("k1")
        lm = _lm(d)
        assert lm["MAR"]["tercatat"] == 0
        assert lm["MAR"]["ditemukan"] == 0, "isi melampaui rumahnya"
        assert lm["MAR"]["belum"] == 0
        assert d["linimasa_janggal"] == 5
        assert lm["OKT"]["tercatat"] == 5 and lm["OKT"]["ditemukan"] == 5
        t = _teks_template()
        assert "mendahului tanggal perolehannya" in t, "kejanggalan tak disebut"
    _jalan(jalan())


def test_linimasa_menyatakan_CAMPURAN_sumbernya():
    """Aset yang diperiksa sebelum stempel ada memakai perkiraan periode
    kegiatan. Angka campuran yang diam soal campurannya adalah bentuk paling
    halus dari mengarang: pembacanya menyimpulkan seluruhnya presisi."""
    t = re.sub(r"\s+", " ", _teks_template())
    assert "linimasa_perkiraan" in t, "porsi perkiraan tak pernah disebut"
    assert "sebelum tanggal pemeriksaan mulai direkam" in t, (
        "keadaan campuran tak dijelaskan")



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
    assert unik == ["Ringkasan Eksekutif", "BMN Tercatat per Kegiatan",
                    "Capaian per Kegiatan", "Kategori Hasil di Lapangan",
                    "Analisis Data", "Personil Terlibat", "Simpulan"], unik


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
        # Kelima aset berperolehan tahun sebelumnya, jadi rumahnya berdiri
        # penuh sejak Januari; dua di antaranya diperiksa pada bulan kegiatan.
        lm = _lm(d)
        assert [b["tercatat"] for b in d["linimasa"]] == [5] * 12
        assert lm["FEB"]["ditemukan"] == 0
        assert lm["MAR"]["ditemukan"] == 2 and lm["MAR"]["belum"] == 3
        assert lm["DES"]["ditemukan"] == 2, "capaian akhir tahun hilang"
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


def test_kegiatan_bertahun_depan_tak_menggambar_CAPAIAN_apa_pun(dbr):
    """Kegiatannya belum terjadi, jadi tak ada pemeriksaan yang bisa mengisi
    rumahnya. Tetapi BMN-nya SUDAH tercatat, dan rumah yang ikut dikosongkan
    akan menyatakan satker itu tak punya barang sama sekali."""
    from datetime import datetime

    async def jalan():
        depan = datetime.now().year + 1
        await _seed(dbr, [_keg_pada(1, depan, 2)], _aset("t1", 5, ditemukan=2))
        d = await rp._build_satker_report_v2("t1")
        assert d["tahun_linimasa"] == datetime.now().year
        assert d["linimasa_stok_awal"] == 5, "stok yang nyata ikut dihapus"
        lm = _lm(d)
        assert lm["JAN"]["tercatat"] == 5 and lm["JAN"]["belum"] == 5
        assert all(b["ditemukan"] == 0 for b in d["linimasa"]), (
            "menggambar capaian dari kegiatan yang belum terjadi")
    _jalan(jalan())


def test_bulan_belum_berjalan_dibedakan_secara_VISUAL():
    """Kalau bulan belum-berjalan digambar sama dengan bulan tanpa tambahan,
    salah bacanya kembali — hanya lebih halus."""
    t = _teks_template()
    assert "{% if b.belum_berjalan %}" in t
    assert ".lm-belum" in t, "tak ada penanda khusus"
    # Spasi dinormalkan: kalimatnya dibungkus antarbaris di template, dan
    # pencarian mentah akan gagal karena pembungkusan, bukan karena kalimatnya
    # hilang — kegagalan yang menyesatkan pembacanya.
    assert "belum berjalan, bukan berarti tanpa tambahan" in re.sub(r"\s+", " ", t)


def test_linimasa_memakai_jam_yang_SAMA_dengan_tanggal_cetak():
    """Jam berbeda membuat laporan bertanggal 1 Oktober memuat grafik yang
    berhenti di September — dua tanggal pada satu dokumen, tanpa penjelasan."""
    import inspect
    src = inspect.getsource(rp._build_satker_report_v2)
    assert "sekarang = datetime.now()" in src
    assert "datetime.now(timezone.utc)" not in src.split("sekarang =")[1][:200]


# ── Tata letak: grafik terbaca, Eselon II, simpulan menunjuk ────────────
#
# Permintaan pemilik: *"maksimalkan penempatan untuk linimasa chartbar baik
# bulan maupun tahun agar tidak terlalu gepeng chartnya dan angkanya juga jadi
# jelas ... tambahkan juga grafik untuk pereselon II-nya dibagian analisis
# data ... simpulan juga tidak spesifik terorganisasir dengan baik per
# kegiatannya."*

def _angka_css(teks, prop):
    """Nilai px sebuah properti CSS, mis. `_angka_css(t, '.lm-plot ... height')`."""
    import re
    m = re.search(re.escape(prop) + r":\s*(\d+(?:\.\d+)?)px", teks)
    return float(m.group(1)) if m else None


def test_grafik_linimasa_dan_tahun_tak_lagi_gepeng():
    """Dua belas batang setinggi 118px pada lembar 1123px: selisih 6 dan 21
    nyaris tak terbaca, dan angkanya terjepit. Tingginya dinaikkan; ambang di
    sini menjaga agar ia tak diam-diam mengecil lagi."""
    import re
    t = _teks_template()
    lm = re.search(r"\.lm-plot \{[^}]*height:\s*(\d+)px", t)
    th = re.search(r"\.th-plot \{[^}]*height:\s*(\d+)px", t)
    assert lm and int(lm.group(1)) >= 240, "linimasa bulanan kembali gepeng"
    assert th and int(th.group(1)) >= 200, "grafik tahun perolehan kembali gepeng"
    # Angka di dalam dan di atas batang harus terbaca, bukan 7px.
    nilai = re.search(r"\.lm-nilai \{[^}]*font-size:\s*([\d.]+)px", t)
    atas = re.search(r"\.lm-atas \{[^}]*font-size:\s*([\d.]+)px", t)
    assert nilai and float(nilai.group(1)) >= 8.5, "angka di batang masih kecil"
    assert atas and float(atas.group(1)) >= 9, "total di atas batang masih kecil"


def test_grafik_per_eselon_II_ada_di_analisis_data(dbr):
    """Satu Eselon I biasanya membawahi beberapa Eselon II; grafik yang
    berhenti di Eselon I menyembunyikan justru unit yang bertanggung jawab
    atas barangnya."""
    async def jalan():
        aset = _aset("k1", 6, ditemukan=6)
        for i, a in enumerate(aset):
            a["eselon1"] = "Ditjen Satu"
            a["eselon2"] = f"Direktorat {i % 3}"
        await _seed(dbr, [_keg(1, 5)], aset)
        d = await rp._build_satker_report_v2("k1")
        nama = {c["name"]: c["count"] for c in d["chart_eselon2"]}
        assert nama == {"Direktorat 0": 2, "Direktorat 1": 2, "Direktorat 2": 2}, nama
        # Eselon I tetap ada — yang satu tak menggantikan yang lain.
        assert [c["name"] for c in d["chart_eselon1"]] == ["Ditjen Satu"]
        # Panelnya benar-benar masuk halaman analisis, bukan cuma datanya.
        judul = [p["judul"] for h in d["halaman_analisis"]
                 for sisi in ("kiri", "kanan") for p in h[sisi]]
        assert "Per Eselon II" in judul, judul
        assert "Per Eselon I" in judul, judul
    _jalan(jalan())


def test_eselon_II_kosong_menjelaskan_dirinya(dbr):
    """Panel kosong tanpa keterangan terbaca sebagai "sistemnya rusak".
    Yang benar: datanya memang belum diisi, dan itu bisa ditindaklanjuti."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5)], _aset("k1", 3))
        d = await rp._build_satker_report_v2("k1")
        assert d["chart_eselon2"] == []
        # Panelnya TETAP muncul walau kosong. Panel yang dibuang diam-diam
        # membuat pembacanya mengira dimensi itu tak ada di sistem.
        kosong = [p for h in d["halaman_analisis"]
                  for sisi in ("kiri", "kanan") for p in h[sisi]
                  if p["judul"] == "Per Eselon II"]
        assert len(kosong) == 1 and kosong[0]["baris"] == []
    t = _teks_template()
    assert "Belum ada aset yang mencantumkan data ini" in t
    _jalan(jalan())


def test_simpulan_MENUNJUK_kegiatan_dan_yang_tertinggal_dibaca_lebih_dulu(dbr):
    """Simpulan tingkat satker benar tetapi tak dapat ditindaklanjuti: ia tak
    memberi tahu kegiatan MANA yang tertinggal. Yang paling perlu perhatian
    harus dibaca lebih dulu, bukan terkubur di bawah yang sudah tuntas."""
    async def jalan():
        # k1 tuntas (6/6), k2 tertinggal (1/8).
        await _seed(dbr, [_keg(1, 5), _keg(2, 7)],
                    _aset("k1", 6, ditemukan=6) + _aset("k2", 8, ditemukan=1))
        d = await rp._build_satker_report_v2("k1")
        sk = d["simpulan_kegiatan"]
        assert len(sk) == 2
        assert sk[0]["nama"] == "Kegiatan 2", "yang tertinggal tak dibaca lebih dulu"
        assert sk[0]["nada"] == "tertinggal" and sk[0]["pct"] < 50
        assert sk[1]["nama"] == "Kegiatan 1" and sk[1]["nada"] == "tuntas"
        # Teksnya MENYEBUT angkanya, bukan sekadar "perlu perhatian".
        assert "1 dari 8 NUP" in str(sk[0]["teks"])
        assert "7 NUP</strong> belum diperiksa" in str(sk[0]["teks"])
        # Pengesahan disebut apa adanya.
        assert sk[0]["sah"] == "belum disahkan"
    t = _teks_template()
    assert "Simpulan per Kegiatan" in t
    _jalan(jalan())


def test_kegiatan_tuntas_tapi_BELUM_DISAHKAN_tak_disebut_selesai(dbr):
    """Capaian 100% yang belum disahkan BELUM selesai secara administratif.
    Simpulan yang diam soal itu menyatakan selesai lebih awal dari
    kenyataannya."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5)], _aset("k1", 5, ditemukan=5))
        sk = (await rp._build_satker_report_v2("k1"))["simpulan_kegiatan"][0]
        assert sk["pct"] == 100.0 and sk["nada"] == "tuntas"
        assert sk["disahkan"] is False and sk["sah"] == "belum disahkan"
    _jalan(jalan())


def test_lembar_simpulan_dipaginasi_agar_tak_terpotong_diam_diam(dbr):
    """Lembarnya bertinggi TETAP dengan overflow:hidden — blok yang tak muat
    hilang tanpa satu pun tanda. Cacahnya dibatasi di template."""
    import re
    t = _teks_template()
    assert "{% set SK_HAL_1 = " in t and "{% set SK_HAL_N = " in t
    assert "jml_hal_sk" in t
    # Cacah per halaman hanya bisa DITETAPKAN kalau tinggi tiap kartu SERAGAM.
    # Nama kegiatan yang panjang membungkus jadi tiga baris — dan lencana
    # "Disahkan" yang lebih lebar dari "Berjalan" menyempitkan kolom namanya
    # sehingga bungkusnya bertambah lagi. Delapan kartu lalu muat di satu
    # halaman tetapi tidak di halaman lain, dan yang tak muat hilang tanpa
    # tanda.
    #
    # Ini diperiksa STRUKTURAL, bukan lewat render: uji render hanya dapat
    # membuktikan "data INI muat", sedang yang harus dijamin adalah "data apa
    # pun muat". Mutasi yang mencabut tinggi tetap ini lolos dari tiga fixture
    # render berturut-turut sebelum pemeriksaan ini ditambahkan.
    nama = re.search(r"\.keg-nama \{([^}]*)\}", t)
    assert nama, ".keg-nama hilang"
    assert re.search(r"height:\s*\d+(\.\d+)?px", nama.group(1)), (
        "tinggi kartu kegiatan kembali mengikuti isi")
    assert "overflow: hidden" in nama.group(1), (
        "tanpa overflow:hidden, tinggi tetapnya tak memotong apa pun")

    async def jalan():
        keg = [_keg(i, (i % 12) + 1) for i in range(1, 15)]
        aset = []
        for i in range(1, 15):
            aset += _aset(f"k{i}", 3, ditemukan=i % 4)
        await _seed(dbr, keg, aset)
        d = await rp._build_satker_report_v2("k1")
        assert len(d["simpulan_kegiatan"]) == 14, "ada kegiatan yang hilang"
    _jalan(jalan())


def _render_pdf(d):
    """(jumlah lembar HTML, jumlah halaman PDF) untuk data laporan `d`."""
    import re
    import tempfile
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    import weasyprint
    import pypdfium2

    env = Environment(
        loader=FileSystemLoader(os.path.join(os.path.dirname(TPL))),
        autoescape=select_autoescape(["html"]))
    html = env.get_template(os.path.basename(TPL)).render(preview=False, **d)
    lembar = len(re.findall(r'<div class="hal[ "]', html))
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        weasyprint.HTML(string=html).write_pdf(f.name)
        return lembar, len(pypdfium2.PdfDocument(f.name))


def test_TIAP_LEMBAR_muat_satu_halaman_A4(dbr):
    """Lembar bertinggi tetap + `overflow: hidden` berarti isi yang tak muat
    HILANG tanpa satu pun tanda di layar — tetapi saat dicetak ia mendorong
    halaman tambahan. Jumlah lembar HTML yang tak sama dengan jumlah halaman
    PDF adalah tanda pasti ada lembar yang meluber.

    Uji ini merender sungguhan. Versi pertamanya hanya memeriksa keberadaan
    `-webkit-line-clamp` di CSS, dan mutasi yang mencabut TINGGI TETAP kartu
    (biang lubernya) lolos tanpa satu pun uji berbunyi: propertinya masih ada,
    hanya tak lagi berefek."""
    async def jalan():
        # Nama kegiatan sengaja PANJANG dan panjangnya BERBEDA-BEDA: nama yang
        # membungkus jadi dua baris membuat delapan kartu muat di satu halaman
        # tetapi tidak di halaman lain. Nama seragam pendek tak akan pernah
        # memicunya.
        keg = []
        for i in range(1, 21):
            k = _keg(i, ((i - 1) % 12) + 1)
            # Panjang field yang REALISTIS. Fixture dengan nomor surat "S-1"
            # dan nama kegiatan pendek tak pernah membuat kartunya membungkus,
            # sehingga mutasi yang mencabut tinggi tetap lolos begitu saja.
            k["nama_kegiatan"] = (
                f"Inventarisasi Barang Milik Negara pada Wilayah Kerja "
                f"Nomor {i} Tahun Anggaran 2025" + (" Lanjutan" * (i % 3)))
            k["nomor_surat"] = f"S-{100 + i}/KPB.401234/{2025}"
            k["penanggung_jawab"] = (
                f"Pejabat Penanggung Jawab Kegiatan Inventarisasi {i}")
            k["nama_satker"] = "Balai Pengelolaan BMN Ibu Kota Nusantara"
            # Lencana "Disahkan" lebih lebar dari "Berjalan" dan tak boleh
            # menyusut, sehingga ia MENYEMPITKAN kolom nama dan menambah baris
            # bungkusnya. Fixture yang seluruhnya belum disahkan tak pernah
            # menemui kartu paling tinggi.
            k["disahkan"] = (i % 3 == 0)
            keg.append(k)
        aset = []
        for i in range(1, 21):
            batch = _aset(f"k{i}", 14 + i, ditemukan=(14 + i) // 2)
            # Sebagian "Tidak Ditemukan" supaya KELIMA chip angka muncul di
            # kartunya. Dengan empat chip barisnya cukup satu baris dan
            # kartunya tak pernah melebar — fixture seperti itu tak akan
            # pernah menyentuh batas halamannya.
            for a in batch[::4]:
                a["inventory_status"] = "Tidak Ditemukan"
            aset += batch
        await _seed(dbr, keg, aset)
        d = await rp._build_satker_report_v2("k1")
        lembar, halaman = _render_pdf(d)
        assert lembar == halaman, (
            f"{lembar} lembar HTML menjadi {halaman} halaman PDF — "
            "ada lembar yang meluber dan isinya terpotong")
        assert lembar > 8, "data ujinya terlalu kecil untuk menguji paginasi"
    _jalan(jalan())


# ── Analisis data tak lagi dipangkas ────────────────────────────────────
#
# Permintaan pemilik: *"perkategori dan lokasi juga buat jangan dibatasi
# biarkan saja mengalir dan buat smart mengatur dan berbagi posisi dengan
# bagian lainnya hingga benar benar 1 kertas penuh."*

def test_kategori_lokasi_dan_eselon_TIDAK_DIPANGKAS_sepuluh_teratas(dbr):
    """`most_common(10)` membuang data tanpa satu pun tanda: satker dengan 23
    lokasi hanya menampilkan 10, dan pembacanya tak punya cara tahu 13 sisanya
    ada. Angka di sini sengaja LEBIH BESAR dari 10 di keempat dimensi —
    fixture dengan sembilan nilai akan lolos meski pemangkasnya dikembalikan."""
    async def jalan():
        aset = _aset("k1", 60, ditemukan=40)
        for i, a in enumerate(aset):
            a["location"] = f"Gedung Blok {i % 23}"
            a["category"] = f"KAT{i % 17}"
            a["eselon1"] = f"Ditjen {i % 13}"
            a["eselon2"] = f"Direktorat {i % 19}"
        await _seed(dbr, [_keg(1, 5)], aset)
        d = await rp._build_satker_report_v2("k1")
        assert len(d["chart_lokasi"]) == 23, len(d["chart_lokasi"])
        assert len(d["chart_kategori"]) == 17, len(d["chart_kategori"])
        assert len(d["chart_eselon1"]) == 13, len(d["chart_eselon1"])
        assert len(d["chart_eselon2"]) == 19, len(d["chart_eselon2"])
        # Dan seluruhnya benar-benar sampai ke halaman, bukan sekadar ke data.
        baris = {}
        for h in d["halaman_analisis"]:
            for sisi in ("kiri", "kanan"):
                for p in h[sisi]:
                    baris.setdefault(p["judul"], 0)
                    baris[p["judul"]] += len(p["baris"])
        assert baris["Per Lokasi"] == 23, baris
        assert baris["Per Kategori"] == 17, baris
        assert baris["Per Eselon II"] == 19, baris
    _jalan(jalan())


def test_halaman_analisis_disusun_dengan_MENGUKUR_bukan_tetapan(dbr):
    """Cacah panel per halaman tak lagi ditetapkan di template. Kalau
    penyusunnya dilepas, seluruh panel menumpuk di satu lembar dan yang tak
    muat hilang diam-diam."""
    async def jalan():
        aset = _aset("k1", 90, ditemukan=60)
        for i, a in enumerate(aset):
            a["location"] = f"Gedung Perkantoran Blok {i % 47}"
            a["category"] = f"KAT{i % 33}"
            a["eselon2"] = f"Direktorat Pengelolaan Kekayaan Negara {i % 19}"
        await _seed(dbr, [_keg(1, 5)], aset)
        d = await rp._build_satker_report_v2("k1")
        hal = d["halaman_analisis"]
        assert len(hal) >= 2, "47 lokasi + 33 kategori muat satu halaman?"
        import laporan_tataletak as tl
        for ke, h in enumerate(hal):
            tersedia = tl.TINGGI_KOLOM - (tl.TINGGI_JUDUL_AWAL if ke == 0
                                          else tl.TINGGI_JUDUL_LANJUT)
            for sisi in ("kiri", "kanan"):
                t = sum(p["tinggi"] for p in h[sisi])
                t += tl.JARAK_PANEL * max(0, len(h[sisi]) - 1)
                assert t <= tersedia, f"hal={ke} {sisi} {t} > {tersedia}"
    t = _teks_template()
    assert "halaman_analisis" in t, "template tak memakai hasil penyusun"
    _jalan(jalan())


# ── Rumah yang sama, diiris per kegiatan ────────────────────────────────
#
# Permintaan pemilik: *"selain grafik gabungan berikan juga grafik yang diambil
# dari grafik gabungan utama, cukup bagian BMN tercatatnya saja sebagai
# rumahnya, dan kemudian di depannya baru data grafik per kegiatannya."*

def test_rumah_per_kegiatan_SAMA_PERSIS_dengan_rumah_grafik_utama(dbr):
    """Kalau tingginya berbeda sedikit saja, kedua grafik itu berbicara tentang
    stok yang berbeda — dan pembacanya tak punya cara tahu yang mana yang
    benar. Rumahnya harus identik sampai ke persen tingginya."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5), _keg(2, 7)],
                    _aset("k1", 9, ditemukan=3, perolehan="2025-02-01")
                    + _aset("k2", 6, ditemukan=2, perolehan="2025-06-01"))
        d = await rp._build_satker_report_v2("k1")
        assert d["linimasa_keg_ada"] is True
        for utama, keg in zip(d["linimasa"], d["linimasa_keg"]):
            assert keg["bulan"] == utama["bulan"]
            assert keg["tercatat"] == utama["tercatat"], keg["bulan"]
            assert keg["h_tercatat"] == utama["h_tercatat"], keg["bulan"]
            assert keg["tambahan"] == utama["tambahan"], keg["bulan"]
            assert keg["belum_berjalan"] == utama["belum_berjalan"]
    _jalan(jalan())


def test_irisan_kegiatan_BERJUMLAH_tepat_dengan_rumahnya(dbr):
    """Irisan yang tak berjumlah tepat berarti ada aset yang hilang atau
    terhitung dua kali — dan batangnya akan terlihat wajar-wajar saja."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5), _keg(2, 7), _keg(3, 9)],
                    _aset("k1", 9, ditemukan=3, perolehan="2025-02-01")
                    + _aset("k2", 6, ditemukan=2, perolehan="2025-06-01")
                    + _aset("k3", 4, ditemukan=0, tahun="2019"))
        d = await rp._build_satker_report_v2("k1")
        for b in d["linimasa_keg"]:
            assert sum(g["n"] for g in b["segmen"]) == b["tercatat"], b
        # Stok warisan k3 sudah berdiri sejak Januari.
        jan = d["linimasa_keg"][0]
        assert jan["tercatat"] == 4 and len(jan["segmen"]) == 1
        # Setelah Juni, ketiganya ikut.
        jun = {b["bulan"]: b for b in d["linimasa_keg"]}["JUN"]
        assert jun["tercatat"] == 19
        assert sorted(g["n"] for g in jun["segmen"]) == [4, 6, 9]
    _jalan(jalan())


def test_satu_kegiatan_TIDAK_menggambar_grafik_kedua(dbr):
    """Pada satu kegiatan, irisannya identik dengan rumahnya sendiri — grafik
    yang tak menambahkan apa pun, hanya satu halaman lagi untuk dilewati."""
    async def jalan():
        await _seed(dbr, [_keg(1, 5)], _aset("k1", 8, ditemukan=3))
        d = await rp._build_satker_report_v2("k1")
        assert d["linimasa_keg_ada"] is False
    _jalan(jalan())


def test_kegiatan_KESEMBILAN_dan_seterusnya_digabung_dan_DISEBUT(dbr):
    """Dua puluh irisan berwarna dalam satu batang tak dapat dibedakan mata
    siapa pun. Yang digabung harus MENYEBUT jumlah kegiatan di dalamnya —
    irisan abu tanpa keterangan terbaca sebagai satu kegiatan bernama
    'lainnya'."""
    async def jalan():
        keg = [_keg(i, 3) for i in range(1, 13)]
        aset = []
        for i in range(1, 13):
            # Ukuran menurun supaya urutan terbesarnya jelas.
            aset += _aset(f"k{i}", 20 - i, ditemukan=0, perolehan="2025-03-01")
        await _seed(dbr, keg, aset)
        d = await rp._build_satker_report_v2("k1")
        leg = d["legenda_kegiatan"]
        assert len(leg) == 9, [x["nama"] for x in leg]
        assert leg[-1]["nama"] == "4 kegiatan lainnya", leg[-1]
        assert leg[-1]["n"] == sum(20 - i for i in range(9, 13))
        # Totalnya tetap utuh.
        assert sum(x["n"] for x in leg) == d["total_count"]
        mar = {b["bulan"]: b for b in d["linimasa_keg"]}["MAR"]
        assert len(mar["segmen"]) == 9
        assert sum(g["n"] for g in mar["segmen"]) == mar["tercatat"]
        # Rinciannya tidak hilang — seluruh 12 kegiatan tetap tercantum.
        assert len(d["kegiatan_list"]) == 12
    t = _teks_template()
    assert "kegiatan lainnya" in t and "Capaian per Kegiatan" in t
    _jalan(jalan())
