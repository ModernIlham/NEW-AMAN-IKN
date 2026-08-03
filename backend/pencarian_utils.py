"""PENCARIAN TEKS BEBAS — satu semantik untuk seluruh aplikasi.

MASALAH YANG DIPERBAIKI
----------------------
Semua daftar (aset, persediaan, surat) dulu memperlakukan kata kunci sebagai
SATU FRASA UTUH yang harus muncul persis di salah satu field:

    "meja jati"    → regex /meja\\ jati/  → TIDAK cocok "Meja Rapat Kayu Jati"
    "lenovo gudang"→ regex /lenovo\\ gudang/ → tak pernah cocok, karena "lenovo"
                     ada di nama barang sedangkan "gudang" ada di lokasi.

Akibatnya makin banyak kata yang diketik, makin sering hasilnya kosong —
persis kebalikan dari harapan pengguna.

SEMANTIK BARU (dipakai SEMUA modul)
-----------------------------------
Kata kunci dipecah per spasi. **SETIAP kata wajib ada** (AND), tetapi boleh
berada di **field mana pun** (OR antar-field). Jadi:

    "meja jati"     → (meja di salah satu field) DAN (jati di salah satu field)
    "lenovo gudang" → cocok: "lenovo" di asset_name, "gudang" di location.

Menambah kata selalu MEMPERSEMPIT hasil, tak pernah membuatnya kosong secara
tak terduga. Ini juga menyamakan perilaku dengan Meilisearch yang di-set
`matchingStrategy: "all"` — jadi hasil tak berubah-ubah tergantung Meili
hidup atau mati.

Nilai pengguna selalu di-escape (`re.escape`) sehingga diperlakukan literal —
input seperti `(a+)+$` atau `[` tak bisa meledak jadi ReDoS/regex tak sah.
"""
import re

# Batas jumlah kata yang diproses. Tanpa batas, tempelan paragraf panjang
# membangun puluhan klausa $or dan membuat satu kueri jadi sangat mahal.
MAKS_KATA = 8

# Panjang minimum SELURUH kata kunci (bukan per kata). Di bawah ini pencarian
# diabaikan: regex infix tak bisa memakai index, dan kueri 1 huruf memindai
# hampir seluruh koleksi tanpa menyaring apa pun.
MIN_PANJANG = 2


def pecah_kata(search: str) -> list:
    """Pecah kata kunci jadi daftar kata (maks MAKS_KATA, tanpa duplikat).

    Mengembalikan [] bila kata kunci kosong atau lebih pendek dari MIN_PANJANG
    — pemanggil memperlakukan itu sebagai 'tanpa pencarian'.
    """
    teks = (search or "").strip()
    if len(teks) < MIN_PANJANG:
        return []
    kata = []
    for k in teks.split():
        if k and k not in kata:
            kata.append(k)
        if len(kata) >= MAKS_KATA:
            break
    return kata


def rx(term: str) -> dict:
    """Pencocokan substring case-insensitive yang memperlakukan input sebagai
    LITERAL (re.escape)."""
    return {"$regex": re.escape(term), "$options": "i"}


def rx_awalan(term: str) -> dict:
    """Seperti `rx` tetapi berjangkar di AWAL nilai — untuk kode berstruktur
    (mis. kode barang 16 digit) yang dicari dari digit pertama."""
    return {"$regex": f"^{re.escape(term)}", "$options": "i"}


def klausa_teks(search: str, fields, fields_awalan=(), tambahan=None) -> dict:
    """Bangun klausa Mongo untuk pencarian teks bebas multi-kata.

    - `fields`        : field yang dicocokkan secara substring.
    - `fields_awalan` : field yang dicocokkan dari awal nilai bila katanya
                        berupa angka (kode berstruktur seperti kode_barang).
    - `tambahan`      : fungsi opsional `(kata) -> list[dict]` untuk klausa
                        khusus per kata (mis. pencocokan harga numerik).

    Mengembalikan `{}` bila kata kunci tak layak dicari (kosong/terlalu pendek),
    sehingga pemanggil bisa langsung `query.update(klausa_teks(...))`.
    """
    kata = pecah_kata(search)
    if not kata:
        return {}

    def per_kata(k):
        cabang = [{f: rx(k)} for f in fields]
        for f in fields_awalan:
            cabang.append({f: rx_awalan(k) if k.isdigit() else rx(k)})
        if tambahan:
            cabang.extend(tambahan(k) or [])
        return cabang

    if len(kata) == 1:
        return {"$or": per_kata(kata[0])}
    # Setiap kata wajib ada (AND), boleh di field berbeda-beda (OR di dalam).
    return {"$and": [{"$or": per_kata(k)} for k in kata]}
