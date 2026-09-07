"""Pemilihan kolom & pemaketan halaman tabel distribusi Laporan Eksekutif.

Permintaan pemilik: *"pastikan benar benar tidak ada batas terbuang sia sia di
ukuran A4 hingga mencapai footer terlebih dahulu di semua distribusi, agar
dibuat smart juga apabila melebihi sudah maka berganti 2 kolom dengan Barchart
yang menghilang agar cukup, baru lanjutkan ke halaman kedua apabila memang
tidak cukup lagi."*

Sebelumnya tiap halaman distribusi memakai TETAPAN baris per halaman, dan
tetapan salah di kedua arah: dua puluh baris menyisakan dua pertiga kertas
kosong, sementara daftar yang sedikit lebih panjang membuka kertas kedua untuk
tiga baris. Modul ini menggantikannya dengan urutan keputusan yang sama dengan
yang diminta:

    muat satu kolom?            → satu kolom, BERBATANG
    tidak                       → dua kolom, batang DIHILANGKAN
    masih tidak muat juga       → baru halaman berikutnya

Tiga keputusan yang membentuknya:

1. **Yang dihitung BARIS TEKS, bukan baris tabel.** Nama unit dan jabatan
   tak lagi dipotong "…" melainkan dibungkus ke bawah, jadi satu baris tabel
   bisa setinggi dua atau tiga baris teks. Memaket menurut jumlah baris tabel
   membuat halaman yang isinya panjang-panjang meluber — dan lembar
   `overflow: hidden` memotongnya tanpa bersuara.

2. **Batang yang hilang MEMBAYAR kolom kedua.** Dua kolom memberi hampir dua
   kali kapasitas, tetapi tiap kolomnya jauh lebih sempit; batang adalah yang
   paling boleh pergi, sebab ia perbandingan yang masih terbaca dari angkanya.

3. **Keputusannya dihitung sekali, di Python.** Template yang memutuskan
   sendiri jumlah kolomnya akan berbeda pendapat dengan penghitung halaman di
   Python, dan "Hal 2 dari 3" pada kop lalu berbohong tanpa satu pun galat.
"""

import math

# ── Geometri lembar, DIUKUR dari render weasyprint ─────────────────────
#
# Satuannya PIKSEL, bukan "baris teks". Satuan baris teks pernah dipakai dan
# gagal dengan cara yang tak berbunyi: satu angka jatah dipakai tiga tabel yang
# tinggi barisnya berbeda-beda, sehingga angka yang pas untuk halaman kategori
# menyisakan sepertiga kertas kosong di halaman pengguna. Piksel membuat
# ketiganya diisi sampai batas fisik yang sama.

#: Tinggi isi (`.exec-body`) satu lembar distribusi. Kop halaman distribusi
#: dua baris, jadi jatahnya sedikit lebih kecil daripada lembar berkop satu
#: baris (981px) — yang dipakai yang lebih kecil.
#:
#: Mengukurnya dari tinggi kotak LEMBAR tidak bisa: lembar `overflow: hidden`
#: selalu melaporkan 1122px entah isinya muat atau meluber, jadi jawabannya
#: selalu "muat". Yang dipakai tinggi `.exec-body` pada lembar yang memang
#: tidak meluber.
TINGGI_ISI_SEHALAMAN = 969.5

#: Judul grafik + legenda jenjang di atas tabel, berikut jaraknya.
TINGGI_JUDUL_LEGENDA = 30.9

#: Baris kepala tabel (`<thead>`).
TINGGI_KEPALA_TABEL = 13.9

#: Baris "Total seluruh aset" di kaki tabel. Ia hanya muncul di lembar
#: terakhir; dihitung di semua lembar karena selisihnya satu baris.
TINGGI_BARIS_TOTAL = 15.5

#: Baris "↵ jalur induk" di kepala kolom yang mulai di tengah pohon — hanya
#: pada tata letak dua lajur.
TINGGI_JALUR_INDUK = 10.0

