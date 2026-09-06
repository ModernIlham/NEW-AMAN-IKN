"""Pemaketan halaman & pemilihan kolom tabel distribusi Laporan Eksekutif.

Permintaan pemilik: *"pastikan benar benar tidak ada batas terbuang sia sia di
ukuran A4 hingga mencapai footer terlebih dahulu di semua distribusi, agar
dibuat smart juga apabila melebihi sudah maka berganti 2 kolom dengan Barchart
yang menghilang agar cukup, baru lanjutkan ke halaman kedua apabila memang
tidak cukup lagi."*

Modul ini tak pernah melempar galat: kesalahannya berupa baris yang hilang dari
laporan, atau halaman yang meluber lalu dipotong diam-diam oleh
`overflow: hidden`. Karena itu uji di bawah menagih SIFAT-nya — tiap baris
muncul tepat sekali, tiap halaman tak melewati kapasitas — bukan sekadar
memanggil fungsinya.
"""

import laporan_kolom as lkl


def _baris(n, depth=0, nama="X"):
    return [{"name": f"{nama}{i}", "depth": depth} for i in range(n)]


def _satu(b, kolom):
    return 1


# ── 1. Urutan keputusan: satu kolom → dua kolom → halaman baru ──────────

def test_muat_satu_kolom_maka_SATU_kolom_berbatang():
    r = lkl.rencana_kolom(_baris(10), _satu, sehalaman=38)
    assert r["kolom"] == 1
    assert r["batang"] is True, "batang hanya boleh hilang bila memang perlu"
    assert r["halaman"] == [{"awal": 0, "pisah": 10, "akhir": 10}]


def test_tepat_penuh_masih_SATU_kolom():
    # Batasnya inklusif: 38 baris pada kapasitas 38 masih muat. Kalau
    # tergelincir menjadi eksklusif, daftar yang pas memenuhi kertas malah
    # pecah jadi dua kolom sempit — ruang terbuang persis yang diminta hilang.
    r = lkl.rencana_kolom(_baris(38), _satu, sehalaman=38)
    assert r["kolom"] == 1 and len(r["halaman"]) == 1


def test_lewat_sebaris_pun_pindah_DUA_kolom_tanpa_batang():
    r = lkl.rencana_kolom(_baris(39), _satu, sehalaman=38)
    assert r["kolom"] == 2
    assert r["batang"] is False, "dua kolom sempit tak menyisakan tempat batang"
    assert len(r["halaman"]) == 1, "76 jatah untuk 39 baris — cukup satu lembar"


def test_dua_kolom_pun_tak_cukup_maka_HALAMAN_berikutnya():
    r = lkl.rencana_kolom(_baris(200), _satu, sehalaman=38)
    assert r["kolom"] == 2
    assert len(r["halaman"]) == 3, "200 baris / 76 per lembar"


def test_daftar_kosong_tak_membuka_halaman():
    r = lkl.rencana_kolom([], _satu)
    assert r["halaman"] == []


# ── 2. Tak satu baris pun boleh hilang atau tergandakan ─────────────────

def _terpakai(rencana, n):
    """Indeks baris yang benar-benar tergambar, menurut rencananya."""
    urut = []
    for h in rencana["halaman"]:
        urut += list(range(h["awal"], h["pisah"]))
        urut += list(range(h["pisah"], h["akhir"]))
    return urut


def test_tiap_baris_muncul_TEPAT_SEKALI_dan_berurutan():
    """Baris yang terlewat tak menimbulkan galat apa pun — ia hanya lenyap.

    Diuji pada banyak panjang sekaligus, termasuk panjang tepat di batas
    kolom dan halaman: di sanalah kekeliruan satu-lebih/satu-kurang bersembunyi.
    """
    for n in (1, 2, 37, 38, 39, 75, 76, 77, 151, 152, 153, 200):
        r = lkl.rencana_kolom(_baris(n), _satu, sehalaman=38)
        assert _terpakai(r, n) == list(range(n)), f"n={n}"


