"""Penyusun tata letak laporan gabungan — helper MURNI, tanpa I/O dan tanpa DB.

Permintaan pemilik: *"perkategori dan lokasi juga buat jangan dibatasi biarkan
saja mengalir dan buat smart mengatur dan berbagi posisi dengan bagian lainnya
hingga benar benar 1 kertas penuh tidak bisa menampung tataletak yang ada lagi,
baru pindah lanjut kekertas berikutnya."*

Sebelumnya panel analisis dipangkas `most_common(10)` dan halaman-halaman lain
dipaginasi dengan TETAPAN (`8 kartu per halaman`). Keduanya keliru dari arah
yang berlawanan:

- **Pemangkasan membuang data.** Satker dengan 40 lokasi hanya menampilkan 10,
  dan tak ada satu pun tanda bahwa 30 sisanya ada. Laporan yang memangkas diam-
  diam lebih buruk daripada laporan yang panjang.
- **Tetapan salah di kedua arah.** Terlalu besar → isi terpotong diam-diam oleh
  `overflow: hidden`. Terlalu kecil → separuh kertas kosong sementara halaman
  berikutnya dibuka untuk tiga baris. Tetapan hanya benar untuk satu ukuran
  data, dan data tak pernah satu ukuran.

Modul ini menggantikan keduanya dengan **pengukuran**: tiap panel menghitung
tingginya sendiri dalam piksel, panel yang terlalu panjang dipecah, lalu
potongannya dijatah ke dua kolom halaman sampai kertasnya benar-benar penuh.

Tiga keputusan yang membentuk modul ini:

1. **Tingginya dihitung di Python, bukan ditebak di Jinja.** Aritmetika di
   dalam template tak dapat diuji unit, dan kekeliruannya baru terlihat sebagai
   isi yang hilang di halaman ke sekian — bentuk kegagalan yang paling sulit
   diperhatikan.

2. **Panel yang lebih panjang dari satu kolom DIPECAH, bukan dipangkas.**
   Potongan kedua dan seterusnya membawa judul yang sama dengan tanda
   "(lanjutan)", sehingga pembacanya tahu daftarnya belum habis. Memangkasnya
   akan mengembalikan cacat yang justru sedang diperbaiki.

3. **Kolom KIRI diisi sampai penuh, baru kolom kanan.** Halaman dua kolom
   dibaca kiri dari atas ke bawah, lalu kanan — seperti koran. Menaruh
   potongan di kolom yang sedang terpendek memang membuat tingginya rata,
   tetapi MERUSAK urutan bacanya: pada percobaan pertama modul ini,
   "Per Lokasi (lanjutan)" berakhir di kolom kiri sementara 42 baris
   pertamanya ada di kolom kanan — lanjutan yang dibaca lebih dulu daripada
   yang dilanjutkannya.

   Mengisi kolom secara berurutan tetap memenuhi "berbagi posisi": keduanya
   sama-sama terisi sampai batas, hanya saja urutannya mengikuti cara orang
   membaca.
"""

#: Tinggi kolom isi satu lembar A4 (1123px) setelah dikurangi kop, kaki, dan
#: padding `.hal-isi`. Diukur dari template, bukan ditebak: kop 60 + kaki 30 +
#: padding 32 = 122, sisanya 1001. Disisakan 20px sebagai jaga-jaga terhadap
#: pembulatan pengukur teks peramban.
TINGGI_KOLOM = 981

#: Tinggi blok judul bagian pada halaman PERTAMA (judul + keterangan) dan pada
#: halaman lanjutannya. Halaman pertama membawa keterangan bagian, jadi ia
#: memuat lebih sedikit.
TINGGI_JUDUL_AWAL = 78
TINGGI_JUDUL_LANJUT = 62

#: Bagian tetap tinggi sebuah panel: padding atas+bawah, garis, dan judulnya.
TINGGI_PANEL_TETAP = 55
#: Tinggi satu baris batang (`.bar-baris`: 13px + margin 4px).
TINGGI_BARIS = 17
#: Jarak antar panel yang bertumpuk di kolom yang sama.
JARAK_PANEL = 13

#: Panel dengan baris lebih sedikit dari ini tak akan pernah dipecah — ekor
#: satu-dua baris di halaman berikutnya membuang lebih banyak ruang daripada
#: yang dihematnya, dan terbaca sebagai kekeliruan cetak.
MIN_BARIS_PECAH = 4


def tinggi_panel(n_baris: int) -> int:
    """Tinggi sebuah panel berisi `n_baris` baris batang, dalam piksel."""
    return TINGGI_PANEL_TETAP + TINGGI_BARIS * max(0, n_baris)


def baris_muat(tinggi_tersedia: int) -> int:
    """Berapa baris batang yang muat dalam ruang setinggi `tinggi_tersedia`."""
    sisa = tinggi_tersedia - TINGGI_PANEL_TETAP
    return sisa // TINGGI_BARIS if sisa > 0 else 0


