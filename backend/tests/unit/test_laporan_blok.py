"""Penataan blok halaman "Analisis Lanjutan, Tim & Cakupan Data".

Permintaan pemilik: *"jadikan smart semua dalam mengatur posisinya
masing-masing menyesuaikan bagaimana caranya berbagi dan mengalah untuk
menampilkan informasi sebaik mungkin tanpa harus melanjutkan ke halaman kedua
dengan memaksimalkan A4 yang ada tanpa harus menggunakan '…'."*

Modul ini tak pernah melempar galat. Kesalahannya berupa blok yang hilang dari
laporan, lembar yang dibuka tanpa perlu, atau daftar tim yang ekornya terpotong
senyap — karena itu yang diuji di sini SIFATNYA: tiap blok muncul tepat sekali,
tiap baris tim terbawa, dan lembar baru hanya lahir bila memang tak muat.
"""

import laporan_blok as lbk
import laporan_kolom as lkl


def _blok(id_blok, tinggi, separuh=False):
    return lbk.blok(id_blok, tinggi, separuh=separuh)


def _semua_id(rencana):
    return [x["id"] for hal in rencana["halaman"] for b in hal for x in b["blok"]]


# ── 1. Berbagi baris: dua blok pendek berdampingan ──────────────────────

def test_dua_blok_SEPARUH_berurutan_berbagi_satu_baris():
    r = lbk.rencana_blok([_blok("a", 100, True), _blok("b", 60, True)],
                         sehalaman=900)
    assert len(r["halaman"]) == 1
    baris = r["halaman"][0]
    assert len(baris) == 1, "keduanya seharusnya satu baris"
    assert [x["id"] for x in baris[0]["blok"]] == ["a", "b"]


def test_tinggi_baris_diambil_yang_TERTINGGI_bukan_dijumlah():
    """Blok yang pendek mengisi sisa ruangnya sendiri di samping pasangannya.

    Menjumlahkan keduanya membuat penata halaman mengira barisnya dua kali
    lebih tinggi daripada sebenarnya, dan lembar baru dibuka padahal kertasnya
    masih separuh kosong.
    """
    r = lbk.rencana_blok([_blok("a", 100, True), _blok("b", 60, True)],
                         sehalaman=900)
    assert r["halaman"][0][0]["tinggi"] == 100


def test_blok_PENUH_tak_pernah_dipaksa_berbagi():
    # Tabel lima kolom yang disempitkan jadi separuh lebar tak lagi terbaca.
    r = lbk.rencana_blok([_blok("a", 100, True), _blok("lebar", 100),
                          _blok("b", 100, True)], sehalaman=900)
    baris = r["halaman"][0]
    assert [[x["id"] for x in b["blok"]] for b in baris] == [["a"], ["lebar"], ["b"]]


def test_blok_separuh_yang_TAK_punya_pasangan_berdiri_sendiri():
    r = lbk.rencana_blok([_blok("a", 100, True)], sehalaman=900)
    assert [[x["id"] for x in b["blok"]] for b in r["halaman"][0]] == [["a"]]


def test_urutan_blok_TIDAK_ditukar_demi_memadatkan():
    """Menukar urutan blok agar lebih padat membuat urutan bacanya
    berpindah-pindah tanpa alasan yang terlihat pembaca."""
    r = lbk.rencana_blok([_blok("a", 100, True), _blok("lebar", 100),
                          _blok("b", 100, True), _blok("c", 100, True)],
                         sehalaman=900)
    assert _semua_id(r) == ["a", "lebar", "b", "c"]


# ── 2. Lembar baru hanya bila memang tak muat ───────────────────────────

def test_muat_semua_maka_SATU_lembar():
    blok = [_blok(f"b{i}", 100) for i in range(8)]
    r = lbk.rencana_blok(blok, sehalaman=900)
    assert len(r["halaman"]) == 1


def test_jarak_antar_blok_TIDAK_dihitung_pada_blok_pertama_lembar():
    """Di awal lembar, jarak itu tak memisahkan apa pun.

    Menghitungnya membuat tiap lembar kehilangan 14px tanpa sebab, dan pada
    daftar panjang kehilangan itu berbunga menjadi satu lembar tambahan.
    """
    # Tiga blok 300px + dua jarak 14 = 928 <= 928; kalau jarak pertama ikut
    # dihitung, jumlahnya 942 dan lembar kedua lahir tanpa perlu.
    tinggi = 300.0
    jatah = 3 * tinggi + 2 * lbk.JARAK_BLOK
    r = lbk.rencana_blok([_blok(f"b{i}", tinggi) for i in range(3)],
                         sehalaman=jatah)
    assert len(r["halaman"]) == 1


