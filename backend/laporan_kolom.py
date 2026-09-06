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

#: Tinggi kolom isi satu lembar A4 laporan eksekutif, dalam BARIS TEKS 7px.
#:
#: DIUKUR, bukan diturunkan dari aritmetika CSS, dan diukur dengan alat yang
#: benar. Mengukurnya dari tinggi kotak halaman TIDAK bisa: lembar
#: `overflow: hidden` selalu melaporkan 1122px entah isinya muat atau tidak.
#: Yang dipakai: lembarnya dirender ulang tanpa `min-height` dan tanpa
#: `overflow`, lalu tinggi `.exec-body` yang sesungguhnya dibandingkan dengan
#: jatah selembar (969px). Di atas jatah itu kaki halaman terdorong keluar dan
#: mendarat sendirian di lembar berikutnya.
#:
#: Pada fixture terpadat (kategori lima jenjang, dua lajur) batasnya jatuh di
#: antara 64 dan 66. Diambil 58: isi halaman terpadat menjadi 883px dari 969px
#: — sisa 9% sebagai jaga-jaga terhadap metrik huruf yang berbeda di mesin
#: lain, tanpa menyisakan kertas menganggur yang terlihat.
BARIS_TEKS_SEHALAMAN = 58

#: Jumlah karakter yang muat pada kolom teks utama, DIUKUR dari lebar kotak
#: kolomnya pada render weasyprint dibagi lebar rata-rata karakter — 3.4px
#: untuk huruf 7px (nama), 3.15px untuk 6.5px (jabatan) — lalu dikalikan 0.75.
#:
#: Pengali 0.75 itu HARGA PEMBUNGKUSAN PER KATA. `baris_teks` membagi rata
#: seolah huruf boleh patah di mana saja; pembungkus sungguhan berhenti di
#: batas kata dan meninggalkan sisa di ujung tiap baris. Diukur pada nama
#: kategori sungguhan, sisa itu seperempat lebar kolom — "305 — Alat Kantor
#: dan Rumah Tangga" hanya memuat 21 dari 26 karakter yang seharusnya muat.
#: Tanpa pengali ini taksirannya separuh dari tinggi sebenarnya.
#:
#: Angka sebelumnya ditaksir di atas kertas dan meleset di kedua arah sekaligus,
#: sebab kolom namanya sendiri jauh lebih sempit daripada yang seharusnya:
#: lebar kolom hanya tertulis pada `<td>` sementara `table-layout: fixed`
#: membacanya dari baris KEPALA, sehingga ketiga kolom dibagi rata dan nama
#: cuma kebagian sepertiga tabel. Setelah lebarnya dipasang di `<th>`, kolom
#: nama satu lajur terukur 526px (dari 206.5px) dan dua lajur 226px (dari
#: 106.5px).
#: Taksiran yang terlalu murah hati membuat baris panjang dinilai muat sebaris
#: padahal membungkus menjadi tiga — dan halamannya meluber. Yang lebih halus
#: lagi: untuk menutupi luberan itu jatah baris sehalaman terpaksa ditekan
#: sampai separuh kertas menganggur, persis "batas terbuang sia-sia" yang
#: diminta hilang.
KARAKTER_SATU_KOLOM = 112
KARAKTER_DUA_KOLOM = 48

#: Halaman Pengguna membagi lebarnya ke TIGA kolom yang sama-sama dapat
#: membungkus (Nama, NIP, Jabatan), jadi jatah karakternya sendiri-sendiri.
#: Pada dua kolom, Nama dan NIP menyatu sehingga jatah Nama menyempit lagi.
KAR_NAMA_1 = 38
KAR_JABATAN_1 = 56
KAR_NAMA_2 = 25
KAR_JABATAN_2 = 30

