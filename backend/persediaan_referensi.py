"""Referensi barang persediaan 16 digit ala SAKTI — bagian murni (tanpa DB).

LATAR. Di SAKTI, tiap barang persediaan diidentifikasi KODE 16 DIGIT:
10 digit kode barang (kodefikasi BMN, mis. `1010301001` = alat tulis) + 6 digit
KODE URUT yang lahir dari pendaftaran barang di satker itu sendiri
(mis. `000001` = "Highlighter / Stabilo - Biru (Pack)"). Karena kode urut
tumbuh dari transaksi masing-masing satker, DAFTARNYA BERBEDA ANTAR SATKER dan
BERUBAH SEIRING WAKTU — dua fakta yang membuat referensi ini tak boleh
diperlakukan sebagai daftar statis bersama.

Sumber kebenarannya adalah laporan SAKTI "UC_PER032 — Referensi Tabel Barang
Persediaan" (PDF) yang diunduh operator per satker. Modul ini mem-parse teks
hasil ekstraksi PDF itu menjadi baris terstruktur + identitas UAKPB-nya,
supaya lapisan route tinggal meng-upsert per satker.

Bentuk baris pada teks hasil ekstraksi (pypdf):

    000001 1010301001 Pack Highlighter / Stabilo - Biru (Pack)
    ^urut6 ^kode10    ^satuan ^deskripsi...

Header tiap halaman memuat:

    UAKPB : DEPUTI ...
    KODE UAKPB : 126.01.1600.691778.000.KP
                              ^^^^^^ kode satker 6 digit
"""
import re

__all__ = [
    "kode16", "pecah_kode16", "parse_teks_uc_per032", "rencana_sinkron",
]

# Baris data: urut 6 digit, kode 10 digit, satuan satu token, sisa = deskripsi.
# Satuan di SAKTI selalu satu kata (Pcs, Pack, Box, Set, Rim, Botol, Buah, …).
_POLA_BARIS = re.compile(r"^(\d{6})\s+(\d{10})\s+(\S+)\s+(.+)$")

# KODE UAKPB : 126.01.1600.691778.000.KP → ambil segmen 6 digit (kode satker).
_POLA_UAKPB = re.compile(r"KODE\s+UAKPB\s*:?\s*([0-9.]+[0-9A-Z.]*)")


def kode16(kode_barang: str, kode_urut: str) -> str:
    """Gabungkan kode barang 10 digit + urut 6 digit menjadi kode 16 digit."""
    kb = str(kode_barang or "").strip()
    ku = str(kode_urut or "").strip()
    if not (kb.isdigit() and len(kb) == 10):
        raise ValueError(f"kode barang harus 10 digit, dapat: '{kb}'")
    if not (ku.isdigit() and len(ku) == 6):
        raise ValueError(f"kode urut harus 6 digit, dapat: '{ku}'")
    return kb + ku


def pecah_kode16(kode: str):
    """Kode 16 digit → (kode_barang_10, kode_urut_6). None bila bukan 16 digit."""
    k = str(kode or "").strip()
    if not (k.isdigit() and len(k) == 16):
        return None
    return k[:10], k[10:]


def _kode_satker_dari_uakpb(kode_uakpb: str):
    """Ambil segmen 6 digit dari kode UAKPB bertitik.

    Contoh `126.01.1600.691778.000.KP` → `691778`. Diambil segmen ENAM digit
    PERTAMA — bukan angka 6 digit di mana pun — karena segmen lain (mis. 1600,
    000) berbeda panjang; bila format berubah dan tak ada segmen 6 digit,
    kembalikan None dan biarkan lapisan atas meminta operator memilih satker.
    """
    for seg in str(kode_uakpb or "").split("."):
        if seg.isdigit() and len(seg) == 6:
            return seg
    return None


