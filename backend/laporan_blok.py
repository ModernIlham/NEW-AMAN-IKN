"""Penataan blok halaman "Analisis Lanjutan, Tim & Cakupan Data".

Permintaan pemilik: *"pada analisis, tim lanjutan & cakupan jadikan smart semua
dalam mengatur posisinya masing-masing menyesuaikan bagaimana caranya berbagi
dan mengalah untuk menampilkan informasi sebaik mungkin tanpa harus
melanjutkan ke halaman kedua dengan memaksimalkan A4 yang ada tanpa harus
menggunakan "…" dan terpampang dengan baik."*

Sebelumnya halaman ini disusun TETAP: pasangan blok ditulis tangan di templat,
lebar kolom label dipatok, dan yang tak muat dipotong — nama unit pada 25
huruf, nama kategori pada 20. Dua akibatnya berlawanan dan sama-sama tak
berbunyi: seperlima kertas menganggur di bawah, sementara di atasnya
"Kedeputian Bidang Transformasi Hijau dan Digital" tercetak sebagai
"Kedeputian Bidang Transfo".

Modul ini menggantikan susunan tetap itu dengan tiga keputusan:

1. **Tinggi tiap blok DIHITUNG dari isinya**, memakai geometri yang diukur dari
   render — bukan ditaksir. Blok yang barisnya banyak memang lebih tinggi, dan
   penata halaman tahu persis berapa.

2. **Blok yang muat berdampingan DIPASANGKAN.** Dua blok setengah-lebar
   berurutan berbagi satu baris, dan tinggi barisnya yang tertinggi di antara
   keduanya — yang pendek "mengalah" mengisi sisa ruang pasangannya. Blok yang
   memang butuh lebar penuh (tabel lima kolom, daftar berlabel panjang) tak
   dipaksa menyempit.

3. **Halaman kedua hanya dibuka bila baris berikutnya sungguh tak muat.**
   Bukan karena susunannya kebetulan begitu.

MURNI: tak menyentuh basis data, tak merender apa pun. Yang diuji di sini
sifatnya; yang menjaga angkanya tetap cocok dengan CSS adalah uji yang
merender laporannya sungguhan.
"""

import laporan_kolom as lkl

# ── Geometri, DIUKUR dari render weasyprint ────────────────────────────
#
# Angka-angka ini pasangan dari CSS-nya. Bila CSS-nya bergeser, ia harus ikut
# bergeser — `test_tinggi_blok_SESUAI_yang_tergambar` membandingkan keduanya
# pada render sungguhan, jadi selisihnya berbunyi alih-alih diam.

#: Judul grafik di dalam kotak, berikut jarak ke isinya.
TINGGI_JUDUL_BOX = 20.9

#: Rangka kotak grafik: garis 1px dua sisi + padding 12px dua sisi.
SISIPAN_BOX = 26.0

#: Jarak antar baris blok. Diberikan oleh baris penampungnya, bukan oleh
#: margin tiap blok: margin yang menempel pada blok ikut terbawa ke mana pun
#: blok itu ditempatkan, dan blok pertama sebuah lembar lalu terdorong turun
#: oleh jarak yang tak memisahkan apa pun.
JARAK_BLOK = 14.0

#: Tinggi satu baris pada tiap jenis daftar, berikut jaraknya ke baris
#: berikutnya. Baris berlabel PANJANG lebih tinggi daripada palangnya sendiri,
#: jadi tingginya diambil yang terbesar di antara keduanya.
TINGGI_TRACK_HBAR = 16.0
TINGGI_BARIS_LABEL_HBAR = 9.1
JARAK_BARIS_HBAR = 5.0

TINGGI_TRACK_SBAR = 14.0
TINGGI_BARIS_LABEL_SBAR = 8.5
JARAK_BARIS_SBAR = 4.0

PITCH_CAKUPAN = 20.0     # cakupan pendataan

#: Legenda tiga warna di atas daftar kondisi.
TINGGI_LEGENDA_KONDISI = 22.9