def test_lembar_kedua_lahir_saat_baris_berikutnya_tak_muat():
    r = lbk.rencana_blok([_blok("a", 500), _blok("b", 500)], sehalaman=900)
    assert [[x["id"] for b in hal for x in b["blok"]] for hal in r["halaman"]] \
        == [["a"], ["b"]]


def test_tiap_blok_muncul_TEPAT_SEKALI():
    """Blok yang terlewat tak menimbulkan galat apa pun — ia hanya lenyap."""
    for n in (1, 2, 3, 7, 8, 9, 25):
        blok = [_blok(f"b{i}", 137.0, separuh=(i % 3 == 0)) for i in range(n)]
        r = lbk.rencana_blok(blok, sehalaman=900)
        assert _semua_id(r) == [f"b{i}" for i in range(n)], n


def test_blok_yang_SENDIRIAN_pun_tak_muat_tetap_tergambar():
    # Tanpa ini perulangannya tak pernah maju dan bloknya hilang dari laporan.
    r = lbk.rencana_blok([_blok("raksasa", 5000)], sehalaman=900)
    assert _semua_id(r) == ["raksasa"]


def test_daftar_kosong_tak_membuka_lembar():
    assert lbk.rencana_blok([])["halaman"] == []
    assert lbk.rencana_blok(None)["halaman"] == []


# ── 3. Tabel tim boleh dipecah antar-lembar ─────────────────────────────

def _blok_tim(n_inti, n_pembantu):
    return lbk.blok_tabel_tim("tim", [
        ("Tim Inti", "tim_inti", n_inti),
        ("Tim Pembantu", "tim_pembantu", n_pembantu)])


def _baris_terbawa(rencana, kunci):
    """Himpunan indeks baris `kunci` yang benar-benar tergambar."""
    keluar = []
    for hal in rencana["halaman"]:
        for b in hal:
            for x in b["blok"]:
                for t in x.get("potong") or []:
                    if t["kunci"] == kunci:
                        keluar += list(range(t["awal"], t["akhir"]))
    return keluar


def test_daftar_tim_yang_LEBIH_PANJANG_dari_selembar_terbawa_seluruhnya():
    """Tanpa pemecahan, blok setinggi dua lembar ditempatkan utuh pada satu
    lembar dan ekornya terpotong senyap oleh `overflow: hidden`. Diuji pada
    data sungguhan: 60 anggota, delapan di antaranya hilang dari cetakan."""
    r = lbk.rencana_blok([_blok_tim(4, 200)], sehalaman=900)
    assert len(r["halaman"]) > 1, "blok setinggi itu mustahil muat selembar"
    assert _baris_terbawa(r, "tim_inti") == list(range(4))
    assert _baris_terbawa(r, "tim_pembantu") == list(range(200))


def test_pecahan_tabel_TIDAK_menggandakan_baris():
    r = lbk.rencana_blok([_blok_tim(3, 120)], sehalaman=900)
    for kunci, n in (("tim_inti", 3), ("tim_pembantu", 120)):
        terbawa = _baris_terbawa(r, kunci)
        assert terbawa == sorted(terbawa), f"{kunci} tak berurutan"
        assert len(terbawa) == len(set(terbawa)) == n, kunci


def test_sisa_ruang_lembar_DIPAKAI_sebagian_tabel():
    """Itulah "mengalah" yang diminta: bagian yang muat tetap tercetak di
    lembar ini, sisanya menyambung — bukan seluruh tabel pindah dan
    meninggalkan setengah kertas kosong."""
    r = lbk.rencana_blok([_blok("atas", 500), _blok_tim(4, 60)], sehalaman=900)
    lembar1 = [x for b in r["halaman"][0] for x in b["blok"]]
    assert [x["id"] for x in lembar1] == ["atas", "tim"]
    dibawa = sum(t["akhir"] - t["awal"] for t in lembar1[1]["potong"])
    assert dibawa > 0, "sisa ruang lembar pertama dibiarkan kosong"


