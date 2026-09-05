"""Penyusun tata letak laporan gabungan — mengukur, bukan menebak.

Permintaan pemilik: *"perkategori dan lokasi juga buat jangan dibatasi biarkan
saja mengalir dan buat smart mengatur dan berbagi posisi dengan bagian lainnya
hingga benar benar 1 kertas penuh tidak bisa menampung tataletak yang ada lagi,
baru pindah lanjut kekertas berikutnya."*

Empat sifat dijaga di sini:

1. **Tak ada baris yang hilang.** Memangkas `most_common(10)` membuang data
   tanpa satu pun tanda; memecah tidak.
2. **Kertas diisi sampai benar-benar penuh** sebelum kertas berikutnya dibuka.
3. **Kedua kolom terisi rata** — itulah "berbagi posisi".
4. **Tak ada yang meluber**: tinggi terpakai tiap kolom tak pernah melebihi
   tinggi kolomnya.
"""
import pytest

import laporan_tataletak as tl


def _panel(judul, n, mulai=0):
    return tl.panel_batang(
        judul, [{"name": f"{judul}-{i}", "count": i, "pct": 1, "val_fmt": "0"}
                for i in range(mulai, mulai + n)], "#000")


def _semua_baris(halaman):
    keluar = []
    for h in halaman:
        for sisi in ("kiri", "kanan"):
            for p in h[sisi]:
                keluar += [b["name"] for b in p["baris"]]
    return keluar


def _tinggi_kolom(halaman_ke, h):
    """(tinggi_kiri, tinggi_kanan) termasuk jarak antar panel."""
    out = []
    for sisi in ("kiri", "kanan"):
        panel = h[sisi]
        t = sum(p["tinggi"] for p in panel)
        t += tl.JARAK_PANEL * max(0, len(panel) - 1)
        out.append(t)
    return tuple(out)


# ── 1. Tak ada baris yang hilang ────────────────────────────────────────

def test_TIDAK_ADA_baris_yang_hilang_berapa_pun_banyaknya():
    """Inti permintaannya: jangan dibatasi. Pemangkasan `most_common(10)`
    membuang data tanpa satu pun tanda — satker dengan 40 lokasi hanya
    menampilkan 10, dan tak ada yang memberi tahu 30 sisanya ada."""
    for n in (1, 9, 10, 11, 40, 137):
        panel = [_panel("Kategori", n), _panel("Lokasi", n)]
        halaman = tl.susun(panel)
        nama = _semua_baris(halaman)
        assert len(nama) == 2 * n, f"n={n}: {len(nama)} dari {2 * n} baris"
        assert len(set(nama)) == len(nama), f"n={n}: ada baris terduplikasi"


def test_panel_panjang_DIPECAH_dan_lanjutannya_menyatakan_diri():
    """Potongan kedua tanpa tanda terbaca sebagai daftar baru yang kebetulan
    berjudul sama, dan pembacanya mengira daftarnya sudah habis di potongan
    pertama."""
    halaman = tl.susun([_panel("Lokasi", 120)])
    potongan = [p for h in halaman for sisi in ("kiri", "kanan") for p in h[sisi]]
    assert len(potongan) > 1, "panel 120 baris tak dipecah"
    assert potongan[0]["lanjutan"] is False
    assert all(p["lanjutan"] for p in potongan[1:]), "lanjutan tak bertanda"
    assert all(p["judul"] == "Lokasi" for p in potongan)


def test_panel_pendek_TIDAK_dipecah():
    """Panel yang muat utuh tak boleh dipecah — potongan tanpa sebab hanya
    menambah judul berulang."""
    halaman = tl.susun([_panel("Kondisi", 3), _panel("Status", 5)])
    potongan = [p for h in halaman for sisi in ("kiri", "kanan") for p in h[sisi]]
    assert len(potongan) == 2
    assert all(p["lanjutan"] is False for p in potongan)


# ── 2. Kertas diisi sampai benar-benar penuh ────────────────────────────