#: Donat komposisi status.
TINGGI_DONUT = 100.0

#: Rangka blok tim: garis 2 + padding 20. Jaraknya ke blok lain datang dari
#: baris penampungnya, sama seperti kotak grafik.
SISIPAN_TIM = 22.0
#: Judul blok tim berikut jaraknya.
TINGGI_JUDUL_TIM = 16.3
#: Kartu tim (peran, nama, NIP) berikut paddingnya.
TINGGI_KARTU_TIM = 41.8
#: Tabel tim: baris kepala dan sub-judul di atas tiap tabel.
TINGGI_KEPALA_TABEL_TIM = 15.4
TINGGI_SUBJUDUL_TIM = 13.1
JARAK_ANTAR_TABEL_TIM = 8.0

#: Lebar isi lembar dan lebar satu lajur bila dua blok berbagi baris.
LEBAR_ISI = 742.0
JARAK_LAJUR = 14.0

#: Lebar kolom tabel tim, dalam piksel — dijumlahkan pas selebar isi blok tim
#: (742 dikurangi garis 2 dan padding 24). Dinyatakan supaya tinggi barisnya
#: dapat dihitung di muka; lihat `.tim-tabel { table-layout: fixed }`.
LEBAR_KOLOM_TIM = (52.0, 148.0, 196.0, 96.0, 224.0)
LEBAR_KOLOM_PENDUKUNG = (180.0, 200.0, 110.0, 226.0)

#: Huruf tabel tim 8px; sisipan sel 3px atas-bawah + garis bawah 1px.
LEBAR_KAR_TIM = 4.23
TINGGI_BARIS_TEKS_TIM = 10.7
SISIPAN_BARIS_TIM = 6.0
#: Harga pembungkusan per kata, sama alasannya dengan di `laporan_kolom`.
FAKTOR_PEMBUNGKUS_KATA_TIM = 0.75


def lebar_lajur(kolom: int) -> float:
    """Lebar satu blok bila barisnya diisi `kolom` blok."""
    if kolom <= 1:
        return LEBAR_ISI
    return (LEBAR_ISI - JARAK_LAJUR * (kolom - 1)) / kolom


def tinggi_box(isi: float) -> float:
    """Tinggi kotak grafik (border-box) dari tinggi isinya."""
    return TINGGI_JUDUL_BOX + isi + SISIPAN_BOX


def tinggi_baris_hbar(baris_label: int = 1) -> float:
    return (max(TINGGI_TRACK_HBAR,
                max(1, int(baris_label)) * TINGGI_BARIS_LABEL_HBAR)
            + JARAK_BARIS_HBAR)


def tinggi_baris_sbar(baris_label: int = 1) -> float:
    return (max(TINGGI_TRACK_SBAR,
                max(1, int(baris_label)) * TINGGI_BARIS_LABEL_SBAR)
            + JARAK_BARIS_SBAR)


def tinggi_daftar_bar(baris_label) -> float:
    """`baris_label` = cacah baris teks tiap label, satu angka per baris data."""
    return tinggi_box(sum(tinggi_baris_hbar(n) for n in (baris_label or [])))


def tinggi_kondisi(baris_label) -> float:
    return tinggi_box(TINGGI_LEGENDA_KONDISI
                      + sum(tinggi_baris_sbar(n) for n in (baris_label or [])))


def tinggi_donut() -> float:
    return tinggi_box(TINGGI_DONUT)


def tinggi_cakupan(n: int = 3) -> float:
    return tinggi_box(max(0, int(n)) * PITCH_CAKUPAN)


def tinggi_tim_kartu(baris_kartu: int = 1) -> float:
    """Blok tim berisi kartu (Penanggung Jawab, Tim Peneliti)."""
    return SISIPAN_TIM + TINGGI_JUDUL_TIM + max(1, int(baris_kartu)) * TINGGI_KARTU_TIM


def _baris_tabel(t):
    """Normalkan argumen tabel: angka → daftar `[1, 1, …]`."""
    if t is None:
        return []
    if isinstance(t, (int, float)):
        return [1] * max(0, int(t))
    return [max(1, int(n)) for n in t]


