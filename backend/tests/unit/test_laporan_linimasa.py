"""Linimasa "Progres Inventarisasi" — modul murni yang dipakai DUA laporan.

Permintaan pemilik: *"pada laporan eksekutif aset berikan linimasa seperti di
laporan gabungan, persis seperti tampilan Progres Inventarisasi-nya."*

Grafiknya sebelumnya hidup sebagai dua ratus baris di dalam
`_build_satker_report_v2` — tak dapat dipakai laporan lain tanpa menyalinnya,
dan salinan kedua tak pernah ikut diperbaiki. Repo ini sudah membayarnya dua
kali: `eselon1` dengan empat salinan cabang bentuk, dan aturan eselon dengan
dua salinan yang sudah berbeda isi sebelum sempat dipakai bersama.

Lima sifat dijaga di sini:

1. Rumahnya BMN tercatat KUMULATIF; isinya capaian pemeriksaan.
2. Stok awal (perolehan tahun sebelumnya) ikut dihitung.
3. Bulan yang belum berjalan DIBEDAKAN dari bulan tanpa tambahan.
4. Isi yang melampaui rumahnya digencet DAN dihitung.
5. Tahun mendatang tak menyandera grafiknya.
"""
from datetime import datetime

import laporan_linimasa as llm

KINI = datetime(2026, 9, 5)


def _keg(i=1, mulai="2026-03-01"):
    return {"id": f"k{i}", "tanggal_mulai": mulai}


def _aset(kid, beli, status="Belum Diinventarisasi", periksa=None, n=1):
    return [{"activity_id": kid, "purchase_date": beli,
             "inventory_status": status,
             llm.FIELD_STEMPEL: periksa} for _ in range(n)]


# ── 1. Rumah dan isinya ─────────────────────────────────────────────────

def test_rumah_adalah_BMN_tercatat_kumulatif():
    h = llm.hitung([_keg()], _aset("k1", "2026-02-10", n=3)
                   + _aset("k1", "2026-05-10", n=2), KINI)
    tercatat = [b["tercatat"] for b in h["baris"][:9]]
    assert tercatat == [0, 3, 3, 3, 5, 5, 5, 5, 5], tercatat


def test_isi_adalah_capaian_pemeriksaan_kumulatif():
    h = llm.hitung([_keg()],
                   _aset("k1", "2026-01-05", "Ditemukan", "2026-03-20", n=4)
                   + _aset("k1", "2026-01-05", "Tidak Ditemukan", "2026-04-02"),
                   KINI)
    b = h["baris"]
    assert (b[2]["ditemukan"], b[2]["periksa_lain"], b[2]["belum"]) == (4, 0, 1)
    assert (b[3]["ditemukan"], b[3]["periksa_lain"], b[3]["belum"]) == (4, 1, 0)


def test_rongga_adalah_selisih_rumah_dan_isinya():
    h = llm.hitung([_keg()], _aset("k1", "2026-01-01", n=10)
                   + _aset("k1", "2026-01-01", "Ditemukan", "2026-02-01", n=3),
                   KINI)
    for b in h["baris"][:9]:
        if not b["belum_berjalan"]:
            assert b["belum"] == b["tercatat"] - b["ditemukan"] - b["periksa_lain"]


# ── 2. Stok awal ────────────────────────────────────────────────────────

def test_perolehan_tahun_sebelumnya_masuk_stok_awal_di_Januari():
    # Rumah yang dimulai dari nol menggambarkan satker seolah baru berdiri,
    # dan tunggakan terbesarnya — justru yang warisan — lenyap dari grafik.
    h = llm.hitung([_keg()], _aset("k1", "2019-07-01", n=7), KINI)
    assert h["stok_awal"] == 7
    assert h["baris"][0]["tercatat"] == 7


def test_tanggal_perolehan_yang_tak_terbaca_juga_masuk_stok_awal():
    # Ia jelas sudah tercatat, hanya kapannya yang tak diketahui; membuangnya
    # berarti menyusutkan stok yang nyata.
    for buruk in ("", None, "bukan tanggal", "9999-99-99"):
        h = llm.hitung([_keg()], _aset("k1", buruk, n=2), KINI)
        assert h["stok_awal"] == 2, buruk


def test_perolehan_tahun_MENDATANG_tak_dihitung_di_mana_pun():
    # Menaruhnya di stok awal akan menyatakan barang yang belum ada sebagai
    # sudah ada.
    h = llm.hitung([_keg()], _aset("k1", "2030-01-01", n=5), KINI)
    assert h["stok_awal"] == 0
    assert all(b["tercatat"] == 0 for b in h["baris"])


