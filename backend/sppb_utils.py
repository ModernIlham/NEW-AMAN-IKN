"""Bentuk SPPB (Surat Perintah Pengeluaran Barang) — di SATU tempat.

SPPB adalah bukti bahwa barang persediaan benar-benar keluar dan benar-benar
diterima seseorang. Selama ini pengeluaran barang hanya meninggalkan baris
jurnal: ada catatan bahwa stok berkurang, tidak ada naskah yang bisa
ditandatangani penerimanya. Sisi masuknya sudah punya LPB sejak lama; sisi
keluarnya tidak punya apa-apa.

MURNI — tanpa Mongo, tanpa ReportLab. Pemformat tanggal dan rupiah diterima
sebagai argumen supaya tetap begitu.
"""

# Bidang yang benar-benar dicetak per baris barang. Register membekukan tepat
# ini — baris jurnal membawa rincian layer FIFO dan stok sebelum/sesudah yang
# tak muncul di naskah, dan menyimpannya membuat register tampak menjanjikan
# kesetiaan yang tidak ia jamin.
FIELD_BARIS = ("persediaan_id", "kode_barang", "nup", "nama_barang", "satuan",
               "jumlah", "harga_satuan", "total")

JUDUL = "SURAT PERINTAH PENGELUARAN BARANG (SPPB)"

HEADERS = ["No", "Kode Barang", "Nama Barang", "Jumlah", "Satuan",
           "Nilai (Rp)"]
WIDTHS = [26, 120, 210, 55, 60, 90]


def baris_dari_jurnal(jurnal) -> list:
    """Baris jurnal keluar → baris SPPB yang dibekukan."""
    keluar = []
    for j in jurnal or []:
        keluar.append({k: (j or {}).get(k) for k in FIELD_BARIS})
    return keluar


def total_nilai(baris) -> float:
    """Jumlah nilai seluruh baris. Baris cacat dihitung 0, bukan melempar —
    satu angka rusak tak boleh membuat SELURUH naskah gagal terbit."""
    jml = 0.0
    for b in baris or []:
        try:
            jml += float((b or {}).get("total") or 0)
        except (TypeError, ValueError):
            continue
    return jml


def isi_tabel(baris, fmt_rp=None) -> list:
    """Isi tabel siap cetak (tanpa baris kepala)."""
    rp = fmt_rp or (lambda v: str(v or 0))
    out = []
    for i, b in enumerate(baris or []):
        d = b or {}
        out.append([str(i + 1), str(d.get("kode_barang") or "-"),
                    str(d.get("nama_barang") or "-"),
                    str(d.get("jumlah") or 0), str(d.get("satuan") or "-"),
                    rp(d.get("total"))])
    return out


def perihal_agenda(jenis_label="") -> str:
    """Perihal untuk buku agenda Persuratan — satu baris."""
    j = str(jenis_label or "").strip()
    return f"Surat Perintah Pengeluaran Barang (SPPB) — {j}" if j else \
        "Surat Perintah Pengeluaran Barang (SPPB)"


def nama_berkas(nomor="") -> str:
    aman = "".join(c if (c.isalnum() or c in "-_") else "_"
                   for c in str(nomor or "").strip())
    return f"SPPB_{aman}.pdf" if aman else "SPPB.pdf"


def ringkas_sppb(sppb) -> dict:
    """SPPB → ringkasan untuk pesan WA/email penanda tangan.

    Tanpa ini pesannya menyusut jadi "judul + tautan": penanda tangan harus
    membuka tautan sekadar untuk tahu dokumen apa yang ia teken, dan setelah
    berbulan-bulan tak ada jejak yang bisa dicari di riwayat percakapannya.
    """
    d = sppb or {}
    items = d.get("items") or []
    try:
        jumlah = int(d.get("jumlah_barang") or 0)
    except (TypeError, ValueError):
        jumlah = 0
    pihak = []
    penerima = str(d.get("penerima_nama") or "").strip()
    if penerima:
        pihak.append(f"{penerima} (Penerima)")
    kpb = str(d.get("kpb_nama") or "").strip()
    if kpb:
        pihak.append(f"{kpb} (Kuasa Pengguna Barang)")
    return {
        "nomor": str(d.get("nomor") or "").strip(),
        "perihal": perihal_agenda(d.get("jenis_label")),
        "tanggal": str(d.get("tanggal") or "")[:10],
        "pihak": pihak,
        "barang": [{"kode": str((b or {}).get("kode_barang") or "").strip(),
                    "nup": str((b or {}).get("nup") or "").strip(),
                    "nama": str((b or {}).get("nama_barang") or "").strip()}
                   for b in items[:3]],
        # Panjang `items` bisa terpotong proyeksi pembacaan; jumlahnya tidak
        # boleh ikut menyusut — angka itu bermakna "berapa barang keluar".
        "jumlah_barang": jumlah or len(items),
    }
