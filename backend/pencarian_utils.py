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


# Pemisah yang lazim dipakai/dilewatkan orang saat mengetik kode & angka:
# titik, koma, tanda hubung, garis miring, dan spasi.
_PEMISAH = r"[.,\-/\s]"
# Batas panjang deret angka yang diberi pola longgar (kode BMN terpanjang jauh
# di bawah ini; pembatas ini menjaga panjang regex tetap wajar).
_MAKS_DIGIT_LONGGAR = 24


def digit_saja(term: str) -> str:
    """Ambil hanya angkanya: '3.10.01.02.001' → '3100102001'."""
    return re.sub(r"\D", "", term or "")


def rx_angka_longgar(term: str):
    """Pola untuk ANGKA/KODE yang boleh ditulis dengan pemisah berbeda.

    Petugas mengetik kode barang tanpa titik (`3100102001`), dengan titik tak
    lengkap (`310.01.02`), atau memakai titik desimal padahal datanya koma
    (`1.5` vs `1,5`). Regex literal menolak semuanya. Pola ini mencocokkan
    deret angkanya dengan pemisah apa pun (atau tanpa pemisah) di antaranya.

    Mengembalikan None bila katanya bukan deret angka yang layak.
    """
    digit = digit_saja(term)
    if len(digit) < 2 or len(digit) > _MAKS_DIGIT_LONGGAR:
        return None
    # d1 [pemisah]* d2 [pemisah]* d3 … — linier, tanpa kuantifier bersarang.
    pola = (_PEMISAH + "*").join(digit)
    return {"$regex": pola, "$options": "i"}


def nilai_angka(term: str):
    """Ubah kata jadi angka bila memang murni angka (dengan/ tanpa pemisah
    ribuan Indonesia). None bila bukan angka."""
    bersih = (term or "").replace(".", "").replace(",", "").strip()
    if not bersih or not bersih.isdigit():
        return None
    try:
        return int(bersih)
    except ValueError:
        return None


def klausa_teks(search: str, fields, fields_awalan=(), tambahan=None,
                fields_kode=(), fields_angka=()) -> dict:
    """Bangun klausa Mongo untuk pencarian teks bebas multi-kata.

    - `fields`        : field yang dicocokkan secara substring.
    - `fields_awalan` : field yang dicocokkan dari awal nilai bila katanya
                        berupa angka (kode berstruktur seperti kode_barang).
    - `tambahan`      : fungsi opsional `(kata) -> list[dict]` untuk klausa
                        khusus per kata (mis. pencocokan harga numerik).
    - `fields_kode`   : field yang juga dicocokkan dengan POLA ANGKA LONGGAR —
                        kode/nomor yang boleh diketik dengan pemisah berbeda.
    - `fields_angka`  : field yang nilainya bisa tersimpan sebagai ANGKA
                        (bukan teks). `$regex` tak pernah cocok ke non-string,
                        jadi ditambah pembandingan kesamaan numerik.

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
        longgar = rx_angka_longgar(k)
        if longgar:
            cabang.extend({f: longgar} for f in fields_kode)
        angka = nilai_angka(k)
        if angka is not None:
            cabang.extend({f: angka} for f in fields_angka)
        if tambahan:
            cabang.extend(tambahan(k) or [])
        return cabang

    if len(kata) == 1:
        return {"$or": per_kata(kata[0])}
    # Setiap kata wajib ada (AND), boleh di field berbeda-beda (OR di dalam).
    return {"$and": [{"$or": per_kata(k)} for k in kata]}