def test_baris_yang_SENDIRIAN_pun_melebihi_kapasitas_tetap_tergambar():
    # Satu nama yang teramat panjang tak boleh membuat pemaketannya berputar
    # selamanya — dan tak boleh pula dibuang. Ia mengambil satu kolom sendiri.
    tinggi = {0: 99}
    r = lkl.rencana_kolom(_baris(3), lambda b, k: tinggi.get(int(b["name"][1:]), 1),
                          sehalaman=38)
    assert _terpakai(r, 3) == [0, 1, 2]


def test_kolom_KIRI_diisi_penuh_dulu_bukan_dibelah_rata():
    # Dibelah rata, daftar 40 baris menjadi dua kolom sama-sama 20 baris dengan
    # separuh kertas kosong di bawahnya.
    r = lkl.rencana_kolom(_baris(40), _satu, sehalaman=38)
    h = r["halaman"][0]
    assert h["pisah"] - h["awal"] == 38, "kolom kiri harus penuh dulu"
    assert h["akhir"] - h["pisah"] == 2


def test_tak_ada_halaman_yang_melewati_kapasitas_kolomnya():
    tinggi = [1, 3, 2, 1, 1, 4, 2, 1, 1, 1] * 12
    r = lkl.rencana_kolom(_baris(len(tinggi)),
                          lambda b, k: tinggi[int(b["name"][1:])], sehalaman=20)
    for h in r["halaman"]:
        for a, z in ((h["awal"], h["pisah"]), (h["pisah"], h["akhir"])):
            isi = sum(tinggi[a:z])
            # Kolom berisi lebih dari satu baris tak boleh melewati kapasitas;
            # kolom berisi satu baris raksasa memang boleh (lihat uji di atas).
            assert isi <= 20 or z - a == 1, (a, z, isi)


# ── 3. Tinggi baris ikut berubah bersama jumlah kolomnya ────────────────

def test_tinggi_dihitung_ULANG_untuk_tata_letak_dua_kolom():
    """Kolom dua kali lebih sempit membungkus dua kali lebih sering.

    Menghitung tinggi dua kolom dengan angka satu kolom adalah cara paling
    langsung membuat halamannya meluber: taksirannya selalu terlalu kecil,
    persis pada baris yang paling banyak jumlahnya.
    """
    dilihat = []

    def tinggi(b, kolom):
        dilihat.append(kolom)
        return 1 if kolom == 1 else 2

    r = lkl.rencana_kolom(_baris(50), tinggi, sehalaman=38)
    assert 2 in dilihat, "tata letak dua kolom tak pernah ditaksir ulang"
    # 50 baris x 2 baris teks = 100; kapasitas dua kolom 76 → dua lembar.
    assert len(r["halaman"]) == 2


def test_jorokan_MEMAKAN_lebar_kolom_nama():
    # Baris jenjang terdalam paling banyak jumlahnya sekaligus paling dalam
    # jorokannya. Mengabaikan jorokan membuat taksiran meleset justru di sana.
    assert lkl.lebar_setelah_jorok(226.0, 0) == 226.0
    assert lkl.lebar_setelah_jorok(226.0, 4) == 226.0 - 4 * lkl.PX_JOROKAN
    assert lkl.lebar_setelah_jorok(226.0, 4) < lkl.lebar_setelah_jorok(226.0, 1)


def test_jorokan_dihitung_dalam_PIKSEL_bukan_karakter():
    """Jorokan 11px sama besarnya di kolom lebar dan kolom sempit, tetapi
    memakan BAGIAN yang jauh lebih besar pada yang sempit. Menguranginya
    dalam satuan karakter membuat tiap tingkat berharga sama di kedua kolom,
    dan kolom dua lajur lalu dinilai terlalu lapang justru pada baris
    terdalam — baris yang paling banyak jumlahnya."""
    lebar = 526.0 - lkl.lebar_setelah_jorok(526.0, 1)
    sempit = 117.5 - lkl.lebar_setelah_jorok(117.5, 1)
    assert lebar == sempit == lkl.PX_JOROKAN
    assert sempit / 117.5 > 3 * lebar / 526.0


def test_kolom_nama_tak_pernah_menyusut_sampai_tak_masuk_akal():
    assert lkl.lebar_setelah_jorok(80.0, 50) == lkl.PX_MINIMUM
    assert lkl.lebar_setelah_jorok(226.0, None) == 226.0
    assert lkl.lebar_setelah_jorok(226.0, "bukan angka") == 226.0