def tinggi_baris_tim(baris_teks: int = 1) -> float:
    """Tinggi satu baris tabel tim dari jumlah baris teks selnya.

    Anggota berjabatan panjang menempati dua-tiga baris. Menghitung semuanya
    sebaris membuat blok tim ditaksir jauh lebih pendek daripada yang
    tergambar — 220px untuk yang sebenarnya 288px — dan halamannya meluber.
    """
    return max(1, int(baris_teks)) * TINGGI_BARIS_TEKS_TIM + SISIPAN_BARIS_TIM


def baris_teks_anggota(nilai_sel, lebar_kolom=LEBAR_KOLOM_TIM) -> int:
    """Berapa baris teks yang ditempati satu baris tabel tim.

    Tinggi barisnya ditentukan sel yang PALING banyak membungkus, bukan sel
    pertama atau sel terpanjang secara huruf: kolom sempit membungkus lebih
    sering daripada kolom lebar meski isinya lebih pendek.
    """
    import math
    paling = 1
    for teks, px in zip(nilai_sel, lebar_kolom):
        n = len(str(teks or "").strip())
        if not n:
            continue
        muat = max(1.0, float(px) / LEBAR_KAR_TIM * FAKTOR_PEMBUNGKUS_KATA_TIM)
        paling = max(paling, math.ceil(n / muat))
    return paling


def tinggi_tim_tabel(*baris_tabel) -> float:
    """Blok tim berisi satu atau lebih tabel.

    Tiap argumen satu tabel: entah cacah barisnya (semua sebaris), entah
    daftar cacah baris teks tiap barisnya. Tabel kosong tak ikut dihitung —
    ia memang tak tergambar.
    """
    isi, tabel = 0.0, [_baris_tabel(t) for t in baris_tabel]
    tabel = [t for t in tabel if t]
    for t in tabel:
        isi += (TINGGI_SUBJUDUL_TIM + TINGGI_KEPALA_TABEL_TIM
                + sum(tinggi_baris_tim(n) for n in t))
    if tabel:
        # Jaraknya menempel pada tabel PERTAMA (margin-bottom-nya), jadi ia
        # ada entah tabelnya satu atau dua. Menghitungnya hanya saat ada dua
        # membuat blok bertabel satu ditaksir 8px terlalu pendek — cukup untuk
        # menggeser blok terakhir keluar lembar tanpa satu pun tanda.
        isi += JARAK_ANTAR_TABEL_TIM
    return SISIPAN_TIM + TINGGI_JUDUL_TIM + isi


#: Sekurang-kurangnya sekian baris sebelum sebuah tabel layak dipecah. Sisa
#: ruang yang hanya memuat satu-dua baris lebih baik dibiarkan kosong: potongan
#: sependek itu menambah satu judul dan satu baris kepala untuk memindahkan
#: dua baris data.
MINIMUM_BARIS_PECAH = 3


def blok(id_blok, tinggi, separuh=False, jarak=None):
    """Satu blok siap-tata."""
    return {"id": id_blok, "tinggi": float(tinggi), "separuh": bool(separuh),
            "jarak": JARAK_BLOK if jarak is None else float(jarak)}


def blok_tabel_tim(id_blok, tabel, separuh=False):
    """Blok tim bertabel yang BOLEH dipecah antar-lembar.

    `tabel` = [(judul, kunci_data, cacah_baris), …]. Tanpa pemecahan, daftar
    tim yang lebih panjang daripada satu lembar tetap ditempatkan utuh pada
    satu lembar — dan sisanya terpotong senyap oleh `overflow: hidden`. Diuji
    pada 60 anggota: delapan orang hilang dari cetakan tanpa satu pun tanda.
    """
    isi = [(j, k, _baris_tabel(n)) for j, k, n in tabel]
    isi = [(j, k, t) for j, k, t in isi if t]
    return {"id": id_blok, "separuh": bool(separuh), "jarak": JARAK_BLOK,
            # Tinggi TIAP baris disimpan, bukan cacahnya saja: pemecahan
            # antar-lembar harus tahu baris mana yang setinggi apa, sebab
            # anggota berjabatan panjang memakan dua-tiga kali lipat.
            "baris_tinggi": {k: [tinggi_baris_tim(n) for n in t]
                             for _, k, t in isi},
            "potong": [{"judul": j, "kunci": k, "awal": 0, "akhir": len(t),
                        "lanjutan": False} for j, k, t in isi],
            "tinggi": tinggi_tim_tabel(*[t for _, _, t in isi])}