#: Tiap tingkat jorokan memakan ~11px dari kolom nama — sekitar tiga karakter
#: pada huruf 7px. Mengabaikannya adalah cara paling halus membuat halaman
#: meluber: baris jenjang terdalam kehilangan belasan karakter lebar, membungkus
#: menjadi dua-tiga baris, dan taksiran tingginya meleset justru pada baris yang
#: paling banyak jumlahnya.
KARAKTER_PER_JOROKAN = 3

#: Kolom nama tak boleh menyusut sampai tak masuk akal betapa pun dalamnya
#: jorokan; di bawah ini pembungkusannya sudah per-kata, bukan per-baris.
KARAKTER_MINIMUM = 8


def lebar_setelah_jorok(kar: int, depth) -> int:
    """Jatah karakter kolom nama setelah dikurangi jorokan sedalam `depth`."""
    try:
        d = max(0, int(depth or 0))
    except (TypeError, ValueError):
        d = 0
    return max(KARAKTER_MINIMUM, int(kar) - KARAKTER_PER_JOROKAN * d)


def baris_teks(teks, lebar_karakter: int) -> int:
    """Berapa baris teks yang ditempati `teks` pada kolom selebar itu.

    Pembungkusan sebenarnya terjadi pada BATAS KATA, jadi angka ini perkiraan
    yang sengaja tak pernah terlalu kecil: kekeliruan ke bawah membuat halaman
    meluber dan terpotong diam-diam, kekeliruan ke atas hanya menyisakan
    sedikit ruang.
    """
    t = str(teks or "").strip()
    lebar = max(1, int(lebar_karakter or 1))
    if not t:
        return 1
    return max(1, math.ceil(len(t) / lebar))


def tinggi_dari_teks(ambil_teks):
    """Fungsi tinggi baris untuk tabel yang hanya punya SATU kolom membungkus.

    Kategori dan Lokasi cukup ini; Pengguna punya tiga kolom yang bisa
    membungkus sekaligus dan menyusun fungsinya sendiri.
    """
    def tinggi(b, kolom):
        kar = KARAKTER_SATU_KOLOM if kolom == 1 else KARAKTER_DUA_KOLOM
        return baris_teks(ambil_teks(b),
                          lebar_setelah_jorok(kar, b.get("depth")))
    return tinggi


def rencana_kolom(baris, tinggi_fn=None, sehalaman=None):
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
    # Bacaannya di dalam badan fungsi, BUKAN sebagai nilai bawaan parameter:
    # nilai bawaan dibekukan saat fungsinya didefinisikan, sehingga menyetel
    # ulang tetapannya (mengukur ulang, atau uji yang menggantinya) tak
    # berpengaruh apa pun — dan diamnya terbaca sebagai "angkanya memang sudah
    # pas".
    sehalaman = BARIS_TEKS_SEHALAMAN if sehalaman is None else sehalaman
    tinggi_fn = tinggi_fn or (lambda b, kolom: 1)
    n = len(baris or [])
    if n == 0:
        return {"kolom": 1, "batang": True, "halaman": []}

    tinggi_1 = [tinggi_fn(b, 1) for b in baris]
    if sum(tinggi_1) <= sehalaman:
        return {"kolom": 1, "batang": True,
                "halaman": [{"awal": 0, "pisah": n, "akhir": n}]}

    # Tak muat satu kolom: dua kolom, batang dihilangkan supaya teksnya tetap
    # kebagian tempat.
    tinggi_2 = [tinggi_fn(b, 2) for b in baris]
    return {"kolom": 2, "batang": False,
            "halaman": _paket_dua_kolom(tinggi_2, sehalaman)}


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
    kar_nama = lebar_setelah_jorok(
        KAR_NAMA_1 if kolom == 1 else KAR_NAMA_2, b.get("depth"))
    kar_jab = KAR_JABATAN_1 if kolom == 1 else KAR_JABATAN_2
    tinggi_nama = baris_teks(nama, kar_nama)
    if kolom == 2 and b.get("daun"):
        tinggi_nama += 1   # NIP turun ke barisnya sendiri
    return max(tinggi_nama, baris_teks(jabatan, kar_jab))
