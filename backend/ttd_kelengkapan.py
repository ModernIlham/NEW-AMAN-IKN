"""Kelengkapan pembubuhan tanda tangan elektronik — helper MURNI.

MASALAH YANG DIPECAHKAN
=======================

Laporan pemilik: *"ketika salah satu penanda tangan menandatangani hanya 1
lembar yang ia tanda tangani dan sudah memencet tombol bubuhkan, sehingga
lembaran yang ada tanda tangan dia lagi di lembar sebelum atau selanjutnya
tidak ditandatangani."*

Modul e-sign SUDAH mampu membubuhkan satu orang di banyak halaman (tombol
"Tanda tangan lagi" → `posisi_ttd_lain`). Yang tidak ada adalah **ukuran
kelengkapannya**: tak satu pun bagian sistem tahu berapa tempat yang
SEHARUSNYA diteken orang itu. Karena itu sistem tak pernah bisa berkata
"masih kurang" — ia hanya menerima apa pun yang dikirim, menutup link (sekali
pakai), dan dokumen terbit dengan lembar yang kosong.

Akibatnya berat sebelah: kelalaian sekejap satu orang memaksa SELURUH
penanda tangan mengulang dari awal, karena satu-satunya pemulihan yang ada
adalah membatalkan permintaan dan menerbitkannya lagi.

KEPUTUSAN
=========

Kelengkapan DIDEKLARASIKAN pemilik dokumen saat permintaan dibuat
(`jumlah_ttd` per penanda tangan), lalu DITEGAKKAN di dua tempat: layar
menolak mengirim sebelum lengkap, dan server menolak kiriman yang kurang.

Ditegakkan di server pula — bukan hanya di layar — karena ini aturan
keutuhan dokumen, bukan sekadar kenyamanan: link e-sign dibuka di peramban
tamu yang tak terkendali, dan kiriman yang kurang TIDAK BISA diperbaiki
sesudahnya tanpa mengulang semuanya.

Yang ditegakkan hanya BATAS BAWAH. Membubuhkan lebih banyak dari yang
dideklarasikan adalah tindakan sengaja (orangnya menekan "Tanda tangan lagi"
sekali lagi) dan tetap terlihat di dokumen; menolaknya hanya akan
mengembalikan masalah yang sama dari arah sebaliknya — orang yang dipaksa
mengulang karena melakukan hal yang benar.

MURNI: tanpa DB, tanpa I/O.
"""

# Sejalan dengan `MAKS_PEMBUBUHAN` di routes/ttd.py — satu orang boleh diminta
# meneken sampai sebanyak itu pada satu dokumen.
MAKS_TTD_PER_ORANG = 20


def normalisasi_jumlah_ttd(v) -> int:
    """Berapa tempat yang wajib diteken satu orang; selalu 1..MAKS.

    Toleran terhadap nilai apa pun yang datang dari form/JSON — kosong, teks,
    pecahan, negatif, NaN. Yang tak terbaca jatuh ke 1, yaitu perilaku sistem
    SEBELUM field ini ada: permintaan lama tanpa `jumlah_ttd` harus tetap
    berjalan persis seperti dulu, bukan mendadak ditolak.
    """
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return 1
    if n < 1:
        return 1
    return min(n, MAKS_TTD_PER_ORANG)


def jumlah_pembubuhan(posisi, posisi_lain) -> int:
    """Berapa tempat yang BENAR-BENAR dikirim penanda tangan.

    `posisi` adalah pembubuhan yang sedang diatur saat tombol ditekan;
    `posisi_lain` yang sudah disimpan lewat "Tanda tangan lagi". Keduanya
    dihitung bersama karena keduanya sama-sama dibubuhkan ke dokumen.
    """
    n = 1 if posisi else 0
    if isinstance(posisi_lain, (list, tuple)):
        n += len(posisi_lain)
    return n


def kurang_pembubuhan(jumlah_wajib, posisi, posisi_lain) -> int:
    """Berapa tempat yang MASIH kurang; 0 = sudah lengkap."""
    return max(0, normalisasi_jumlah_ttd(jumlah_wajib)
               - jumlah_pembubuhan(posisi, posisi_lain))


def pesan_kurang(jumlah_wajib, posisi, posisi_lain) -> str:
    """Penolakan yang MENYEBUT jalan keluarnya; "" bila sudah lengkap.

    Penolakan yang hanya berkata "kurang" akan membuat orang menekan tombol
    yang sama berulang kali. Yang dibutuhkan adalah nama tombol yang harus
    ditekan dan berapa kali lagi.
    """
    kurang = kurang_pembubuhan(jumlah_wajib, posisi, posisi_lain)
    if not kurang:
        return ""
    wajib = normalisasi_jumlah_ttd(jumlah_wajib)
    sudah = jumlah_pembubuhan(posisi, posisi_lain)
    return (f"Dokumen ini menuntut {wajib} tanda tangan dari Anda, baru "
            f"{sudah} yang ditempatkan. Tekan \"Tanda tangan lagi\", pindah "
            f"ke halaman berikutnya, dan tempatkan {kurang} lagi sebelum "
            "membubuhkan. Jika angka permintaan memang berlebih, periksa "
            "seluruh dokumen lalu gunakan deklarasi \"tidak ada area TTD "
            "saya lagi\"; operator/admin satker akan memvalidasinya.")


def pesan_deklarasi_tanpa_area(jumlah_wajib, posisi, posisi_lain,
                               deklarasi=False, ada_dokumen=True) -> str:
    """Validasi jalan keluar saat angka deklarasi pemilik terlalu besar.

    ``""`` berarti kiriman boleh masuk ke antrean validator. Deklarasi hanya
    sah bila ada PDF yang benar-benar dapat diperiksa dan sedikitnya satu
    pembubuhan sudah ditempatkan; ia tidak boleh menjadi jalan pintas untuk
    mengirim tanda tangan tanpa menunjuk satu area pun.
    """
    kurang = kurang_pembubuhan(jumlah_wajib, posisi, posisi_lain)
    if not kurang:
        return ""
    if not deklarasi:
        return pesan_kurang(jumlah_wajib, posisi, posisi_lain)
    if not ada_dokumen:
        return ("Deklarasi tanpa area hanya tersedia untuk dokumen PDF yang "
                "dapat diperiksa halaman demi halaman")
    sudah = jumlah_pembubuhan(posisi, posisi_lain)
    if sudah < 1:
        return ("Tempatkan sedikitnya satu tanda tangan Anda sebelum "
                "menyatakan tidak ada area tanda tangan lainnya")
    return ""
