"""LAPORAN PENERIMAAN BARANG (LPB) — helper MURNI, tanpa I/O dan tanpa DB.

LPB adalah dokumen yang menyatakan "barang ini benar-benar DITERIMA satker,
sekian jumlahnya, dalam kondisi begini, pada tanggal itu". Selama ini AMAN
hanya menerbitkannya untuk PERSEDIAAN — padahal laptop, kendaraan, dan gedung
juga diterima lewat pintu yang sama dan menuntut bukti terima yang sama.

TIGA KEPUTUSAN YANG MENENTUKAN BENTUK MODUL INI
================================================

1. **Satu BAST bisa melahirkan DUA jenis catatan.** Satu kontrak pengadaan
   lazim memuat kertas HVS (persediaan) DAN printer (aset) sekaligus. Memaksa
   operator memilah sendiri lalu menekan dua tombol berbeda adalah pekerjaan
   yang komputer bisa lakukan tanpa salah — dan yang manusia PASTI salah
   sesekali. Karena itu pemilahan hidup di sini, sebagai fungsi murni yang
   bisa diuji, bukan tersebar di dua endpoint.

2. **Golongan barang ditentukan oleh DIGIT PERTAMA kode barang**, mengikuti
   kodefikasi BMN: golongan 1 = Persediaan, 2 = Tanah, 3 = Peralatan & Mesin,
   4 = Gedung & Bangunan, 5 = Jalan/Irigasi/Jaringan, 6 = Aset Tetap Lainnya,
   7 = KDP, 8 = Aset Tak Berwujud. Aturan ini SUDAH dipakai
   `daftarkan_persediaan`; di sini ia dinaikkan jadi satu tempat bernama
   supaya kedua jalur tak bisa lagi berbeda pendapat diam-diam.

3. **Barang tanpa kode bukan barang persediaan, dan bukan pula aset.** Ia
   barang yang BELUM BISA DICATAT. Menebaknya ke salah satu keranjang akan
   membuat satu baris BAST menghilang tanpa jejak — jadi ia jadi keranjang
   ketiga yang eksplisit, untuk dilaporkan balik ke operator.
"""

# Digit pertama kode barang → golongan BMN (kodefikasi Kemenkeu).
GOLONGAN_BARANG = {
    "1": "Persediaan",
    "2": "Tanah",
    "3": "Peralatan dan Mesin",
    "4": "Gedung dan Bangunan",
    "5": "Jalan, Irigasi, dan Jaringan",
    "6": "Aset Tetap Lainnya",
    "7": "Konstruksi Dalam Pengerjaan",
    "8": "Aset Tak Berwujud",
}

# Kategori LPB. Bukan sekadar label: menentukan kolom mana yang dicetak (NUP
# hanya bermakna untuk BMN) dan judul dokumennya.
KATEGORI_LPB = {
    "persediaan": "Persediaan",
    "aset": "Barang Milik Negara (Aset Tetap)",
}


def golongan_kode(kode) -> str:
    """Digit pertama kode barang — '' bila kode kosong/tak berdigit."""
    k = str(kode or "").strip()
    return k[0] if k and k[0].isdigit() else ""


def label_golongan(kode) -> str:
    """Nama golongan BMN untuk kode barang; '' bila tak dikenali."""
    return GOLONGAN_BARANG.get(golongan_kode(kode), "")


def is_persediaan(kode) -> bool:
    """Kode barang termasuk golongan 1 (Persediaan)?

    Sengaja BUKAN `kode.startswith('1')` yang tersebar di pemanggil: kode
    kosong harus menjawab False di sini, dan pemanggil tak boleh menebak.
    """
    return golongan_kode(kode) == "1"