def parse_teks_uc_per032(teks: str) -> dict:
    """Parse teks hasil ekstraksi PDF UC_PER032.

    Mengembalikan dict:
      - `uakpb_nama`, `uakpb_kode`, `kode_satker` (bisa None bila header aneh)
      - `items`: daftar {kode16, kode_barang, kode_urut, satuan, deskripsi}
      - `galat`: daris yang MIRIP data tapi tak lolos pola — dilaporkan, bukan
        dibuang senyap; format PDF berubah harus terlihat, bukan mengecilkan
        hasil diam-diam.

    Baris ganda (urut+kode sama muncul dua kali, mis. tumpang-tindih halaman)
    diambil kemunculan TERAKHIR — laporan SAKTI mengurutkan menaik sehingga
    yang terakhir adalah keadaan termutakhir di berkas itu.
    """
    baris_semua = [b.strip() for b in str(teks or "").splitlines()]

    uakpb_nama = None
    uakpb_kode = None
    per_kode = {}
    galat = []

    # Nama UAKPB menyambung ke baris berikut bila panjang (lihat contoh nyata:
    # "UAKPB :DEPUTI ..." lalu baris lanjutan "DIGITAL"). Cukup ambil baris
    # pertama ber-"UAKPB :"; nama hanya pelengkap tampilan, kode yang mengikat.
    for i, b in enumerate(baris_semua):
        if uakpb_nama is None:
            m = re.match(r"^UAKPB\s*:?\s*(.+)$", b)
            if m and "KODE" not in b.upper():
                uakpb_nama = m.group(1).strip()
        if uakpb_kode is None:
            m = _POLA_UAKPB.search(b)
            if m:
                uakpb_kode = m.group(1).strip()
        if uakpb_nama and uakpb_kode:
            break

    for b in baris_semua:
        if not b:
            continue
        m = _POLA_BARIS.match(b)
        if m:
            urut, kode, satuan, deskripsi = m.groups()
            per_kode[(kode, urut)] = {
                "kode16": kode + urut,
                "kode_barang": kode,
                "kode_urut": urut,
                "satuan": satuan.strip(),
                "deskripsi": deskripsi.strip(),
            }
            continue
        # Baris yang DIAWALI 6 digit tapi tak lolos pola = format berubah.
        # Header/footer (UAKPB, Halaman, Tanggal, judul kolom) memang bukan
        # data — jangan dianggap galat.
        if re.match(r"^\d{6}\s", b):
            galat.append(b[:120])

    items = sorted(per_kode.values(), key=lambda x: x["kode16"])
    return {
        "uakpb_nama": uakpb_nama,
        "uakpb_kode": uakpb_kode,
        "kode_satker": _kode_satker_dari_uakpb(uakpb_kode),
        "items": items,
        "galat": galat,
    }


def rencana_sinkron(items_pdf, existing_by_kode16):
    """Susun rencana upsert: apa yang baru, berubah, tak berubah, dan hilang.

    `existing_by_kode16`: dict kode16 -> {deskripsi, satuan} milik satker itu
    di basis data.

    Yang HILANG dari PDF **tidak dihapus** — laporan SAKTI bisa saja diunduh
    dengan filter, dan menghapus referensi yang dipakai transaksi adalah
    kerusakan data. Ia hanya dilaporkan agar operator tahu.
    """
    baru, ubah, tetap = [], [], []
    kode_pdf = set()
    for it in items_pdf:
        k = it["kode16"]
        kode_pdf.add(k)
        lama = existing_by_kode16.get(k)
        if lama is None:
            baru.append(it)
        elif (str(lama.get("deskripsi") or "").strip() != it["deskripsi"]
              or str(lama.get("satuan") or "").strip() != it["satuan"]):
            ubah.append(it)
        else:
            tetap.append(it)
    hilang = sorted(set(existing_by_kode16) - kode_pdf)
    return {"baru": baru, "ubah": ubah, "tetap": tetap, "hilang_dari_pdf": hilang}