#: Tinggi satu baris teks 7px (line-height 1.35) dan sisipan tetap tiap baris
#: tabel (padding 1.5px atas-bawah + garis). Diukur: baris satu-baris 13.4px,
#: baris dua-baris 22.9px — selisihnya 9.45, sisanya 3.95.
TINGGI_BARIS_TEKS = 9.45
SISIPAN_BARIS = 3.95

#: Catatan kaki tabel: `margin-top` 6px + baris teks 7px selebar penuh.
MARGIN_CATATAN = 6.0

#: Cadangan yang HARUS ditinggalkan di luar perabot yang dapat ditunjuk.
#:
#: Ia menyerap kelesetan taksiran tinggi baris ke dua arah: pembungkusan
#: sebenarnya bergantung di mana batas katanya jatuh, dan itu tak dapat
#: dihitung dari panjang teks saja.
#:
#: DIKALIBRASI dengan render A4 sungguhan pada delapan fixture, dengan dua
#: patokan sekaligus:
#:
#: - jumlah halaman PDF harus sama dengan jumlah lembar HTML (kaki halaman
#:   tak terdorong keluar), dan
#: - jarak antara bawah tabel dan kaki halaman harus tetap POSITIF.
#:
#: Patokan kedua yang mengikat sekarang: sejak `.exec-body` memakai
#: `flex: 1 1 0; min-height: 0`, kelebihan isi tak lagi mendorong halaman
#: melainkan menindih kaki halaman. Jarak nol tercapai pada -30; diambil 40,
#: yang menyisakan 67px pada lembar terpadat — cukup terlihat sebagai batas,
#: cukup jauh dari nol untuk menahan metrik huruf mesin lain.
#:
#: Angkanya pernah 100 karena menyerap cacat lain: kotak isi diregangkan
#: melewati jatahnya oleh `min-height: auto` bawaan flex. Setelah cacat itu
#: diperbaiki di CSS, cadangan sebesar itu tak lagi diperlukan — dan
#: menyimpannya berarti membuang seratus piksel kertas di tiap lembar.
CADANGAN_TATA_LETAK = 40.0

# ── Lebar kolom, DIUKUR dari render weasyprint ─────────────────────────
#
# Yang ditulis di sini LEBAR PIKSEL kotak kolomnya, bukan jumlah karakter
# hasil hitungan tangan: piksel dapat dicocokkan langsung dengan hasil render
# (uji `test_lebar_kolom_sesuai_yang_tergambar` melakukannya), sedangkan angka
# karakter hanya dapat dipercaya oleh yang menghitungnya.

#: Lebar rata-rata satu karakter. Diukur dari kotak baris yang benar-benar
#: tergambar — lebar baris dibagi cacah hurufnya — bukan dari setengah
#: ukuran huruf. Taksiran 3.4px pernah dipakai dan meleset ~9%: cukup untuk
#: membuat halaman terpadat meluber 48px tanpa satu pun galat.
LEBAR_KAR_7PX = 3.7
LEBAR_KAR_65PX = 3.44

#: Harga PEMBUNGKUSAN PER KATA. `baris_teks` membagi rata seolah huruf boleh
#: patah di mana saja; pembungkus sungguhan berhenti di batas kata dan
#: meninggalkan sisa di ujung tiap baris. Diukur pada nama kategori sungguhan,
#: sisa itu seperempat lebar kolom — "305 — Alat Kantor dan Rumah Tangga"
#: hanya memuat 21 dari 26 karakter yang seharusnya muat.
FAKTOR_PEMBUNGKUS_KATA = 0.75

#: Lebar kotak kolom nama pada tabel Kategori/Lokasi, satu dan dua lajur.
#:
#: Keduanya pernah jauh lebih sempit — 206.5px dan 106.5px — karena lebar
#: kolomnya hanya tertulis pada `<td>` sementara `table-layout: fixed`
#: membacanya dari baris KEPALA, sehingga ketiga kolom dibagi rata.
PX_NAMA_1_KOLOM = 526.0
PX_NAMA_2_KOLOM = 226.0