def test_tak_ada_kolom_yang_MELUBER():
    """Lembarnya `overflow: hidden` — yang meluber hilang tanpa satu pun tanda
    di layar. Ini pemeriksaan yang paling menentukan di berkas ini."""
    for n in (1, 7, 23, 60, 200):
        panel = [_panel(f"P{i}", n) for i in range(6)]
        halaman = tl.susun(panel)
        for ke, h in enumerate(halaman):
            tersedia = tl.TINGGI_KOLOM - (tl.TINGGI_JUDUL_AWAL if ke == 0
                                          else tl.TINGGI_JUDUL_LANJUT)
            kiri, kanan = _tinggi_kolom(ke, h)
            assert kiri <= tersedia, f"n={n} hal={ke} kiri {kiri} > {tersedia}"
            assert kanan <= tersedia, f"n={n} hal={ke} kanan {kanan} > {tersedia}"


def test_halaman_baru_hanya_dibuka_setelah_yang_lama_PENUH():
    """Kertas berikutnya yang dibuka untuk tiga baris, sementara separuh kertas
    sebelumnya kosong, adalah persis pemborosan yang dikeluhkan."""
    panel = [_panel(f"P{i}", 12) for i in range(9)]
    halaman = tl.susun(panel)
    assert len(halaman) >= 2, "data ujinya terlalu kecil"
    for ke, h in enumerate(halaman[:-1]):
        tersedia = tl.TINGGI_KOLOM - (tl.TINGGI_JUDUL_AWAL if ke == 0
                                      else tl.TINGGI_JUDUL_LANJUT)
        kiri, kanan = _tinggi_kolom(ke, h)
        # Halaman yang BUKAN terakhir harus terisi rapat: sisa ruang di kolom
        # terpendek tak boleh cukup untuk panel berikutnya yang tersedia.
        sisa = tersedia - min(kiri, kanan)
        # Ambangnya `MIN_BARIS_PECAH`, bukan satu baris: potongan satu-dua
        # baris di ujung kolom membuang lebih banyak ruang daripada yang
        # dihematnya (judul panelnya sendiri 55px) dan terbaca sebagai
        # kekeliruan cetak. Sisa yang lebih kecil dari itu memang tak
        # terpakai — dan itu keputusan, bukan kelalaian.
        assert sisa < tl.tinggi_panel(tl.MIN_BARIS_PECAH) + tl.JARAK_PANEL, (
            f"hal={ke} menyisakan {sisa}px — masih muat potongan yang layak")


def test_SISA_RUANG_kolom_diisi_sebelum_pindah_kolom(dbf=None):
    """Inti "hingga benar benar 1 kertas penuh".

    Panel pendek lalu panel panjang: sisa kolom kiri masih muat puluhan baris,
    jadi panel panjang harus DIPECAH di situ — bukan pindah kolom dan
    meninggalkan setengah kolom kosong.

    Uji sebelumnya memakai panel SERAGAM, sehingga jalur pemecahan-di-tempat
    tak pernah terpakai dan mutasi yang mematikannya lolos begitu saja."""
    halaman = tl.susun([_panel("Pendek", 20), _panel("Panjang", 60)])
    kiri = halaman[0]["kiri"]
    assert [p["judul"] for p in kiri] == ["Pendek", "Panjang"], kiri
    assert kiri[1]["lanjutan"] is False, "kepala panjangnya bukan di kiri"
    assert len(kiri[1]["baris"]) >= tl.MIN_BARIS_PECAH

    tersedia = tl.TINGGI_KOLOM - tl.TINGGI_JUDUL_AWAL
    terpakai = sum(p["tinggi"] for p in kiri) + tl.JARAK_PANEL * (len(kiri) - 1)
    sisa = tersedia - terpakai
    assert sisa < tl.tinggi_panel(tl.MIN_BARIS_PECAH), (
        f"kolom kiri menyisakan {sisa}px yang masih bisa diisi")