def pilah_barang_perolehan(barang) -> dict:
    """Baris barang BAST → tiga keranjang tujuan pencatatan.

    - `persediaan`  — golongan 1: masuk stok lewat jurnal FIFO.
    - `aset`        — golongan 2–8: jadi draft aset ber-NUP.
    - `tanpa_kode`  — kode kosong: TIDAK BISA dicatat ke mana pun. Bukan
                      kesalahan operator yang perlu dihukum dengan diam;
                      dikembalikan apa adanya supaya layar bisa berkata
                      "tiga baris ini butuh kode barang dulu".

    Tiap keranjang memuat `(indeks_asli, baris)` — indeksnya dipertahankan
    karena `POST /pengadaan/{id}/tautkan` mengalamatkan baris dengan indeks,
    dan keranjang yang kehilangan indeks membuat hasil tak bisa ditautkan
    balik ke baris yang melahirkannya.
    """
    hasil = {"persediaan": [], "aset": [], "tanpa_kode": []}
    for i, b in enumerate(barang or []):
        row = b or {}
        kode = str(row.get("kode") or "").strip()
        if not kode:
            hasil["tanpa_kode"].append((i, row))
        elif is_persediaan(kode):
            hasil["persediaan"].append((i, row))
        else:
            hasil["aset"].append((i, row))
    return hasil


def _angka(v, bawaan=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return bawaan


def baris_lpb_dari_aset(aset_dibuat) -> list:
    """Aset draft yang baru dibuat → baris tabel LPB.

    `aset_dibuat` = daftar dict berisi minimal asset_code/NUP/asset_name +
    `harga_satuan` baris BAST asalnya. Satu unit = satu baris ber-NUP: itulah
    seluruh gunanya LPB aset — membuktikan NUP mana saja yang benar-benar
    masuk, bukan sekadar "printer 5 unit".
    """
    baris = []
    for a in aset_dibuat or []:
        d = a or {}
        harga = _angka(d.get("harga_satuan"))
        baris.append({
            "asset_id": str(d.get("id") or d.get("asset_id") or ""),
            "kode_barang": str(d.get("asset_code") or "").strip(),
            "nup": str(d.get("NUP") or d.get("nup") or "").strip(),
            "nama_barang": str(d.get("asset_name") or "").strip(),
            "golongan": label_golongan(d.get("asset_code")),
            "jumlah": 1, "satuan": "Unit",
            "harga_satuan": harga, "total": harga,
            "keterangan": str(d.get("keterangan") or "Kondisi Baik & Lengkap"),
        })
    return baris


def total_nilai_lpb(items) -> float:
    """Jumlah kolom Total pada tabel LPB."""
    return sum(_angka((b or {}).get("total")) for b in items or [])


def ringkas_pencatatan(hasil_aset, hasil_persediaan, tanpa_kode=0) -> dict:
    """Gabungkan hasil dua jalur pencatatan jadi satu ringkasan untuk layar.

    Operator menekan SATU tombol; ia berhak melihat SATU jawaban. Angka gagal
    dan daftar alasannya tetap dibawa apa adanya — jalur massal di aplikasi
    ini memang tak transaksional (Mongo standalone), dan menyembunyikan
    kegagalan sebagian justru bentuk kebohongan yang paling mahal di sini.
    """
    a = hasil_aset or {}
    p = hasil_persediaan or {}
    gagal = list(a.get("gagal") or []) + list(p.get("gagal") or [])
    return {
        "aset_dibuat": int(a.get("dibuat") or 0),
        "aset_dilewati_tertaut": int(a.get("dilewati_tertaut") or 0),
        "persediaan_masuk": int(p.get("masuk") or 0),
        "persediaan_master_baru": int(p.get("dibuat_master") or 0),
        "persediaan_dilewati_terdaftar": int(p.get("dilewati_sudah_terdaftar") or 0),
        "tanpa_kode": int(tanpa_kode or 0),
        "gagal": gagal[:40],
        "total_gagal": len(gagal),
    }


def pesan_ringkas(r) -> str:
    """Ringkasan satu kalimat untuk toast — bahasa manusia, bukan JSON."""
    r = r or {}
    bagian = []
    if r.get("aset_dibuat"):
        bagian.append(f"{r['aset_dibuat']} aset")
    if r.get("persediaan_masuk"):
        bagian.append(f"{r['persediaan_masuk']} barang persediaan")
    inti = " dan ".join(bagian) if bagian else "tidak ada barang baru"
    ekor = []
    if r.get("tanpa_kode"):
        ekor.append(f"{r['tanpa_kode']} baris belum berkode barang")
    if r.get("total_gagal"):
        ekor.append(f"{r['total_gagal']} gagal")
    return f"Tercatat: {inti}" + (f" ({'; '.join(ekor)})" if ekor else "")