def test_karakter_muat_memperhitungkan_pembungkusan_per_kata():
    # Tanpa faktor ini taksirannya separuh dari tinggi sebenarnya: pembungkus
    # berhenti di batas kata dan menyisakan ruang di ujung tiap baris.
    assert lkl.FAKTOR_PEMBUNGKUS_KATA < 1
    mentah = int(226.0 / lkl.LEBAR_KAR_7PX)
    assert lkl.karakter_muat(226.0) < mentah


def test_huruf_JABATAN_lebih_kecil_maka_lebih_banyak_muat():
    # Kolom jabatan berhuruf 6.5px; memakai lebar huruf 7px membuatnya dinilai
    # lebih sempit daripada sebenarnya, dan halamannya jadi boros.
    assert lkl.LEBAR_KAR_65PX < lkl.LEBAR_KAR_7PX
    assert lkl.karakter_muat(200.0, lkl.LEBAR_KAR_65PX) > lkl.karakter_muat(200.0)


# ── 5. Jatah tinggi halaman dihitung dalam PIKSEL ───────────────────────

def test_kapasitas_mengurangi_seluruh_PERABOT_halaman():
    """Judul, legenda, kepala tabel, baris total, catatan, dan jalur induk
    memakan tempat yang sudah dijanjikan kepada baris. Yang tak dikurangkan
    membuat lembarnya meluber tepat sebanyak tinggi perabot itu — tanpa satu
    pun galat, hanya kaki halaman yang terdorong ke lembar berikutnya."""
    k1 = lkl.kapasitas_kolom(1)
    assert k1 < (lkl.TINGGI_ISI_SEHALAMAN - lkl.TINGGI_JUDUL_LEGENDA
                 - lkl.TINGGI_KEPALA_TABEL - lkl.TINGGI_BARIS_TOTAL)
    # Dua lajur membayar satu baris jalur induk di kepala tiap kolom.
    assert lkl.kapasitas_kolom(2) == k1 - lkl.TINGGI_JALUR_INDUK
    # Catatan kaki mengurangi jatah persis setinggi catatannya.
    catatan = lkl.tinggi_catatan("x " * 200)
    assert catatan > 0
    assert abs(lkl.kapasitas_kolom(1, catatan) - (k1 - catatan)) < 1e-9


def test_tanpa_catatan_tak_ada_yang_dikurangi():
    assert lkl.tinggi_catatan("") == 0
    assert lkl.tinggi_catatan(None) == 0
    assert lkl.kapasitas_kolom(1, 0.0) == lkl.kapasitas_kolom(1)


def test_catatan_yang_MEMBUNGKUS_memakan_lebih_banyak():
    sebaris = lkl.tinggi_catatan("Catatan pendek.")
    panjang = lkl.tinggi_catatan("Catatan yang jauh lebih panjang. " * 20)
    assert panjang > sebaris >= lkl.MARGIN_CATATAN


def test_kapasitas_tak_pernah_negatif_betapapun_besar_catatannya():
    # Catatan raksasa tak boleh membuat jatahnya minus — perulangan
    # pemaketannya akan berhenti mengambil baris dan barisnya lenyap.
    k = lkl.kapasitas_kolom(2, 100000.0)
    assert k >= lkl.tinggi_baris(1)


def test_tinggi_baris_TUMBUH_selaras_jumlah_baris_teksnya():
    satu, dua = lkl.tinggi_baris(1), lkl.tinggi_baris(2)
    assert dua - satu == lkl.TINGGI_BARIS_TEKS
    assert lkl.tinggi_baris(0) == satu, "baris kosong tetap setinggi satu"


def test_baris_teks_membulat_KE_ATAS_dan_tak_pernah_nol():
    px = 37.0                       # 10 karakter pada huruf 7px
    assert lkl.baris_teks("", px) == 1, "baris kosong tetap setinggi satu"
    assert lkl.baris_teks("a" * 10, px) == 1
    assert lkl.baris_teks("a" * 11, px) == 2, "sisa sekarakter tetap dua baris"
    assert lkl.baris_teks("a" * 30, px) == 4
    assert lkl.baris_teks(None, px) == 1
    assert lkl.baris_teks("abc", 0) >= 1, "lebar nol tak boleh membagi nol"