def test_pecahan_EKOR_terlalu_pendek_tak_dibuat():
    """Potongan satu-dua baris di ujung kolom membuang lebih banyak ruang
    (judul panelnya sendiri 55px) daripada yang dihematnya, dan terbaca sebagai
    kekeliruan cetak."""
    for n_ekor in range(1, tl.MIN_BARIS_PECAH):
        tersedia = tl.TINGGI_KOLOM - tl.TINGGI_JUDUL_AWAL
        # Panel pertama menyisakan ruang untuk (n_total - n_ekor) baris.
        n_total = 40
        tinggi_kepala = tl.tinggi_panel(n_total - n_ekor)
        n_pendek = tl.baris_muat(tersedia - tinggi_kepala - tl.JARAK_PANEL)
        if n_pendek < 1:
            continue
        halaman = tl.susun([_panel("Pendek", n_pendek), _panel("Panjang", n_total)])
        for h in halaman:
            for sisi in ("kiri", "kanan"):
                for p in h[sisi]:
                    assert len(p["baris"]) == 0 or len(p["baris"]) >= tl.MIN_BARIS_PECAH \
                        or len(p["baris"]) == n_pendek, (
                        f"potongan {len(p['baris'])} baris terlalu pendek")


def test_satu_panel_raksasa_tak_membuat_perulangan_tak_berujung():
    """Panel yang lebih tinggi dari kolomnya harus tetap ditempatkan; tanpa
    cabang halaman-kosong, penyusunnya membuka halaman baru selamanya."""
    besar = tl.panel_batang("Raksasa", [{"name": str(i)} for i in range(500)], "#000")
    halaman = tl.susun([besar], tinggi_kolom=200, judul_awal=0, judul_lanjut=0)
    assert len(_semua_baris(halaman)) == 500
    assert len(halaman) < 500, "tiap baris membuka halamannya sendiri"


# ── 3. Kedua kolom terisi rata ──────────────────────────────────────────

def test_URUTAN_BACA_terjaga_kiri_penuh_dulu_baru_kanan():
    """Halaman dua kolom dibaca kiri dari atas ke bawah, lalu kanan.

    Percobaan pertama modul ini menaruh potongan di kolom yang sedang
    TERPENDEK. Tingginya jadi rata, tetapi urutan bacanya rusak: pada data
    sungguhan "Per Lokasi (lanjutan)" berakhir di kolom kiri sementara 42
    baris pertamanya ada di kolom kanan — lanjutan yang dibaca lebih dulu
    daripada yang dilanjutkannya."""
    halaman = tl.susun([_panel("Tinggi", 30), _panel("A", 2),
                        _panel("B", 2), _panel("C", 2)])
    h = halaman[0]
    urut = [p["judul"] for p in h["kiri"]] + [p["judul"] for p in h["kanan"]]
    assert urut == ["Tinggi", "A", "B", "C"], (h["kiri"], h["kanan"])
    assert h["kiri"][0]["judul"] == "Tinggi", "kolom kiri tak diisi lebih dulu"


def test_potongan_dan_lanjutannya_TIDAK_terbalik_urutannya():
    """Kepala harus selalu terbaca sebelum ekornya, di kolom mana pun ia
    jatuh."""
    halaman = tl.susun([_panel("Pendek", 3), _panel("Panjang", 90)])
    urut = []
    for h in halaman:
        for sisi in ("kiri", "kanan"):
            urut += [(p["judul"], p["lanjutan"], p["baris"][0]["name"])
                     for p in h[sisi] if p["baris"]]
    panjang = [u for u in urut if u[0] == "Panjang"]
    assert panjang[0][1] is False, "lanjutan terbaca lebih dulu"
    nomor = [int(u[2].split("-")[1]) for u in panjang]
    assert nomor == sorted(nomor), f"potongan tak berurutan: {nomor}"