# ── 3. Bulan yang belum berjalan ────────────────────────────────────────

def test_bulan_setelah_bulan_ini_ditandai_belum_berjalan():
    h = llm.hitung([_keg()], _aset("k1", "2026-01-01", n=3), KINI)
    tanda = [b["belum_berjalan"] for b in h["baris"]]
    assert tanda == [False] * 9 + [True] * 3, tanda


def test_bulan_belum_berjalan_tak_membawa_angka_apa_pun():
    h = llm.hitung([_keg()], _aset("k1", "2026-01-01", n=3), KINI)
    for b in h["baris"][9:]:
        assert (b["tercatat"], b["ditemukan"], b["belum"]) == (0, 0, 0)


def test_tahun_lampau_ditampilkan_penuh_dua_belas_bulan():
    h = llm.hitung([_keg(mulai="2024-02-01")],
                   _aset("k1", "2024-01-01", n=4), KINI)
    assert h["tahun"] == 2024
    assert not any(b["belum_berjalan"] for b in h["baris"])


# ── 4. Data janggal digencet DAN dihitung ───────────────────────────────

def test_isi_yang_melampaui_rumahnya_digencet_dan_DIHITUNG():
    # Diperiksa Februari, diperoleh Mei — kekeliruan data, bukan keadaan yang
    # mungkin. Grafik yang menggencet diam-diam menyembunyikan justru baris
    # yang perlu dibetulkan.
    h = llm.hitung([_keg()],
                   _aset("k1", "2026-05-01", "Ditemukan", "2026-02-01", n=3),
                   KINI)
    assert h["janggal"] > 0
    for b in h["baris"]:
        assert b["ditemukan"] + b["periksa_lain"] <= b["tercatat"]


# ── 5. Tahun yang ditampilkan ───────────────────────────────────────────

def test_satu_salah_ketik_tahun_tak_menyandera_grafiknya():
    # "2062" alih-alih "2026" akan memindahkan seluruh linimasa ke tahun itu
    # dan menyisakan grafik kosong.
    h = llm.hitung([_keg(1, "2026-03-01"), _keg(2, "2062-01-01")],
                   _aset("k1", "2026-04-01", n=5), KINI)
    assert h["tahun"] == 2026
    assert h["ada"]


def test_tanpa_kegiatan_memakai_tahun_berjalan():
    assert llm.hitung([], [], KINI)["tahun"] == 2026


def test_grafik_kosong_ditandai_tidak_ada():
    assert llm.hitung([_keg()], [], KINI)["ada"] is False


# ── Bahan grafik kedua: irisan per kegiatan ─────────────────────────────

def test_irisan_per_kegiatan_memakai_rumah_yang_SAMA():
    h = llm.hitung([_keg(1), _keg(2, "2026-04-01")],
                   _aset("k1", "2026-02-01", n=3) + _aset("k2", "2026-05-01", n=2),
                   KINI)
    baris, legenda, ada = llm.iris_per_kegiatan(h, {"k1": "Keg A", "k2": "Keg B"})
    assert ada
    for i, b in enumerate(baris):
        assert b["tercatat"] == h["baris"][i]["tercatat"]
        assert b["h_tercatat"] == h["baris"][i]["h_tercatat"]
    assert sum(s["n"] for s in baris[8]["segmen"]) == baris[8]["tercatat"]
    assert {l["nama"] for l in legenda} == {"Keg A", "Keg B"}


def test_irisan_tak_digambar_bila_kegiatannya_hanya_satu():
    # Irisannya identik dengan rumahnya sendiri — grafik yang tak menambahkan
    # apa pun, hanya satu halaman lagi untuk dilewati.
    h = llm.hitung([_keg()], _aset("k1", "2026-02-01", n=3), KINI)
    assert llm.iris_per_kegiatan(h, {"k1": "Keg A"})[2] is False


def test_kegiatan_melebihi_jatah_warna_digabung_dan_DISEBUT_jumlahnya():
    # Dua puluh irisan berwarna dalam satu batang tak dapat dibedakan mata
    # siapa pun; rinciannya tetap ada di bagian Capaian per Kegiatan.
    keg = [_keg(i, "2026-02-01") for i in range(1, 12)]
    aset = []
    for i in range(1, 12):
        aset += _aset(f"k{i}", "2026-02-01", n=12 - i)
    h = llm.hitung(keg, aset, KINI)
    _, legenda, _ = llm.iris_per_kegiatan(h, {f"k{i}": f"Keg {i}" for i in range(1, 12)})
    assert len(legenda) == len(llm.WARNA_KEGIATAN) + 1
    assert "kegiatan lainnya" in legenda[-1]["nama"]