#: Tabel Pengguna membagi lebarnya ke TIGA kolom yang sama-sama dapat
#: membungkus (Nama, NIP, Jabatan). Pada dua lajur, Nama dan NIP menyatu
#: sehingga jatah Nama menyempit lagi.
PX_NAMA_PENGGUNA_1 = 177.7
PX_JABATAN_1 = 244.3
PX_NAMA_PENGGUNA_2 = 117.5
PX_JABATAN_2 = 132.9

#: Catatan kaki tabel selebar penuh isi lembar.
PX_CATATAN = 742.0

#: Tiap tingkat jorokan memakan 11px dari kolom nama. Mengabaikannya adalah
#: cara paling halus membuat halaman meluber: baris jenjang terdalam kehilangan
#: belasan karakter lebar, membungkus menjadi dua-tiga baris, dan taksiran
#: tingginya meleset justru pada baris yang paling banyak jumlahnya.
PX_JOROKAN = 11.0

#: Kolom nama tak boleh menyusut sampai tak masuk akal betapa pun dalamnya
#: jorokan; di bawah ini pembungkusannya sudah per-kata, bukan per-baris.
PX_MINIMUM = 30.0
KARAKTER_MINIMUM = 8


def karakter_muat(px: float, lebar_kar: float = LEBAR_KAR_7PX) -> int:
    """Berapa karakter yang muat pada kolom selebar `px`."""
    return max(KARAKTER_MINIMUM,
               int(float(px) / lebar_kar * FAKTOR_PEMBUNGKUS_KATA))



def lebar_setelah_jorok(px: float, depth) -> float:
    """Lebar piksel kolom nama setelah jorokan sedalam `depth`.

    Jorokan memakan lebar kolom NAMA, bukan lebar tabel: barisnya menjorok ke
    dalam selnya sendiri.
    """
    try:
        d = max(0, int(depth or 0))
    except (TypeError, ValueError):
        d = 0
    return max(PX_MINIMUM, float(px) - PX_JOROKAN * d)


def baris_teks(teks, px: float, lebar_kar: float = LEBAR_KAR_7PX) -> int:
    """Berapa baris teks yang ditempati `teks` pada kolom selebar `px`.

    Dua hal yang berbeda, dan membedakannya penting:

    - Teks yang MUAT UTUH tak pernah dibungkus, jadi ia sebaris betapa pun
      mepetnya. Harga pembungkusan per kata tak berlaku baginya.
    - Teks yang TAK muat dibungkus pada batas kata, dan tiap barisnya
      menyisakan ruang di ujung — di sinilah `FAKTOR_PEMBUNGKUS_KATA`.

    Mengenakan harga itu pada keduanya adalah kekeliruan yang mahal justru
    karena tak berbunyi: nama sepanjang 25 huruf pada kolom yang memuat 25
    huruf dinilai dua baris, seluruh tabel dinilai sepertiga lebih tinggi
    daripada sebenarnya, dan sepertiga kertas ditinggalkan kosong.
    """
    t = str(teks or "").strip()
    if not t:
        return 1
    mentah = max(1.0, float(px) / max(0.1, lebar_kar))
    if len(t) <= mentah:
        return 1
    return max(2, math.ceil(len(t) / (mentah * FAKTOR_PEMBUNGKUS_KATA)))


def tinggi_baris(jumlah_baris_teks: int) -> float:
    """Tinggi satu baris tabel dalam piksel, dari jumlah baris teksnya."""
    return max(1, int(jumlah_baris_teks)) * TINGGI_BARIS_TEKS + SISIPAN_BARIS


def tinggi_catatan(teks) -> float:
    """Tinggi catatan kaki tabel dalam piksel — 0 bila tak ada catatan.

    Catatan yang tak dihitung memakan tempat yang sudah dijanjikan kepada
    baris, dan lembarnya meluber tepat sebanyak tinggi catatan itu.
    """
    t = str(teks or "").strip()
    if not t:
        return 0.0
    return MARGIN_CATATAN + baris_teks(t, PX_CATATAN) * TINGGI_BARIS_TEKS