def _tinggi_potong(b, potong) -> float:
    """Tinggi blok tim untuk irisan tabel `potong`."""
    isi = 0.0
    for t in potong:
        tinggi = b["baris_tinggi"][t["kunci"]][t["awal"]:t["akhir"]]
        isi += TINGGI_SUBJUDUL_TIM + TINGGI_KEPALA_TABEL_TIM + sum(tinggi)
    if potong:
        isi += JARAK_ANTAR_TABEL_TIM
    return SISIPAN_TIM + TINGGI_JUDUL_TIM + isi


def _pecah_blok_tim(b, sisa):
    """`(kepala, ekor)` — bagi blok tim agar bagian pertamanya muat `sisa`.

    Mengembalikan `(None, None)` bila yang muat lebih sedikit daripada
    `MINIMUM_BARIS_PECAH`.
    """
    ruang = float(sisa) - SISIPAN_TIM - TINGGI_JUDUL_TIM - JARAK_ANTAR_TABEL_TIM
    kepala, ekor, terambil = [], [], 0
    for t in b["potong"]:
        tinggi = b["baris_tinggi"][t["kunci"]][t["awal"]:t["akhir"]]
        muat = 0
        if tinggi and ruang >= (TINGGI_SUBJUDUL_TIM + TINGGI_KEPALA_TABEL_TIM
                                + tinggi[0]):
            ruang -= TINGGI_SUBJUDUL_TIM + TINGGI_KEPALA_TABEL_TIM
            for h in tinggi:
                if ruang < h:
                    break
                ruang -= h
                muat += 1
        if muat > 0:
            terambil += muat
            kepala.append({**t, "akhir": t["awal"] + muat})
        if muat < len(tinggi):
            ekor.append({**t, "awal": t["awal"] + muat,
                         "lanjutan": t["lanjutan"] or muat > 0})
    if terambil < MINIMUM_BARIS_PECAH or not ekor:
        return None, None
    return ({**b, "potong": kepala, "tinggi": _tinggi_potong(b, kepala)},
            {**b, "potong": ekor, "tinggi": _tinggi_potong(b, ekor)})


def _baris_dari(blok_list):
    """Pasangkan blok setengah-lebar yang BERURUTAN menjadi satu baris.

    Yang dipasangkan hanya yang berdampingan: menukar urutan blok demi
    memadatkan halaman membuat urutan bacanya berpindah-pindah tanpa alasan
    yang terlihat pembaca.
    """
    baris, i = [], 0
    while i < len(blok_list):
        b = blok_list[i]
        if b["separuh"] and i + 1 < len(blok_list) and blok_list[i + 1]["separuh"]:
            pasangan = [b, blok_list[i + 1]]
            baris.append({
                "blok": pasangan,
                # Tinggi baris = yang TERTINGGI. Yang pendek mengisi sisa
                # ruangnya sendiri, bukan memaksa yang tinggi menyusut.
                "tinggi": max(x["tinggi"] for x in pasangan),
                "jarak": max(x["jarak"] for x in pasangan),
            })
            i += 2
            continue
        baris.append({"blok": [b], "tinggi": b["tinggi"], "jarak": b["jarak"]})
        i += 1
    return baris


