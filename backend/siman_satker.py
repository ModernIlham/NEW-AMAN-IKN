"""Identitas satker SIMAN: kecocokan utuh, tanpa substring atau wildcard.

Kode lokasi BMN berformat BA(3), eselon(2), wilayah(4), satker(6),
subsatker(3), kewenangan(2). Jadi ``126011600691778000KP`` bersatker
``691778``; angka ``160069`` yang kebetulan terkandung bukan identitasnya.
Modul ini murni; kewenangan membaca/menulis tetap diperiksa pemanggil.
"""

import math
import re


_ENAM = re.compile(r"^[0-9]{6}$")
_LENGKAP = re.compile(r"^[0-9]{18}[A-Z0-9]{2}$")
_EXCEL_BULAT = re.compile(r"^([0-9]+)\.0+$")
_DESIMAL = re.compile(r"^[+-]?[0-9]+\.[0-9]+$")
_EKSPONEN = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)[eE][+-]?[0-9]+$")


def norm_kode_satker(nilai) -> str:
    """Rapikan kode6/full20; identitas lama dipertahankan persis setelah trim.

    Excel kadang memberikan kode enam digit sebagai float atau ``'001234.0'``.
    Artefak itu dibuang sebelum pemisah, agar tidak menambahkan digit nol.
    Float panjang/notasi eksponen ditolak: pembulatan Excel sudah dapat
    menghilangkan identitas dan tidak bisa diperbaiki dengan menebak.
    String digit panjang tetap dipertahankan persis. Pemisah/huruf hanya
    dirapikan bila hasilnya berbentuk kode enam digit atau kode penuh yang
    sah: ID lama ``satker-A`` dan ``SATKERA`` tetap dua identitas berbeda.
    """
    if nilai is None or isinstance(nilai, bool):
        return ""
    if isinstance(nilai, float):
        if not math.isfinite(nilai) or not nilai.is_integer() or not 0 <= nilai <= 999999:
            return ""
        return str(int(nilai))
    if isinstance(nilai, int):
        return str(nilai) if nilai >= 0 else ""
    teks = str(nilai).strip()
    excel = _EXCEL_BULAT.fullmatch(teks)
    if excel:
        return excel[1] if len(excel[1]) <= 6 else ""
    if _DESIMAL.fullmatch(teks) or _EKSPONEN.fullmatch(teks):
        return ""
    kandidat = re.sub(r"[^0-9A-Za-z]", "", teks).upper()
    return kandidat if _ENAM.fullmatch(kandidat) or _LENGKAP.fullmatch(kandidat) else teks


def kode_satker_sama(kode_a, kode_b) -> bool:
    """Identitas sama; enam digit hanya dicocokkan ke segmen satker penuh.

    Dua kode penuh yang berbeda tetap berbeda, termasuk bila hanya wilayah,
    subsatker, atau kewenangannya berbeda. Kode lama nonkosong hanya cocok
    persis setelah trim, bukan sebagai potongan kode lain atau alias case.
    """
    a, b = norm_kode_satker(kode_a), norm_kode_satker(kode_b)
    if not a or not b:
        return False
    if a == b:
        return True
    if _ENAM.fullmatch(a) and _LENGKAP.fullmatch(b):
        return a == b[9:15]
    if _LENGKAP.fullmatch(a) and _ENAM.fullmatch(b):
        return a[9:15] == b
    return False


def identitas_satker(kode, kode_lengkap="") -> str:
    """Pilih identitas paling lengkap; dua isian yang bertentangan ditolak.

    Tanpa kode lengkap, kode induk lama tetap dapat dipakai secara persis.
    Isian lengkap tidak pernah menutupi kode enam digit yang berbeda atau
    kode penuh lain. Kosong berarti identitas tidak dapat dipastikan.
    """
    akar, lengkap = norm_kode_satker(kode), norm_kode_satker(kode_lengkap)
    # Isian terisi yang gagal dinormalisasi tidak boleh diabaikan lalu jatuh
    # kembali ke identitas yang lebih longgar.
    if str(kode or "").strip() and not akar:
        return ""
    if str(kode_lengkap or "").strip() and not lengkap:
        return ""
    if not lengkap:
        return akar
    if not akar or akar == lengkap:
        return lengkap
    if _LENGKAP.fullmatch(lengkap) and _ENAM.fullmatch(akar) and kode_satker_sama(akar, lengkap):
        return lengkap
    return ""


class IndeksSatker:
    """Resolusi kode enam digit hanya jika satu identitas penuh diketahui.

    Jika dua kode penuh berbagi enam digit, keduanya tetap dapat dicocokkan
    secara utuh, tetapi bentuk enam digitnya ambigu dan menghasilkan ``''``.
    Kode enam digit tanpa padanan penuh tetap menjadi identitas enam digit.
    """

    def __init__(self, kode_iterable):
        self._lengkap_per_akar = {}
        for nilai in kode_iterable or ():
            kode = norm_kode_satker(nilai)
            if _LENGKAP.fullmatch(kode):
                self._lengkap_per_akar.setdefault(kode[9:15], set()).add(kode)

    def kunci(self, nilai) -> str:
        kode = norm_kode_satker(nilai)
        if not kode or not _ENAM.fullmatch(kode):
            return kode
        lengkap = self._lengkap_per_akar.get(kode, set())
        if len(lengkap) > 1:
            return ""
        return next(iter(lengkap)) if lengkap else kode