def kapasitas_kolom(kolom: int, catatan_px: float = 0.0) -> float:
    """Tinggi yang tersisa untuk BARIS tabel pada satu lajur, dalam piksel.

    Perabot halaman dikurangkan lebih dulu — judul, legenda, kepala tabel,
    baris total, catatan kaki, dan (pada dua lajur) baris jalur induk. Tanpa
    itu jatahnya dihitung seolah tabelnya memenuhi lembar dari tepi ke tepi,
    dan kelebihan itu persis yang mendorong kaki halaman keluar.
    """
    sisa = (TINGGI_ISI_SEHALAMAN - CADANGAN_TATA_LETAK - TINGGI_JUDUL_LEGENDA
            - TINGGI_KEPALA_TABEL - TINGGI_BARIS_TOTAL - max(0.0, catatan_px))
    if kolom == 2:
        sisa -= TINGGI_JALUR_INDUK
    return max(tinggi_baris(1), sisa)


def tinggi_dari_teks(ambil_teks):
    """Fungsi tinggi baris untuk tabel yang hanya punya SATU kolom membungkus.

    Kategori dan Lokasi cukup ini; Pengguna punya tiga kolom yang bisa
    membungkus sekaligus dan menyusun fungsinya sendiri.
    """
    def tinggi(b, kolom):
        px = PX_NAMA_1_KOLOM if kolom == 1 else PX_NAMA_2_KOLOM
        return tinggi_baris(baris_teks(
            ambil_teks(b), lebar_setelah_jorok(px, b.get("depth"))))
    return tinggi


def rencana_kolom(baris, tinggi_fn=None, sehalaman=None, catatan_px=0.0):
    """`{"kolom", "batang", "halaman"}` — rencana tata letak satu tabel.

    `tinggi_fn(baris, kolom)` mengembalikan tinggi satu baris dalam BARIS TEKS,
    untuk tata letak satu atau dua kolom. Ia menerima jumlah kolomnya karena
    tinggi baris memang berubah bersama tata letaknya: pada dua kolom, kolom
    Nama dan NIP digabung sehingga NIP turun ke barisnya sendiri, dan baris
    yang setinggi satu di satu kolom menjadi setinggi dua di dua kolom.
    Menghitungnya dengan lebar yang sama untuk kedua mode adalah cara paling
    langsung membuat halamannya meluber.

    `halaman` adalah daftar `[{"awal", "pisah", "akhir"}, …]`. `pisah` adalah
    indeks tempat kolom KEDUA dimulai; pada tata letak satu kolom ia sama
    dengan `akhir`.

    Kolom KIRI diisi sampai penuh, baru kolom kanan — bukan dibelah rata.
    Membelah rata memang membuat tingginya seimbang, tetapi pada daftar yang
    hanya sedikit melewati batas satu kolom hasilnya dua kolom yang sama-sama
    sepertiga penuh dengan setengah kertas kosong di bawahnya: persis "batas
    terbuang sia-sia" yang diminta hilang. Mengisi berurutan juga
    mempertahankan urutan baca — kiri dari atas ke bawah, lalu kanan.
    """
    # Jatahnya dihitung di dalam badan fungsi, BUKAN sebagai nilai bawaan
    # parameter: nilai bawaan dibekukan saat fungsinya didefinisikan, sehingga
    # menyetel ulang tetapannya (mengukur ulang, atau uji yang menggantinya)
    # tak berpengaruh apa pun — dan diamnya terbaca sebagai "angkanya memang
    # sudah pas".
    #
    # Jatah satu lajur dan dua lajur BERBEDA: dua lajur membayar satu baris
    # jalur induk di kepala tiap kolom.
    tinggi_fn = tinggi_fn or (lambda b, kolom: 1)
    n = len(baris or [])
    if n == 0:
        return {"kolom": 1, "batang": True, "halaman": []}

    jatah_1 = kapasitas_kolom(1, catatan_px) if sehalaman is None else sehalaman
    jatah_2 = kapasitas_kolom(2, catatan_px) if sehalaman is None else sehalaman

    tinggi_1 = [tinggi_fn(b, 1) for b in baris]
    if sum(tinggi_1) <= jatah_1:
        return {"kolom": 1, "batang": True,
                "halaman": [{"awal": 0, "pisah": n, "akhir": n}]}

    # Tak muat satu kolom: dua kolom, batang dihilangkan supaya teksnya tetap
    # kebagian tempat.
    tinggi_2 = [tinggi_fn(b, 2) for b in baris]
    return {"kolom": 2, "batang": False,
            "halaman": _paket_dua_kolom(tinggi_2, jatah_2)}