def rencana_blok(blok_list, sehalaman=None):
    """`{"halaman": [[baris, …], …]}` — susunan blok per lembar.

    `sehalaman` tinggi isi yang boleh dipakai satu lembar; bawaannya jatah
    lembar laporan ini dikurangi cadangan yang sama dengan yang dipakai tabel
    distribusi, supaya keduanya tak berselisih paham soal apa artinya "muat".

    Halaman baru dibuka HANYA bila baris berikutnya tak muat lagi. Baris yang
    sendirian saja sudah melebihi satu lembar tetap diambil — tanpa itu
    perulangannya tak pernah maju dan bloknya lenyap dari laporan.
    """
    jatah = (lkl.TINGGI_ISI_SEHALAMAN - lkl.CADANGAN_TATA_LETAK
             if sehalaman is None else float(sehalaman))
    baris = _baris_dari([b for b in (blok_list or []) if b])
    if not baris:
        return {"halaman": []}

    halaman, kini, terpakai = [], [], 0.0
    antre = list(baris)
    while antre:
        b = antre.pop(0)
        # Jarak antar blok tak dihitung pada blok pertama tiap lembar: di sana
        # ia tak memisahkan apa pun.
        jarak = b["jarak"] if kini else 0.0
        if terpakai + b["tinggi"] + jarak <= jatah:
            kini.append(b)
            terpakai += b["tinggi"] + jarak
            continue
        # Tak muat. Sebelum membuka lembar baru, coba isi sisanya dengan
        # sebagian tabel — itulah "mengalah" yang diminta: bagian yang muat
        # tetap tercetak di sini, sisanya menyambung di lembar berikutnya.
        #
        # Ini berlaku juga ketika bloknya SENDIRIAN di lembar kosong dan tetap
        # tak muat: di situlah daftar tim yang lebih panjang daripada selembar
        # dulu ditempatkan utuh lalu ekornya terpotong senyap.
        kepala, ekor = _coba_pecah(b, jatah - terpakai - jarak)
        if kepala is not None:
            kini.append(kepala)
            halaman.append(kini)
            kini, terpakai = [], 0.0
            antre.insert(0, ekor)
            continue
        if not kini:
            # Tak dapat dipecah dan sendirian pun tak muat: tetap diambil.
            # Tanpa ini perulangannya tak pernah maju dan bloknya lenyap.
            kini.append(b)
            terpakai += b["tinggi"]
            continue
        halaman.append(kini)
        kini, terpakai = [], 0.0
        antre.insert(0, b)
    if kini:
        halaman.append(kini)
    return {"halaman": halaman}


def _coba_pecah(baris_blok, sisa):
    """Pecah baris berisi SATU blok bertabel; selain itu tak dipecah.

    Blok berdampingan tak dipecah: memotong salah satu dari dua blok yang
    berbagi baris membuat pasangannya menggantung sendirian tanpa alasan yang
    terlihat pembaca.
    """
    if sisa <= 0 or len(baris_blok["blok"]) != 1:
        return None, None
    b = baris_blok["blok"][0]
    if not b.get("baris_tinggi"):
        return None, None
    kepala, ekor = _pecah_blok_tim(b, sisa)
    if kepala is None:
        return None, None
    return ({"blok": [kepala], "tinggi": kepala["tinggi"],
             "jarak": baris_blok["jarak"]},
            {"blok": [ekor], "tinggi": ekor["tinggi"],
             "jarak": baris_blok["jarak"]})


def sisa_ruang(rencana, indeks_halaman, sehalaman=None) -> float:
    """Tinggi yang MASIH KOSONG pada satu lembar rencana.

    Dipakai memberi jatah lebih kepada daftar yang dapat memanjang: kertas
    yang tersisa lebih berguna diisi baris data daripada dibiarkan putih.
    """
    jatah = (lkl.TINGGI_ISI_SEHALAMAN - lkl.CADANGAN_TATA_LETAK
             if sehalaman is None else float(sehalaman))
    hal = (rencana or {}).get("halaman") or []
    if not (0 <= indeks_halaman < len(hal)):
        return 0.0
    isi = hal[indeks_halaman]
    terpakai = sum(b["tinggi"] for b in isi) + sum(b["jarak"] for b in isi[1:])
    return max(0.0, jatah - terpakai)
