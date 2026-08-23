"""Tautan baris pengadaan → master persediaan yang SUDAH TERDAFTAR. MURNI.

MASALAH YANG DIPECAHKAN
=======================

Baris barang di register Pengadaan menyimpan `kode` sebagai TEKS BEBAS. Saat
tombol "Daftarkan ke Persediaan" ditekan, `daftarkan_persediaan` menebak
master mana yang dimaksud: kode 16 digit dicocokkan persis, kode 10 digit
dicocokkan per-awalan DITAMBAH nama barang yang sama persis. Tebakan itu
sudah dua kali salah arah (riwayat lengkap ada di komentar endpoint-nya):
mencocokkan persis membuat master baru setiap pembelian, mencocokkan awalan
saja membuang stok ke kartu barang yang salah.

Tebakan yang paling baik pun masih tebakan. "Kertas HVS A4" dan "Kertas HVS
A4 80gr" adalah barang yang SAMA di gudang tetapi nama yang BERBEDA bagi
regex — dan hasilnya dua kartu stok untuk satu tumpukan kertas, yang baru
ketahuan saat opname.

Jalan keluarnya bukan regex yang lebih pintar, melainkan MENGHAPUS tebakannya:
operator memilih langsung dari daftar persediaan yang sudah tercatat di
inventarisasi, dan pilihan itu disimpan sebagai `psd_master_id` di baris.
Master persediaan selalu ber-kode 16 digit (10 digit kodefikasi + 6 digit
nomor urut yang dibuatkan `create_persediaan`), jadi memilih dari daftar
sekaligus menegakkan "kode 16 digit" yang diminta pemilik.

BATAS TANGGUNG JAWAB MODUL INI
==============================

Murni: tanpa DB, tanpa I/O, tanpa waktu. Pemanggil yang mengambil dokumen
master dari Mongo (ber-scope satker) lalu menyerahkannya ke sini sebagai dict
biasa. Modul ini hanya menjawab tiga pertanyaan:

1. Baris ini memang barang persediaan? (`butuh_taut_persediaan`)
2. Boleh kah baris ini ditautkan ke master itu? (`validate_taut_persediaan`)
3. Baris mana yang akan MENEBAK lagi karena belum ditautkan?
   (`peringatan_persediaan`)

Menautkan TIDAK memaksa: baris tanpa tautan tetap boleh diposting seperti
sebelumnya — hanya saja operator diberi tahu lebih dulu bahwa sistem akan
membuat master baru. Memaksa akan mengunci data lama yang sudah telanjur
ada, dan register ini adalah pendamping SAKTI, bukan gerbangnya.
"""

from lpb_utils import is_persediaan
from persediaan_utils import KODE_PENUH_LEN, KODE_PREFIX_LEN


def butuh_taut_persediaan(kode) -> bool:
    """Baris ber-`kode` ini bermuara ke kartu stok persediaan?

    Sekadar nama yang jujur untuk `is_persediaan`: yang menentukan bukan
    "16 digit atau bukan", melainkan GOLONGANNYA (digit pertama '1'). Baris
    10 digit pun barang persediaan — justru baris itulah yang paling butuh
    dipilihkan masternya, karena 6 digit pembedanya belum ada.
    """
    return is_persediaan(kode)


def kode_bersih(kode) -> str:
    """Kode barang tanpa spasi pinggir; non-string ditoleransi."""
    return str(kode or "").strip()


def validate_taut_persediaan(kode, master) -> list:
    """Daftar alasan baris ber-`kode` TIDAK boleh ditautkan ke `master`.

    Kosong = boleh. `master` adalah dokumen master persediaan (dict) atau
    None bila pemanggil tak menemukannya dalam lingkup satker — keduanya
    ditangani di sini supaya pemanggil tak perlu berpendapat.
    """
    k = kode_bersih(kode)
    errs = []
    if not butuh_taut_persediaan(k):
        errs.append(
            "Tautan barang persediaan hanya untuk kode golongan 1 "
            "(persediaan). Kode aset tetap ditautkan lewat 'Tautkan ke Aset'.")
        return errs
    if not master:
        errs.append(
            "Barang persediaan terdaftar tidak ditemukan pada satker ini — "
            "pilih ulang dari daftar persediaan.")
        return errs
    km = kode_bersih(master.get("kode_barang"))
    if not km:
        errs.append("Barang persediaan terpilih tidak punya kode barang.")
        return errs
    # Kode master boleh LEBIH PANJANG dari kode baris: itu justru kasus
    # normalnya — operator mengetik 10 digit kodefikasi, lalu memilih salah
    # satu barang terdaftar di bawahnya. Yang ditolak adalah kode yang
    # menunjuk barang LAIN (awalannya sudah berbeda).
    if km != k and not (len(k) == KODE_PREFIX_LEN and km.startswith(k)):
        errs.append(
            f"Kode baris ({k or '-'}) tidak cocok dengan kode barang "
            f"terdaftar ({km}). Perbaiki kodenya atau pilih barang lain.")
    return errs


def kode_setelah_taut(master) -> str:
    """Kode 16 digit yang HARUS dipakai baris setelah ditautkan.

    Baris mengadopsi kode master, bukan sebaliknya. Dengan begitu LPB, BAST,
    dan kartu stok mencetak kode yang sama persis, dan baris 10 digit yang
    ditautkan otomatis naik jadi 16 digit sebagaimana diminta.
    """
    return kode_bersih((master or {}).get("kode_barang"))


def _uraian(row) -> str:
    return str(row.get("uraian") or "").strip() or "(tanpa uraian)"


def peringatan_persediaan(barang) -> list:
    """Baris persediaan mana yang masih akan DITEBAK masternya?

    → [{index, kode, uraian, sebab, pesan}] dengan `sebab`:
      - `belum_tertaut` — kode persediaan tanpa `psd_master_id`
      - `kode_pendek`   — belum tertaut DAN kodenya baru 10 digit, jadi
                          6 digit nomor urut akan dikarang sistem

    Baris yang sudah punya `psd_item_id` (sudah masuk stok) dan baris yang
    sudah telanjur jadi aset dilewati: keduanya tak akan diposting lagi.
    """
    keluar = []
    for i, row in enumerate(barang or []):
        if not isinstance(row, dict):
            continue
        kode = kode_bersih(row.get("kode"))
        if not butuh_taut_persediaan(kode):
            continue
        if str(row.get("psd_item_id") or "").strip():
            continue
        if str(row.get("asset_id") or "").strip():
            continue
        if str(row.get("psd_master_id") or "").strip():
            continue
        pendek = len(kode) < KODE_PENUH_LEN
        pesan = (
            f"{_uraian(row)} ({kode}) belum dipilih dari daftar persediaan "
            "terdaftar. Bila diteruskan, sistem mencocokkan sendiri lewat "
            "kode + nama barang; bila meleset, master BARU dibuat dan stok "
            "jenis yang sama pecah jadi dua kartu.")
        if pendek:
            pesan += (
                f" Kodenya juga baru {len(kode)} digit — {KODE_PENUH_LEN} "
                "digit penuhnya akan dibuatkan sistem, bukan mengikuti yang "
                "sudah tercatat.")
        keluar.append({"index": i, "kode": kode, "uraian": _uraian(row),
                       "sebab": "kode_pendek" if pendek else "belum_tertaut",
                       "pesan": pesan})
    return keluar