def jalur_induk(baris, i):
    """Nama leluhur `baris[i]`, dari terluar ke terdalam.

    Dipakai kolom/halaman yang MULAI di tengah pohon: tanpa jalur induknya
    tercetak di kepala kolom, sebuah baris "30501 — Alat Kantor" berdiri
    sendirian di kolom kanan sementara "3 — Peralatan dan Mesin" ada di kolom
    kiri, dan hubungan yang justru menjadi alasan pohonnya dibuat hilang di
    situ.
    """
    jalur, butuh = [], (baris[i]["depth"] if i < len(baris) else 0)
    for j in range(i - 1, -1, -1):
        if butuh <= 0:
            break
        if baris[j]["depth"] < butuh:
            jalur.append(baris[j].get("name") or baris[j].get("label") or "")
            butuh = baris[j]["depth"]
    return list(reversed(jalur))


def _isi_kolom(tinggi, mulai, kapasitas):
    """Indeks setelah baris terakhir yang masih muat, mulai dari `mulai`.

    Baris yang SENDIRIAN saja sudah melebihi kapasitas tetap diambil satu —
    tanpa itu perulangannya tak pernah maju, dan barisnya hilang dari laporan
    tanpa satu pun tanda.
    """
    if mulai >= len(tinggi):
        return mulai
    i, terpakai = mulai, 0
    while i < len(tinggi):
        if terpakai and terpakai + tinggi[i] > kapasitas:
            break
        terpakai += tinggi[i]
        i += 1
    return max(i, mulai + 1)


def _paket_dua_kolom(tinggi, kapasitas_kolom):
    """`[{"awal", "pisah", "akhir"}, …]` — kolom kiri penuh dulu, baru kanan."""
    keluar, awal = [], 0
    n = len(tinggi)
    while awal < n:
        pisah = _isi_kolom(tinggi, awal, kapasitas_kolom)
        akhir = _isi_kolom(tinggi, pisah, kapasitas_kolom)
        keluar.append({"awal": awal, "pisah": pisah, "akhir": akhir})
        awal = akhir
    return keluar


def tinggi_pengguna(b, kolom) -> int:
    """Tinggi baris tabel Pengguna dalam baris teks, untuk `kolom` kolom.

    Tabel ini punya TIGA kolom yang sama-sama dapat membungkus (Nama, NIP,
    Jabatan), jadi tinggi barisnya yang TERTINGGI di antara mereka —
    menaksirnya dari nama saja membuat baris berjabatan panjang selalu
    dinilai terlalu pendek.

    Pada dua kolom, Nama dan NIP menyatu (permintaan pemilik: *"apabila menjadi
    2 kolom, maka gabungkan kolom Nama dan NIP/NIK agar menghemat ruang
    juga"*), sehingga NIP turun ke barisnya sendiri dan tiap baris PENGGUNA
    bertambah satu baris teks. Baris pembagi tak punya NIP, jadi ia tidak.
    """
    nama, jabatan = (b.get("name") or ""), (b.get("jabatan") or "")
    px_nama = lebar_setelah_jorok(
        PX_NAMA_PENGGUNA_1 if kolom == 1 else PX_NAMA_PENGGUNA_2,
        b.get("depth"))
    px_jab = PX_JABATAN_1 if kolom == 1 else PX_JABATAN_2
    baris_nama = baris_teks(nama, px_nama)
    if kolom == 2 and b.get("daun"):
        baris_nama += 1   # NIP turun ke barisnya sendiri
    return tinggi_baris(max(baris_nama,
                            baris_teks(jabatan, px_jab, LEBAR_KAR_65PX)))