def test_potongan_yang_TERLALU_PENDEK_tak_dibuat():
    """Sisa yang hanya memuat satu-dua baris lebih baik dibiarkan kosong:
    potongan sependek itu menambah judul dan baris kepala untuk memindahkan
    dua baris data."""
    tinggi_kepala = (lbk.SISIPAN_TIM + lbk.TINGGI_JUDUL_TIM
                     + lbk.TINGGI_SUBJUDUL_TIM + lbk.TINGGI_KEPALA_TABEL_TIM
                     + lbk.JARAK_ANTAR_TABEL_TIM)
    # Sisa hanya cukup untuk dua baris — di bawah MINIMUM_BARIS_PECAH.
    sisa = tinggi_kepala + 2 * lbk.tinggi_baris_tim(1)
    jatah = 500.0
    r = lbk.rencana_blok([_blok("atas", jatah - sisa - lbk.JARAK_BLOK),
                          _blok_tim(0, 40)], sehalaman=jatah)
    assert [x["id"] for b in r["halaman"][0] for x in b["blok"]] == ["atas"]


def test_blok_berdampingan_TIDAK_dipecah():
    # Memotong salah satu dari dua blok sebaris membuat pasangannya
    # menggantung sendirian tanpa alasan yang terlihat.
    r = lbk.rencana_blok([_blok("atas", 700),
                          _blok_tim(4, 40), _blok("x", 100, True)],
                         sehalaman=900)
    hal1 = [x["id"] for b in r["halaman"][0] for x in b["blok"]]
    assert hal1 == ["atas"] or "tim" in hal1


# ── 4. Sisa ruang: bahan untuk memanjangkan daftar yang bisa memanjang ──

def test_sisa_ruang_menghitung_jarak_antar_blok():
    r = lbk.rencana_blok([_blok("a", 100), _blok("b", 100)], sehalaman=900)
    assert lbk.sisa_ruang(r, 0, sehalaman=900) == 900 - 200 - lbk.JARAK_BLOK


def test_sisa_ruang_lembar_yang_tak_ada_bernilai_nol():
    r = lbk.rencana_blok([_blok("a", 100)], sehalaman=900)
    assert lbk.sisa_ruang(r, 5, sehalaman=900) == 0.0
    assert lbk.sisa_ruang(None, 0) == 0.0


def test_jatah_bawaan_SAMA_dengan_yang_dipakai_tabel_distribusi():
    """Dua penata halaman yang berbeda pendapat soal apa artinya "muat" akan
    menghasilkan dua nomor halaman yang berbeda pada kop yang sama."""
    r = lbk.rencana_blok([_blok("a", 1.0)])
    sisa = lbk.sisa_ruang(r, 0)
    assert abs(sisa - (lkl.TINGGI_ISI_SEHALAMAN - lkl.CADANGAN_TATA_LETAK - 1.0)) < 1e-9


# ── 5. Tinggi blok tumbuh selaras isinya ────────────────────────────────

def test_tinggi_daftar_TUMBUH_selaras_cacah_barisnya():
    assert lbk.tinggi_daftar_bar([1] * 4) > lbk.tinggi_daftar_bar([1] * 2)
    assert lbk.tinggi_kondisi([1] * 20) > lbk.tinggi_kondisi([1] * 8)


def test_label_yang_MEMBUNGKUS_membuat_barisnya_lebih_tinggi():
    # Label dua baris lebih tinggi daripada palangnya; mengabaikannya membuat
    # taksiran meleset justru pada blok berlabel panjang.
    assert lbk.tinggi_baris_hbar(2) > lbk.tinggi_baris_hbar(1)
    assert lbk.tinggi_baris_sbar(3) > lbk.tinggi_baris_sbar(1)
    # …tetapi label sebaris tak pernah lebih pendek daripada palangnya.
    assert lbk.tinggi_baris_hbar(1) == lbk.TINGGI_TRACK_HBAR + lbk.JARAK_BARIS_HBAR


def test_tabel_tim_KOSONG_tak_ikut_dihitung():
    # Tabel yang tak punya baris memang tak tergambar; menghitungnya membuat
    # bloknya ditaksir lebih tinggi dan lembar dibuka tanpa perlu.
    assert lbk.tinggi_tim_tabel(4, 0) == lbk.tinggi_tim_tabel(4)
    assert lbk.tinggi_tim_tabel() < lbk.tinggi_tim_tabel(1)
