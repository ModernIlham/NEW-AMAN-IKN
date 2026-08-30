"""State machine validasi tanda tangan elektronik dan label dokumennya.

Penanda tangan hanya *membubuhkan*. Operator/admin satker yang memeriksa
hasilnya lalu *memvalidasi*. Pemisahan ini mencegah pembubuhan yang salah
tempat atau deklarasi jumlah tanda tangan yang keliru langsung menjadikan
dokumen final.

Modul ini murni: tanpa basis data/I/O, supaya aturan status dan perapian judul
dapat diuji tanpa MongoDB.
"""
import re


# ``ditandatangani`` adalah status final era-lama. Ia tetap dianggap valid
# agar permintaan yang sudah selesai sebelum gerbang validator ditambahkan
# tidak berubah mundur menjadi "menunggu validasi".
STATUS_PEMBUBUHAN = {"menunggu_validasi", "terverifikasi", "ditandatangani"}
STATUS_TERVERIFIKASI = {"terverifikasi", "ditandatangani"}

LABEL_JENIS_TTD = {
    "bast": "BAST",
    "lpb": "LPB",
    "persetujuan_aset": "Persetujuan Aset",
    "persetujuan_persediaan": "Persetujuan Persediaan",
    "dokumen_unggahan": "Dokumen Unggahan",
    "dokumen": "Dokumen",
}


def sudah_membubuhkan(signer) -> bool:
    """Signer sudah mengirim hasil pembubuhan untuk diperiksa?"""
    s = signer or {}
    return (str(s.get("status") or "") in STATUS_PEMBUBUHAN
            or bool(str(s.get("signature_file_id") or "").strip()))


def sudah_terverifikasi(signer) -> bool:
    """Pembubuhan signer sudah diterima validator?"""
    return str((signer or {}).get("status") or "") in STATUS_TERVERIFIKASI


def status_permintaan(signers) -> str:
    """Turunkan status permintaan dari keadaan signer terkini.

    - semua tervalidasi  -> ``selesai``
    - semua membubuhkan -> ``menunggu_validasi``
    - sebagian masuk    -> ``sebagian``
    - belum ada         -> ``terkirim``
    """
    daftar = list(signers or [])
    if not daftar:
        return "terkirim"
    if all(sudah_terverifikasi(s) for s in daftar):
        return "selesai"
    if all(sudah_membubuhkan(s) for s in daftar):
        return "menunggu_validasi"
    if any(sudah_membubuhkan(s) for s in daftar):
        return "sebagian"
    return "terkirim"


def label_jenis_ttd(doc_type) -> str:
    jenis = str(doc_type or "dokumen").strip()
    return LABEL_JENIS_TTD.get(jenis, jenis.replace("_", " ").title() or "Dokumen")


def judul_ttd_tampil(judul, doc_type) -> str:
    """Judul ringkas untuk row, dengan jenis dokumen ditampilkan terpisah.

    Contoh data lama ``BAST BAST-035/...`` menjadi ``BAST-035/...``. Hanya
    awalan label jenis yang dibuang; nomor/isi judulnya tidak diubah.
    """
    teks = " ".join(str(judul or "").split()).strip()
    label = label_jenis_ttd(doc_type)
    if not teks:
        return label
    pola = re.compile(rf"^{re.escape(label)}\s+", re.IGNORECASE)
    sisa = pola.sub("", teks, count=1).strip()
    return sisa or teks