def test_teks_yang_MUAT_UTUH_tak_kena_harga_pembungkusan():
    """Teks yang muat tak pernah dibungkus, jadi harga pembungkusan per kata
    tak berlaku baginya.

    Mengenakannya pada keduanya adalah kekeliruan yang mahal justru karena tak
    berbunyi: nama 25 huruf pada kolom yang memuat 25 huruf dinilai dua baris,
    seluruh tabel dinilai sepertiga lebih tinggi daripada sebenarnya, dan
    sepertiga kertas ditinggalkan kosong.
    """
    px = 100.0
    muat = int(px / lkl.LEBAR_KAR_7PX)          # persis muat, tanpa diskon
    assert lkl.baris_teks("a" * muat, px) == 1
    # Sekarakter lebih panjang: barisnya pecah, dan DI SANA diskonnya berlaku.
    assert lkl.baris_teks("a" * (muat + 1), px) == 2


def test_huruf_lebih_kecil_memuat_lebih_banyak_sebaris():
    px = 100.0
    besar = lkl.baris_teks("a" * 30, px, lkl.LEBAR_KAR_7PX)
    kecil = lkl.baris_teks("a" * 30, px, lkl.LEBAR_KAR_65PX)
    assert kecil <= besar


def test_tinggi_dari_teks_memakai_lebar_yang_BERBEDA_di_tiap_tata_letak():
    f = lkl.tinggi_dari_teks(lambda b: b["name"])
    b = {"name": "a" * 200, "depth": 0}
    assert f(b, 1) < f(b, 2), "kolom sempit harus menghasilkan baris lebih banyak"


# ── 4. Kolom yang mulai di tengah pohon menyebut jalur induknya ─────────

def test_jalur_induk_dari_TERLUAR_ke_terdalam():
    baris = [
        {"name": "3 Peralatan dan Mesin", "depth": 0},
        {"name": "305 Alat Kantor", "depth": 1},
        {"name": "30501 Alat Kantor", "depth": 2},
        {"name": "3050102 Meja", "depth": 3},
    ]
    assert lkl.jalur_induk(baris, 3) == [
        "3 Peralatan dan Mesin", "305 Alat Kantor", "30501 Alat Kantor"]


def test_jalur_induk_MELEWATI_saudara_bukan_leluhur():
    baris = [
        {"name": "Gol", "depth": 0},
        {"name": "Bid A", "depth": 1},
        {"name": "Kel A1", "depth": 2},
        {"name": "Bid B", "depth": 1},
        {"name": "Kel B1", "depth": 2},
    ]
    # "Bid A" dan "Kel A1" saudara/keponakan — bukan leluhur "Kel B1".
    assert lkl.jalur_induk(baris, 4) == ["Gol", "Bid B"]


def test_baris_teratas_tak_punya_jalur_induk():
    baris = [{"name": "Gol", "depth": 0}, {"name": "Bid", "depth": 1}]
    assert lkl.jalur_induk(baris, 0) == []


def test_catatan_kaki_MENGGESER_pemaketan_halaman():
    """Catatan yang tak dikurangkan dari jatah memakan tempat yang sudah
    dijanjikan kepada baris.

    Diuji lewat RENCANA-nya, bukan lewat kapasitasnya saja: yang mudah
    terlewat bukan rumus kapasitasnya melainkan meneruskan `catatan_px` dari
    pemanggil ke perencana. Kalau ia tak diteruskan, kapasitasnya benar dan
    rencananya tetap salah — dan tak ada satu pun galat.
    """
    baris = _baris(200)
    tinggi = lkl.tinggi_dari_teks(lambda b: b["name"])
    tanpa = lkl.rencana_kolom(baris, tinggi)
    dengan = lkl.rencana_kolom(baris, tinggi, catatan_px=300.0)
    assert dengan["halaman"] != tanpa["halaman"], (
        "catatan setinggi 300px tak menggeser satu baris pun")
    assert len(dengan["halaman"]) >= len(tanpa["halaman"])
