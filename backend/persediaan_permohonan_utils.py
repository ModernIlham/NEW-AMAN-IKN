"""Permohonan transaksi persediaan ber-persetujuan — SEDIA-KPB (murni).

Keputusan pemilik (2026-08-09): SEMUA transaksi persediaan (masuk, keluar,
massal, opname, koreksi nilai, hapus definitif, pindah gudang) diajukan
sebagai PERMOHONAN lalu dieksekusi hanya saat DISETUJUI oleh admin satker
yang BUKAN pengajunya — pemisahan peran ditegakkan kode, bukan kebiasaan
(pola izin darurat IoT). Dokumen "Surat Persetujuan Transaksi Persediaan"
terbit ber-nomor dengan tanda tangan Kuasa Pengguna Barang.

Modul ini hanya berisi aturan MURNI (tanpa DB/HTTP) supaya bisa diuji tanpa
infrastruktur; penegakan + eksekusi ada di routes/persediaan_permohonan.py.
"""

# Jalur = endpoint eksekusi yang diwakilinya. Payload permohonan adalah body
# ASLI endpoint itu, divalidasi ulang oleh model Pydantic yang sama saat
# dieksekusi — permohonan tidak melahirkan skema kedua yang bisa melenceng.
JALUR_PERMOHONAN = {
    "masuk": "Transaksi Masuk",
    "keluar": "Transaksi Keluar",
    "massal": "Transaksi Massal",
    "opname": "Opname Fisik (P01)",
    "koreksi_nilai": "Koreksi Nilai",
    "hapus_definitif": "Penghapusan Definitif ber-SK",
    "pindah_gudang": "Pindah Gudang",
}

# diusulkan → (diproses) → disetujui | ditolak; pengaju boleh membatalkan
# selama masih diusulkan. 'diproses' adalah KLAIM ATOMIK anti-double-approve:
# dua admin menekan Setujui bersamaan → hanya satu yang lolos transisi
# bersyarat, yang lain 409.
STATUS_PERMOHONAN = ("diusulkan", "diproses", "disetujui", "ditolak",
                     "dibatalkan")


def validate_permohonan_baru(jalur: str, payload, item_id: str = ""):
    """(ok, err) bentuk minimum permohonan — validasi ISI transaksi tetap
    milik model Pydantic + validator endpoint eksekusi (satu sumber aturan)."""
    if jalur not in JALUR_PERMOHONAN:
        valid = ", ".join(sorted(JALUR_PERMOHONAN))
        return False, f"Jalur permohonan tidak dikenal (pilihan: {valid})"
    if not isinstance(payload, dict) or not payload:
        return False, "Payload transaksi wajib diisi"
    if jalur == "massal":
        if not payload.get("items"):
            return False, "Permohonan massal wajib memuat daftar barang"
    elif not str(item_id or "").strip():
        return False, "item_id barang persediaan wajib diisi"
    return True, ""


def boleh_putuskan(permohonan: dict, user: dict):
    """(ok, err) — pemisahan pemohon/penyetuju.

    Pengaju TIDAK boleh menyetujui MAUPUN menolak permohonannya sendiri.
    Berlaku juga untuk admin: alur ini kehilangan maknanya bila satu orang
    bisa mengajukan lalu menyetujui dirinya. Satker ber-admin tunggal tetap
    berjalan lewat super-admin sebagai penyetuju.
    """
    pengaju = str((permohonan or {}).get("diajukan_oleh") or "").strip()
    pemutus = str((user or {}).get("username") or "").strip()
    if pengaju and pemutus and pengaju == pemutus:
        return False, ("Pengaju tidak boleh menyetujui/menolak permohonannya "
                       "sendiri — minta admin lain atau super-admin")
    return True, ""


def ringkasan_permohonan(jalur: str, payload: dict, nama_barang: str = ""):
    """Satu kalimat ringkas untuk daftar & surat — murni, tahan payload cacat."""
    p = payload or {}
    label = JALUR_PERMOHONAN.get(jalur, jalur)
    if jalur == "massal":
        n = len(p.get("items") or [])
        arah = str(p.get("arah") or "")
        return f"{label}: {n} barang ({arah} — {p.get('jenis', '-')})"
    inti = str(nama_barang or "").strip() or "barang"
    if jalur == "koreksi_nilai":
        return f"{label} {inti}: Rp{p.get('nilai', 0)} ({p.get('jenis', '-')})"
    if jalur == "opname":
        return f"{label} {inti}: stok fisik {p.get('stok_fisik', '-')}"
    if jalur == "pindah_gudang":
        return f"{label} {inti} → {p.get('lokasi_baru', '-')}"
    if jalur == "hapus_definitif":
        return (f"{label} {inti}: {p.get('jumlah', '-')} unit "
                f"({p.get('jenis', '-')}, SK {p.get('sk_nomor', '-')})")
    return (f"{label} {inti}: {p.get('jumlah', '-')} unit "
            f"({p.get('jenis', '-')})")