def _potong(panel, maks_baris):
    """Pecah satu panel menjadi potongan-potongan yang muat satu kolom.

    Potongan kedua dan seterusnya ditandai `lanjutan` supaya judulnya dapat
    menyatakan bahwa daftarnya belum habis (lihat #2).
    """
    baris = panel.get("baris") or []
    if not baris:
        return [{**panel, "baris": [], "lanjutan": False,
                 "tinggi": tinggi_panel(0)}]
    if maks_baris <= 0:
        maks_baris = 1
    keluar = []
    for i in range(0, len(baris), maks_baris):
        bagian = baris[i:i + maks_baris]
        keluar.append({**panel, "baris": bagian, "lanjutan": i > 0,
                       "tinggi": tinggi_panel(len(bagian))})
    return keluar


def susun(panel_list, tinggi_kolom=TINGGI_KOLOM,
          judul_awal=TINGGI_JUDUL_AWAL, judul_lanjut=TINGGI_JUDUL_LANJUT):
    """Susun panel menjadi halaman dua kolom yang terisi penuh.

    `panel_list` adalah `[{"judul", "jenis", "baris": [...]}, ...]`.
    Kembalikan `[{"kiri": [...], "kanan": [...]}, ...]` — satu entri per
    halaman, dengan tiap potongan membawa `tinggi` dan `lanjutan`.

    Halaman pertama menyediakan ruang lebih sedikit karena membawa judul
    bagian beserta keterangannya.
    """
    SISI = ("kiri", "kanan")
    halaman = []
    isi = None            # {"kiri": [...], "kanan": [...]}
    sisi = 0              # kolom yang sedang diisi
    tinggi = 0            # tinggi terpakai kolom itu

    def buka_halaman():
        nonlocal isi, sisi, tinggi
        tersedia = tinggi_kolom - (judul_awal if not halaman else judul_lanjut)
        isi = {"kiri": [], "kanan": []}
        sisi, tinggi = 0, 0
        halaman.append(isi)
        return tersedia

    tersedia = buka_halaman()

    # Antrean, bukan perulangan bersarang: sebuah potongan yang tak muat di
    # sisa kolom dapat dipecah lagi, dan ekornya harus diproses seperti
    # potongan biasa — termasuk kemungkinan dipecah sekali lagi di halaman
    # berikutnya.
    antrean = []
    for panel in panel_list:
        antrean += _potong(panel, baris_muat(tersedia))
    antrean.reverse()

    while antrean:
        bagian = antrean.pop()
        jarak = JARAK_PANEL if tinggi else 0
        ruang = tersedia - tinggi - jarak
        if bagian["tinggi"] <= ruang:
            isi[SISI[sisi]].append(bagian)
            tinggi += jarak + bagian["tinggi"]
            continue

        # Tak muat utuh. Sebelum pindah kolom, coba isi sisa ruangnya — inilah
        # "sampai kertasnya benar-benar penuh". Tetapi hanya bila kepala DAN
        # ekornya sama-sama layak: potongan satu-dua baris di ujung kolom
        # membuang lebih banyak ruang (judulnya sendiri 55px) daripada yang
        # dihematnya, dan terbaca sebagai kekeliruan cetak.
        muat = baris_muat(ruang)
        sisa_baris = len(bagian["baris"]) - muat
        if muat >= MIN_BARIS_PECAH and sisa_baris >= MIN_BARIS_PECAH:
            isi[SISI[sisi]].append({**bagian, "baris": bagian["baris"][:muat],
                                    "tinggi": tinggi_panel(muat)})
            tinggi += jarak + tinggi_panel(muat)
            antrean.append({**bagian, "baris": bagian["baris"][muat:],
                            "lanjutan": True,
                            "tinggi": tinggi_panel(sisa_baris)})
            continue

        if tinggi == 0:
            # Kolomnya masih kosong dan isinya tetap tak muat: taruh apa
            # adanya. Tanpa cabang ini perulangannya tak pernah berhenti.
            isi[SISI[sisi]].append(bagian)
            tinggi = bagian["tinggi"]
            continue

        antrean.append(bagian)
        if sisi == 0:
            sisi, tinggi = 1, 0          # lanjut ke kolom kanan
        else:
            tersedia = buka_halaman()    # kertas berikutnya

    # Halaman terakhir bisa saja kosong bila panel_list kosong.
    if halaman and not halaman[-1]["kiri"] and not halaman[-1]["kanan"]:
        halaman.pop()
    return halaman


def panel_batang(judul, baris, warna, kolom_nilai="count"):
    """Bentuk baku sebuah panel batang untuk `susun()`.

    `kolom_nilai` memilih apa yang tercetak di ujung kanan tiap baris —
    `count` untuk cacah, `val_fmt` untuk nilai rupiah.
    """
    return {"judul": judul, "warna": warna, "kolom_nilai": kolom_nilai,
            "baris": list(baris or [])}