def test_kedua_kolom_terisi_HAMPIR_SAMA_tinggi():
    """Ukuran "berbagi posisi": pada panel seragam, selisih tinggi kedua kolom
    tak boleh lebih dari satu panel."""
    panel = [_panel(f"P{i}", 8) for i in range(8)]
    h = tl.susun(panel)[0]
    kiri, kanan = _tinggi_kolom(0, h)
    assert abs(kiri - kanan) <= tl.tinggi_panel(8) + tl.JARAK_PANEL, (kiri, kanan)


# ── 4. Sudut-sudut ──────────────────────────────────────────────────────

def test_tanpa_panel_tak_ada_halaman_kosong():
    """Halaman kosong yang tetap tercetak membuat pembacanya mengira ada isi
    yang gagal dimuat."""
    assert tl.susun([]) == []


def test_panel_TANPA_BARIS_tetap_muncul():
    """Panel kosong yang dibuang diam-diam membuat pembacanya mengira dimensi
    itu tak ada; yang benar adalah datanya belum terisi."""
    halaman = tl.susun([tl.panel_batang("Eselon II", [], "#000")])
    potongan = [p for h in halaman for sisi in ("kiri", "kanan") for p in h[sisi]]
    assert [p["judul"] for p in potongan] == ["Eselon II"]
    assert potongan[0]["baris"] == []


def test_tinggi_panel_dan_baris_muat_saling_membalik():
    """`baris_muat` adalah kebalikan `tinggi_panel`; kalau keduanya bergeser,
    penyusunnya akan yakin sesuatu muat padahal tidak."""
    for n in range(0, 60):
        assert tl.baris_muat(tl.tinggi_panel(n)) >= n, n


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_panel_sangat_pendek_tak_memicu_pecahan_ekor(n):
    halaman = tl.susun([_panel("Kecil", n)])
    potongan = [p for h in halaman for sisi in ("kiri", "kanan") for p in h[sisi]]
    assert len(potongan) == 1


# ── Jatah baris tabel struktur organisasi ───────────────────────────────
#
# Tabel struktur duduk di bawah kartu kegiatan pada halaman TERAKHIR bagian
# itu. Jatahnya dulu tetapan enam, dan tetapan salah di kedua arah: pada
# halaman berisi delapan kegiatan pun masih muat belasan baris, sementara
# satker dengan lebih dari enam unit kehilangan sisanya tanpa satu pun tanda.

def test_makin_banyak_kartu_makin_sedikit_baris_yang_muat():
    jatah = [tl.baris_struktur_muat(n) for n in (2, 4, 6, 8)]
    assert jatah == sorted(jatah, reverse=True), jatah
    assert len(set(jatah)) > 1, "jatahnya tak bergantung isi halaman"


def test_halaman_penuh_delapan_kegiatan_tetap_muat_lebih_dari_enam():
    # Inilah yang membuat tetapan enam keliru bahkan pada kasus tersempitnya.
    assert tl.baris_struktur_muat(8) > 6


def test_halaman_lapang_memberi_jatah_jauh_lebih_besar():
    assert tl.baris_struktur_muat(1) >= 2 * tl.baris_struktur_muat(8)


def test_dua_kartu_sebaris_jadi_satu_baris_kartu():
    # `.keg-grid` dua kolom: satu dan dua kegiatan memakai tinggi yang sama.
    assert tl.baris_struktur_muat(1) == tl.baris_struktur_muat(2)
    assert tl.baris_struktur_muat(3) == tl.baris_struktur_muat(4)


def test_halaman_pertama_tak_pernah_lebih_lapang_daripada_lanjutannya():
    # Halaman pertama membawa keterangan bagian, jadi ia memuat lebih sedikit.
    for n in (1, 4, 8):
        assert (tl.baris_struktur_muat(n, lanjutan=False)
                <= tl.baris_struktur_muat(n, lanjutan=True))


def test_jatah_tak_pernah_negatif():
    # Halaman yang sudah penuh sesak tak boleh menghasilkan potongan terbalik.
    assert tl.baris_struktur_muat(999) == 0
    assert tl.baris_struktur_muat(0) > 0
    assert tl.baris_struktur_muat(None) > 0
